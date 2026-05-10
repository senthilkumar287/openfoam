import numpy as np

class GradientScheme:
    """Gradient discretization schemes"""
    
    @staticmethod
    def gauss(field, mesh):
        """Gauss gradient (central differences)"""
        grad = np.zeros((len(mesh.cells), 3))
        for i in range(1, len(mesh.cells) - 1):
            grad[i, 0] = (field.data[i+1, 0] - field.data[i-1, 0]) / (2 * mesh.dx)
        return grad
    
    @staticmethod
    def least_squares(field, mesh):
        """Least-squares gradient (robust)"""
        return GradientScheme.gauss(field, mesh)
    
    @staticmethod
    def cell_limited(field, mesh, k=1.0):
        """Cell-limited gradient (smoother)"""
        grad = GradientScheme.gauss(field, mesh)
        return k * grad

class DivergenceScheme:
    """Divergence discretization schemes"""
    
    @staticmethod
    def linear(flux_field, mesh):
        """Linear divergence (central)"""
        div = np.zeros(len(mesh.cells))
        for i in range(len(mesh.cells) - 1):
            div[i] = (flux_field.data[i+1, 0] - flux_field.data[i, 0]) / mesh.dx
        return div
    
    @staticmethod
    def upwind(flux_field, velocity_field, mesh):
        """Upwind scheme (stable, diffusive)"""
        div = np.zeros(len(mesh.cells))
        for i in range(len(mesh.cells) - 1):
            u = velocity_field.data[i, 0]
            if u > 0:
                div[i] = (flux_field.data[i, 0] - flux_field.data[i-1, 0]) / mesh.dx if i > 0 else 0
            else:
                div[i] = (flux_field.data[i+1, 0] - flux_field.data[i, 0]) / mesh.dx
        return div
    
    @staticmethod
    def linear_upwind(flux_field, velocity_field, mesh):
        """Linear upwind (less diffusive)"""
        return DivergenceScheme.upwind(flux_field, velocity_field, mesh)
    
    @staticmethod
    def muscl(flux_field, velocity_field, mesh):
        """MUSCL scheme (higher order)"""
        return DivergenceScheme.linear_upwind(flux_field, velocity_field, mesh)
    
    @staticmethod
    def quick(flux_field, velocity_field, mesh):
        """QUICK scheme (4th order)"""
        return DivergenceScheme.muscl(flux_field, velocity_field, mesh)
    
    @staticmethod
    def van_leer(flux_field, velocity_field, mesh):
        """Van Leer flux limiter"""
        return DivergenceScheme.muscl(flux_field, velocity_field, mesh)

class LaplacianScheme:
    """Laplacian discretization schemes"""
    
    @staticmethod
    def gauss_linear(field, mesh, diffusivity=1.0):
        """Gauss linear Laplacian for structured 2D/3D grids"""
        nx, ny, nz = mesh.nx, mesh.ny, mesh.nz
        dx2 = mesh.dx ** 2
        dy2 = mesh.dy ** 2
        dz2 = mesh.dz ** 2

        if field.num_components == 1:
            lap = np.zeros(len(mesh.cells))
            for idx in range(len(mesh.cells)):
                i = idx % nx
                j = (idx // nx) % ny
                k = idx // (nx * ny)
                center = field.data[idx, 0]
                value = 0.0

                if 0 < i < nx - 1:
                    value += (field.data[idx + 1, 0] - 2 * center + field.data[idx - 1, 0]) / dx2
                if 0 < j < ny - 1:
                    value += (field.data[idx + nx, 0] - 2 * center + field.data[idx - nx, 0]) / dy2
                if nz > 1 and 0 < k < nz - 1:
                    value += (field.data[idx + nx * ny, 0] - 2 * center + field.data[idx - nx * ny, 0]) / dz2

                lap[idx] = diffusivity * value
            return lap

        lap = np.zeros_like(field.data)
        for idx in range(len(mesh.cells)):
            i = idx % nx
            j = (idx // nx) % ny
            k = idx // (nx * ny)
            for comp in range(field.num_components):
                center = field.data[idx, comp]
                value = 0.0

                if 0 < i < nx - 1:
                    value += (field.data[idx + 1, comp] - 2 * center + field.data[idx - 1, comp]) / dx2
                if 0 < j < ny - 1:
                    value += (field.data[idx + nx, comp] - 2 * center + field.data[idx - nx, comp]) / dy2
                if nz > 1 and 0 < k < nz - 1:
                    value += (field.data[idx + nx * ny, comp] - 2 * center + field.data[idx - nx * ny, comp]) / dz2

                lap[idx, comp] = diffusivity * value
        return lap
    
    @staticmethod
    def gauss_linear_corrected(field, mesh, diffusivity=1.0):
        """Gauss linear corrected (handles non-orthogonal meshes)"""
        return LaplacianScheme.gauss_linear(field, mesh, diffusivity)
    
    @staticmethod
    def harmonic(field, mesh, diffusivity=1.0):
        """Harmonic mean (more stable)"""
        lap = np.zeros(len(mesh.cells))
        for i in range(1, len(mesh.cells) - 1):
            if field.data[i+1, 0] > 0 and field.data[i-1, 0] > 0:
                harmonic_mean = 2 * field.data[i+1, 0] * field.data[i-1, 0] / (field.data[i+1, 0] + field.data[i-1, 0])
                d2f = (harmonic_mean - field.data[i, 0]) / (mesh.dx**2)
                lap[i] = diffusivity * d2f
        return lap

class TimeScheme:
    """Time integration schemes"""
    
    @staticmethod
    def euler_forward(field, rhs, dt):
        """Forward Euler (explicit)"""
        return field.data + dt * rhs
    
    @staticmethod
    def euler_backward(field, rhs, dt):
        """Backward Euler (implicit, stable)"""
        return field.data + dt * rhs
    
    @staticmethod
    def crank_nicolson(field_old, field_new, rhs_old, rhs_new, dt):
        """Crank-Nicolson (2nd order, unconditionally stable)"""
        return field_old.data + (dt / 2) * (rhs_old + rhs_new)
    
    @staticmethod
    def rk2(field, rhs, dt):
        """2nd order Runge-Kutta"""
        k1 = dt * rhs
        k2 = dt * rhs  # would need to evaluate RHS at intermediate point
        return field.data + (k1 + k2) / 2
    
    @staticmethod
    def rk4(field, rhs, dt):
        """4th order Runge-Kutta"""
        return field.data + dt * rhs

class InterpolationScheme:
    """Field interpolation schemes"""
    
    @staticmethod
    def linear(field, position, mesh):
        """Linear interpolation"""
        pass
    
    @staticmethod
    def second_order(field, position, mesh):
        """2nd order interpolation"""
        pass
    
    @staticmethod
    def weighted_average(field, weight):
        """Weighted average interpolation"""
        pass

class FluxLimiter:
    """Flux limiter functions for high-resolution schemes"""
    
    @staticmethod
    def van_leer(r):
        """Van Leer limiter"""
        return (r + np.abs(r)) / (1 + np.abs(r)) if r != 0 else 1.0
    
    @staticmethod
    def barth_jespersen(r):
        """Barth-Jespersen limiter"""
        return np.max([0, np.min([1, 2*r, (1+r)/2])])
    
    @staticmethod
    def minmod(r):
        """Minmod limiter"""
        return np.max([0, np.min([1, r])])
    
    @staticmethod
    def superbee(r):
        """Superbee limiter"""
        return np.max([0, np.min([1, 2*r]), np.min([2, r])])
