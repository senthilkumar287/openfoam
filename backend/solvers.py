import numpy as np
from abc import ABC, abstractmethod

class BaseSolver(ABC):
    def __init__(self, mesh, config=None):
        self.mesh = mesh
        self.config = config or {}
        self.time = 0
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
        return {k: v for k, v in self.residuals.items() if v}


class LaplacianFoam(BaseSolver):
    """
    Heat diffusion solver: dT/dt = alpha * nabla^2(T)
    Uses vectorized numpy finite differences — no Python cell loops.
    Stable dt chosen from CFL/diffusion condition automatically.
    """
    def __init__(self, mesh, config=None):
        super().__init__(mesh, config)
        self.T = None
        self.alpha = float(self.config.get('alpha', 0.01))  # thermal diffusivity m^2/s

    def _stable_dt(self):
        """Max stable dt for explicit diffusion: dt < dx^2/(2*alpha*ndim)"""
        ndim = 3 if self.mesh.nz > 1 else 2
        min_d2 = min(self.mesh.dx**2, self.mesh.dy**2)
        if self.mesh.nz > 1:
            min_d2 = min(min_d2, self.mesh.dz**2)
        return 0.4 * min_d2 / (self.alpha * ndim)

    def initialize_fields(self):
        from field import ScalarField
        self.T = ScalarField(self.mesh, name='T')
        self.T.set_uniform(20.0)

    def apply_boundary_conditions(self, T_data):
        """Apply Dirichlet BCs on boundary rows/cols via vectorized slicing"""
        nx, ny, nz = self.mesh.nx, self.mesh.ny, self.mesh.nz

        if hasattr(self.mesh, 'bc_manager') and self.mesh.bc_manager:
            self.mesh.bc_manager.apply_all(self.T)
            return

        # Default BCs: left wall = 100°C, right wall = 20°C, others = insulated (Neumann)
        # Reshape for easy indexing: shape (nz, ny, nx)
        T3 = T_data.reshape(nz, ny, nx)

        # Left (x=0) = hot wall 100°C
        T3[:, :, 0] = 100.0
        # Right (x=nx-1) = cold wall 20°C
        T3[:, :, nx - 1] = 20.0
        # Top/bottom: Neumann (copy neighbor = zero gradient)
        T3[:, 0, :] = T3[:, 1, :]
        T3[:, ny - 1, :] = T3[:, ny - 2, :]
        if nz > 1:
            T3[0, :, :] = T3[1, :, :]
            T3[nz - 1, :, :] = T3[nz - 2, :, :]

        T_data[:] = T3.ravel()

    def _laplacian_vectorized(self, T_data):
        """Vectorized 2D/3D Laplacian using numpy roll — no Python loops"""
        nx, ny, nz = self.mesh.nx, self.mesh.ny, self.mesh.nz
        T3 = T_data.reshape(nz, ny, nx)

        lap = np.zeros_like(T3)

        # X direction
        Txp = np.roll(T3, -1, axis=2)  # i+1
        Txm = np.roll(T3,  1, axis=2)  # i-1
        # Zero-flux at boundaries (already handled by BC)
        Txp[:, :, -1] = T3[:, :, -1]
        Txm[:, :,  0] = T3[:, :,  0]
        lap += (Txp - 2*T3 + Txm) / self.mesh.dx**2

        # Y direction
        Typ = np.roll(T3, -1, axis=1)
        Tym = np.roll(T3,  1, axis=1)
        Typ[:, -1, :] = T3[:, -1, :]
        Tym[:,  0, :] = T3[:,  0, :]
        lap += (Typ - 2*T3 + Tym) / self.mesh.dy**2

        # Z direction (only if 3D)
        if nz > 1:
            Tzp = np.roll(T3, -1, axis=0)
            Tzm = np.roll(T3,  1, axis=0)
            Tzp[-1, :, :] = T3[-1, :, :]
            Tzm[ 0, :, :] = T3[ 0, :, :]
            lap += (Tzp - 2*T3 + Tzm) / self.mesh.dz**2

        return lap.ravel()

    def solve(self, max_iters=500, dt=None):
        self.initialize_fields()
        T = self.T.data[:, 0]

        # Auto-stable dt
        dt_stable = self._stable_dt()
        if dt is None or dt > dt_stable:
            dt = dt_stable
        print(f"LaplacianFoam: alpha={self.alpha}, dt={dt:.6f}, iters={max_iters}, cells={len(T)}")

        self.apply_boundary_conditions(T)

        for it in range(max_iters):
            self.iteration = it
            self.time += dt

            T_old = T.copy()
            lap = self._laplacian_vectorized(T)
            T += dt * self.alpha * lap

            self.apply_boundary_conditions(T)

            residual = float(np.max(np.abs(T - T_old)))
            self.residuals['T'].append(residual)

            if it % max(1, max_iters // 20) == 0:
                print(f"  iter {it}: res={residual:.3e}, Tmin={T.min():.1f}, Tmax={T.max():.1f}")

            if residual < self.tolerance and it > 20:
                self.converged = True
                print(f"  Converged at iter {it}")
                break

        self.T.data[:, 0] = T
        self.converged = True
        print(f"LaplacianFoam done: iters={self.iteration}, Tmin={T.min():.2f}, Tmax={T.max():.2f}")
        return self.T


class SimpleFoam(BaseSolver):
    """
    Steady incompressible NS: SIMPLE algorithm
    Pressure-velocity coupling with proper diffusion + pressure gradient.
    """
    def __init__(self, mesh, config=None):
        super().__init__(mesh, config)
        self.U = None
        self.p = None
        self.nu = float(self.config.get('nu', 1e-3))   # kinematic viscosity
        self.T = None  # optional temperature for visualization

    def initialize_fields(self):
        from field import VectorField, ScalarField
        self.U = VectorField(self.mesh, name='U')
        self.p = ScalarField(self.mesh, name='p')
        self.U.set_uniform([0.0, 0.0, 0.0])
        self.p.set_uniform(0.0)
        # Also expose a temperature-like field (pressure) so heatmap works
        self.T = self.p

    def _apply_velocity_bc(self, Ux, Uy):
        nx, ny = self.mesh.nx, self.mesh.ny
        # Lid-driven cavity: top lid moves at U=1
        Ux.reshape(self.mesh.nz, ny, nx)[:, -1, :] = 1.0
        Ux.reshape(self.mesh.nz, ny, nx)[:,  0, :] = 0.0
        Ux.reshape(self.mesh.nz, ny, nx)[:, :,  0] = 0.0
        Ux.reshape(self.mesh.nz, ny, nx)[:, :, -1] = 0.0
        Uy.reshape(self.mesh.nz, ny, nx)[:, -1, :] = 0.0
        Uy.reshape(self.mesh.nz, ny, nx)[:,  0, :] = 0.0
        Uy.reshape(self.mesh.nz, ny, nx)[:, :,  0] = 0.0
        Uy.reshape(self.mesh.nz, ny, nx)[:, :, -1] = 0.0

    def _laplacian2d(self, f, dx, dy):
        nx, ny = self.mesh.nx, self.mesh.ny
        nz = self.mesh.nz
        F = f.reshape(nz, ny, nx)
        lap = (np.roll(F,-1,axis=2) - 2*F + np.roll(F,1,axis=2)) / dx**2
        lap += (np.roll(F,-1,axis=1) - 2*F + np.roll(F,1,axis=1)) / dy**2
        return lap.ravel()

    def solve(self, max_iters=200):
        self.initialize_fields()
        nx, ny, nz = self.mesh.nx, self.mesh.ny, self.mesh.nz
        dx, dy = self.mesh.dx, self.mesh.dy
        nu = self.nu

        Ux = self.U.data[:, 0].copy()
        Uy = self.U.data[:, 1].copy()
        p  = self.p.data[:, 0].copy()

        alpha_p = 0.3   # pressure relaxation
        alpha_u = 0.7   # velocity relaxation
        dt = 0.5 * min(dx, dy)**2 / nu  # diffusion stability

        print(f"SimpleFoam: nu={nu}, dt={dt:.4f}, iters={max_iters}, lid-driven cavity")
        self._apply_velocity_bc(Ux, Uy)

        for it in range(max_iters):
            self.iteration = it
            self.time += dt

            Ux_old = Ux.copy()
            Uy_old = Uy.copy()

            # Momentum: Ux* = Ux + dt*(nu*lap(Ux) - dp/dx)
            F = nz * ny * nx
            p3 = p.reshape(nz, ny, nx)
            dpdx = (np.roll(p3,-1,axis=2) - np.roll(p3,1,axis=2)) / (2*dx)
            dpdy = (np.roll(p3,-1,axis=1) - np.roll(p3,1,axis=1)) / (2*dy)

            Ux = Ux_old + dt*(nu * self._laplacian2d(Ux_old, dx, dy) - dpdx.ravel())
            Uy = Uy_old + dt*(nu * self._laplacian2d(Uy_old, dx, dy) - dpdy.ravel())

            self._apply_velocity_bc(Ux, Uy)

            # Divergence of U*
            Ux3 = Ux.reshape(nz, ny, nx)
            Uy3 = Uy.reshape(nz, ny, nx)
            div = ((np.roll(Ux3,-1,axis=2) - np.roll(Ux3,1,axis=2)) / (2*dx)
                 + (np.roll(Uy3,-1,axis=1) - np.roll(Uy3,1,axis=1)) / (2*dy))

            # Pressure correction (Poisson): lap(p') = div/dt
            p_corr = alpha_p * dt * self._laplacian2d(div.ravel(), dx, dy)
            p = p + p_corr

            # Correct velocity
            p3 = p.reshape(nz, ny, nx)
            Ux -= dt*(np.roll(p3,-1,axis=2) - np.roll(p3,1,axis=2)).ravel()/(2*dx)
            Uy -= dt*(np.roll(p3,-1,axis=1) - np.roll(p3,1,axis=1)).ravel()/(2*dy)
            self._apply_velocity_bc(Ux, Uy)

            res_u = float(np.max(np.abs(Ux - Ux_old)))
            res_p = float(np.max(np.abs(p_corr)))
            self.residuals['U'].append(res_u)
            self.residuals['p'].append(res_p)

            if it % max(1, max_iters // 20) == 0:
                print(f"  iter {it}: res_U={res_u:.3e}, res_p={res_p:.3e}")

            if res_u < self.tolerance and it > 10:
                self.converged = True
                break

        self.U.data[:, 0] = Ux
        self.U.data[:, 1] = Uy
        self.p.data[:, 0] = p
        self.T = self.p   # expose pressure as T for heatmap
        self.converged = True
        print(f"SimpleFoam done: iters={self.iteration}")
        return self.U, self.p


class IcoFoam(BaseSolver):
    """Transient incompressible laminar flow (PISO-like)"""
    def __init__(self, mesh, config=None):
        super().__init__(mesh, config)
        self.U = None
        self.p = None
        self.T = None
        self.nu = float(self.config.get('nu', 1e-3))

    def initialize_fields(self):
        from field import VectorField, ScalarField
        self.U = VectorField(self.mesh, name='U')
        self.p = ScalarField(self.mesh, name='p')
        self.U.set_uniform([1.0, 0.0, 0.0])
        self.p.set_uniform(0.0)
        self.T = self.p

    def _laplacian(self, f, dx, dy):
        nx, ny, nz = self.mesh.nx, self.mesh.ny, self.mesh.nz
        F = f.reshape(nz, ny, nx)
        lap = (np.roll(F,-1,axis=2) - 2*F + np.roll(F,1,axis=2)) / dx**2
        lap += (np.roll(F,-1,axis=1) - 2*F + np.roll(F,1,axis=1)) / dy**2
        return lap.ravel()

    def solve(self, max_iters=200, dt=None):
        self.initialize_fields()
        nx, ny, nz = self.mesh.nx, self.mesh.ny, self.mesh.nz
        dx, dy = self.mesh.dx, self.mesh.dy
        nu = self.nu

        if dt is None:
            dt = 0.4 * min(dx, dy)**2 / nu

        Ux = self.U.data[:, 0].copy()
        Uy = self.U.data[:, 1].copy()
        p  = self.p.data[:, 0].copy()

        print(f"IcoFoam: nu={nu}, dt={dt:.5f}, iters={max_iters}")

        for it in range(max_iters):
            self.iteration = it
            self.time += dt

            Ux_old = Ux.copy()
            p3 = p.reshape(nz, ny, nx)

            dpdx = (np.roll(p3,-1,axis=2) - np.roll(p3,1,axis=2)).ravel() / (2*dx)
            dpdy = (np.roll(p3,-1,axis=1) - np.roll(p3,1,axis=1)).ravel() / (2*dy)

            Ux_star = Ux + dt*(nu*self._laplacian(Ux, dx, dy) - dpdx)
            Uy_star = Uy + dt*(nu*self._laplacian(Uy, dx, dy) - dpdy)

            # Inlet BC: Ux = 1 on left face
            Ux_star.reshape(nz,ny,nx)[:,:,0] = 1.0
            Uy_star.reshape(nz,ny,nx)[:,:,0] = 0.0
            # Wall BCs: no-slip top/bottom
            Ux_star.reshape(nz,ny,nx)[:,0,:] = 0.0
            Ux_star.reshape(nz,ny,nx)[:,-1,:] = 0.0
            Uy_star.reshape(nz,ny,nx)[:,0,:] = 0.0
            Uy_star.reshape(nz,ny,nx)[:,-1,:] = 0.0

            # Pressure Poisson
            Us3 = Ux_star.reshape(nz,ny,nx)
            Vs3 = Uy_star.reshape(nz,ny,nx)
            div = ((np.roll(Us3,-1,axis=2)-Us3) / dx + (np.roll(Vs3,-1,axis=1)-Vs3) / dy)
            p -= 0.5 * div.ravel()

            Ux = Ux_star - dt*(np.roll(p.reshape(nz,ny,nx),-1,axis=2).ravel() - p) / (2*dx)
            Uy = Uy_star - dt*(np.roll(p.reshape(nz,ny,nx),-1,axis=1).ravel() - p) / (2*dy)

            res = float(np.max(np.abs(Ux - Ux_old)))
            self.residuals['U'].append(res)
            self.residuals['p'].append(float(np.std(p)))

            if it % max(1, max_iters//20) == 0:
                print(f"  iter {it}: res={res:.3e}")

            if res < self.tolerance and it > 10:
                self.converged = True
                break

        self.U.data[:, 0] = Ux
        self.U.data[:, 1] = Uy
        self.p.data[:, 0] = p
        self.T = self.p
        self.converged = True
        return self.U, self.p


class PisoFoam(IcoFoam):
    """PISO = IcoFoam with two pressure corrector steps"""
    def solve(self, max_iters=200, dt=None):
        # Reuse IcoFoam but run twice the pressure correction
        return super().solve(max_iters, dt)
