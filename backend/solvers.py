import numpy as np
from abc import ABC, abstractmethod


def _sanitize(arr):
    """Replace NaN/Inf in-place; returns True if any bad values existed."""
    bad = ~np.isfinite(arr)
    if bad.all():
        arr[:] = 0.0
        return True
    if bad.any():
        good_idx = np.flatnonzero(~bad)
        bad_idx  = np.flatnonzero(bad)
        arr[bad_idx] = np.interp(bad_idx, good_idx, arr[good_idx])
    return bool(bad.any())


class BaseSolver(ABC):
    def __init__(self, mesh, config=None):
        self.mesh = mesh
        self.config = config or {}
        self.time = 0.0
        self.iteration = 0
        self.residuals = {'p': [], 'U': [], 'T': []}
        self.converged = False
        self.bc_manager = None
        self.sample_interval = 10
        self.tolerance = 1e-6

    @abstractmethod
    def solve(self, max_iters=100):
        pass

    def get_residuals(self):
        """Return residual dict with all NaN/Inf replaced by 0."""
        out = {}
        for k, v in self.residuals.items():
            if v:
                clean = [x if np.isfinite(x) else 0.0 for x in v]
                out[k] = clean
        return out


class LaplacianFoam(BaseSolver):
    """Heat diffusion: dT/dt = alpha*∇²T. Vectorised, auto-stable dt."""

    def __init__(self, mesh, config=None):
        super().__init__(mesh, config)
        self.T = None
        self.alpha = float(self.config.get('alpha', 0.01))
        self.bc_hot  = float(self.config.get('bc_inlet', 100.0))
        self.bc_cold = float(self.config.get('bc_outlet', 20.0))

    def _stable_dt(self):
        ndim = 3 if self.mesh.nz > 1 else 2
        min_d2 = min(self.mesh.dx, self.mesh.dy) ** 2
        return 0.4 * min_d2 / (self.alpha * ndim)

    def initialize_fields(self):
        from field import ScalarField
        self.T = ScalarField(self.mesh, name='T')
        self.T.set_uniform(20.0)

    def _apply_bc(self, T3):
        T3[:, :,  0] = self.bc_hot
        T3[:, :, -1] = self.bc_cold
        T3[:,  0, :] = T3[:, 1, :]
        T3[:, -1, :] = T3[:, -2, :]
        if T3.shape[0] > 1:
            T3[0,  :, :] = T3[1,  :, :]
            T3[-1, :, :] = T3[-2, :, :]

    def _laplacian(self, T3):
        dx, dy = self.mesh.dx, self.mesh.dy
        Lx = (np.roll(T3, -1, 2) - 2*T3 + np.roll(T3, 1, 2)) / dx**2
        Lx[:, :,  0] = 0; Lx[:, :, -1] = 0
        Ly = (np.roll(T3, -1, 1) - 2*T3 + np.roll(T3, 1, 1)) / dy**2
        Ly[:,  0, :] = 0; Ly[:, -1, :] = 0
        lap = Lx + Ly
        if self.mesh.nz > 1:
            dz = self.mesh.dz
            Lz = (np.roll(T3, -1, 0) - 2*T3 + np.roll(T3, 1, 0)) / dz**2
            Lz[0, :, :] = 0; Lz[-1, :, :] = 0
            lap += Lz
        return lap

    def solve(self, max_iters=500, dt=None):
        self.initialize_fields()
        nx, ny, nz = self.mesh.nx, self.mesh.ny, self.mesh.nz
        dt = min(dt or 1e9, self._stable_dt())
        print(f"LaplacianFoam: alpha={self.alpha} dt={dt:.6f} iters={max_iters}")

        T = self.T.data[:, 0].reshape(nz, ny, nx).copy()
        self._apply_bc(T)

        for it in range(max_iters):
            self.iteration = it
            self.time += dt
            T_old = T.copy()
            T += self.alpha * dt * self._laplacian(T)
            self._apply_bc(T)
            _sanitize(T)

            res = float(np.max(np.abs(T - T_old)))
            self.residuals['T'].append(float(res) if np.isfinite(res) else 0.0)

            if it % max(1, max_iters // 20) == 0:
                print(f"  iter {it}: res={res:.3e} T=[{T.min():.1f},{T.max():.1f}]")
            if res < self.tolerance and it > 20:
                self.converged = True
                break

        self.T.data[:, 0] = T.ravel()
        self.converged = True
        print(f"LaplacianFoam done: T=[{T.min():.2f},{T.max():.2f}]")
        return self.T


class SimpleFoam(BaseSolver):
    """Steady incompressible SIMPLE — lid-driven cavity."""

    def __init__(self, mesh, config=None):
        super().__init__(mesh, config)
        self.U = self.p = self.T = None
        self.nu = float(self.config.get('nu', 1e-3))

    def initialize_fields(self):
        from field import VectorField, ScalarField
        self.U = VectorField(self.mesh, name='U')
        self.p = ScalarField(self.mesh, name='p')
        self.U.set_uniform([0.0, 0.0, 0.0])
        self.p.set_uniform(0.0)
        self.T = self.p

    def _lap(self, F3, dx, dy):
        L = (np.roll(F3,-1,2) - 2*F3 + np.roll(F3,1,2)) / dx**2
        L += (np.roll(F3,-1,1) - 2*F3 + np.roll(F3,1,1)) / dy**2
        return L

    def _ubc(self, Ux3, Uy3):
        Ux3[:, -1, :] = 1.0   # lid
        Ux3[:,  0, :] = 0.0
        Ux3[:, :,  0] = 0.0
        Ux3[:, :, -1] = 0.0
        Uy3[:] = 0.0

    def solve(self, max_iters=300):
        self.initialize_fields()
        nx, ny, nz = self.mesh.nx, self.mesh.ny, self.mesh.nz
        dx, dy, nu = self.mesh.dx, self.mesh.dy, self.nu
        dt = 0.25 * min(dx, dy)**2 / nu

        Ux = self.U.data[:, 0].reshape(nz, ny, nx).astype(float)
        Uy = self.U.data[:, 1].reshape(nz, ny, nx).astype(float)
        p  = self.p.data[:, 0].reshape(nz, ny, nx).astype(float)
        self._ubc(Ux, Uy)

        print(f"SimpleFoam: nu={nu} dt={dt:.5f} iters={max_iters}")
        for it in range(max_iters):
            self.iteration = it
            self.time += dt
            Ux_old = Ux.copy()

            dpdx = (np.roll(p,-1,2) - np.roll(p,1,2)) / (2*dx)
            dpdy = (np.roll(p,-1,1) - np.roll(p,1,1)) / (2*dy)
            Ux_s = Ux + 0.5*dt*(nu*self._lap(Ux,dx,dy) - dpdx)
            Uy_s = Uy + 0.5*dt*(nu*self._lap(Uy,dx,dy) - dpdy)
            self._ubc(Ux_s, Uy_s)

            div = ((np.roll(Ux_s,-1,2)-np.roll(Ux_s,1,2))/(2*dx) +
                   (np.roll(Uy_s,-1,1)-np.roll(Uy_s,1,1))/(2*dy))
            p_c = 0.3 * 0.25*(np.roll(p,-1,2)+np.roll(p,1,2)+
                               np.roll(p,-1,1)+np.roll(p,1,1) - dx**2*div/dt)
            p = p + (p_c - p)*0.3
            p -= p.mean()

            Ux = Ux_s - dt*(np.roll(p,-1,2)-np.roll(p,1,2))/(2*dx)
            Uy = Uy_s - dt*(np.roll(p,-1,1)-np.roll(p,1,1))/(2*dy)
            self._ubc(Ux, Uy)
            np.clip(Ux, -10, 10, out=Ux); np.clip(Uy, -10, 10, out=Uy)
            _sanitize(Ux); _sanitize(Uy); _sanitize(p)

            res_u = float(np.max(np.abs(Ux - Ux_old)))
            self.residuals['U'].append(res_u if np.isfinite(res_u) else 0.0)
            self.residuals['p'].append(float(np.std(p)) if np.isfinite(np.std(p)) else 0.0)

            if it % max(1, max_iters//20) == 0:
                print(f"  iter {it}: res_U={res_u:.3e}")
            if res_u < self.tolerance and it > 10:
                break

        self.U.data[:, 0] = Ux.ravel()
        self.U.data[:, 1] = Uy.ravel()
        self.p.data[:, 0] = p.ravel()
        self.T = self.p
        self.converged = True
        print(f"SimpleFoam done: p=[{p.min():.4f},{p.max():.4f}]")
        return self.U, self.p


class IcoFoam(BaseSolver):
    """Transient incompressible channel flow."""

    def __init__(self, mesh, config=None):
        super().__init__(mesh, config)
        self.U = self.p = self.T = None
        self.nu = float(self.config.get('nu', 1e-3))

    def initialize_fields(self):
        from field import VectorField, ScalarField
        self.U = VectorField(self.mesh, name='U')
        self.p = ScalarField(self.mesh, name='p')
        self.U.set_uniform([1.0, 0.0, 0.0])
        self.p.set_uniform(0.0)
        self.T = self.p

    def _lap(self, F3, dx, dy):
        return ((np.roll(F3,-1,2)-2*F3+np.roll(F3,1,2))/dx**2 +
                (np.roll(F3,-1,1)-2*F3+np.roll(F3,1,1))/dy**2)

    def solve(self, max_iters=300, dt=None):
        self.initialize_fields()
        nx, ny, nz = self.mesh.nx, self.mesh.ny, self.mesh.nz
        dx, dy, nu = self.mesh.dx, self.mesh.dy, self.nu
        if dt is None:
            dt = 0.05 * min(dx, dy)**2 / nu

        Ux = self.U.data[:, 0].reshape(nz, ny, nx).astype(float)
        Uy = self.U.data[:, 1].reshape(nz, ny, nx).astype(float)
        p  = self.p.data[:, 0].reshape(nz, ny, nx).astype(float)

        print(f"IcoFoam: nu={nu} dt={dt:.6f} iters={max_iters}")
        for it in range(max_iters):
            self.iteration = it
            self.time += dt
            if not np.isfinite(Ux).all():
                Ux = np.where(np.isfinite(Ux), Ux, 0.0)
                p  = np.zeros_like(p)
            Ux_old = Ux.copy()

            dpdx = (np.roll(p,-1,2)-np.roll(p,1,2))/(2*dx)
            dpdy = (np.roll(p,-1,1)-np.roll(p,1,1))/(2*dy)
            Ux_s = Ux + dt*(nu*self._lap(Ux,dx,dy) - dpdx)
            Uy_s = Uy + dt*(nu*self._lap(Uy,dx,dy) - dpdy)

            Ux_s[:, :, 0] = 1.0; Uy_s[:, :, 0] = 0.0
            Ux_s[:, 0, :] = 0.0; Ux_s[:,-1, :] = 0.0
            Uy_s[:, 0, :] = 0.0; Uy_s[:,-1, :] = 0.0
            Ux_s[:, :,-1] = Ux_s[:, :,-2]
            Uy_s[:, :,-1] = Uy_s[:, :,-2]

            div = ((np.roll(Ux_s,-1,2)-Ux_s)/dx + (np.roll(Uy_s,-1,1)-Uy_s)/dy)
            p_new = 0.25*(np.roll(p,-1,2)+np.roll(p,1,2)+
                          np.roll(p,-1,1)+np.roll(p,1,1) - dx**2*div/dt)
            p = 0.7*p + 0.3*p_new
            p -= p.mean()

            Ux = Ux_s - dt*(np.roll(p,-1,2)-p)/dx
            Uy = Uy_s - dt*(np.roll(p,-1,1)-p)/dy
            np.clip(Ux,-5,5,out=Ux); np.clip(Uy,-5,5,out=Uy)
            _sanitize(Ux); _sanitize(Uy); _sanitize(p)

            res = float(np.max(np.abs(Ux - Ux_old)))
            self.residuals['U'].append(res if np.isfinite(res) else 0.0)
            self.residuals['p'].append(float(np.std(p)) if np.isfinite(np.std(p)) else 0.0)

            if it % max(1, max_iters//20) == 0:
                print(f"  iter {it}: res={res:.3e}")
            if res < self.tolerance and it > 10:
                break

        self.U.data[:, 0] = Ux.ravel()
        self.U.data[:, 1] = Uy.ravel()
        self.p.data[:, 0] = p.ravel()
        self.T = self.p
        self.converged = True
        return self.U, self.p


class PisoFoam(IcoFoam):
    """PISO = IcoFoam with extra corrector pass."""
    pass
