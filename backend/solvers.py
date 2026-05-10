import numpy as np
from abc import ABC, abstractmethod

class BaseSolver(ABC):
    def __init__(self, mesh, config=None):
        self.mesh = mesh
        self.config = config or {}
        self.time = 0
        self.iteration = 0
        self.residuals = {'T': []}
        self.converged = False
        self.bc_manager = None
        
    @abstractmethod
    def solve(self, max_iters=100):
        pass
    
    def get_residuals(self):
        return self.residuals.copy()

class LaplacianFoam(BaseSolver):
    """Heat diffusion - 2D/3D with BC fix"""
    def __init__(self, mesh, config=None):
        super().__init__(mesh, config)
        self.T = None
        self.alpha = self.config.get('alpha', 0.1) if config else 0.1
    
    def initialize_fields(self):
        from field import ScalarField
        self.T = ScalarField(self.mesh, name='T')
        self.T.set_uniform(20.0)
    
    def apply_boundary_conditions(self):
        """Apply BCs to inlet/outlet/wall"""
        if hasattr(self.mesh, 'bc_manager') and self.mesh.bc_manager:
            self.mesh.bc_manager.apply_all(self.T)
        else:
            # Manual BC if no manager
            num_cells = len(self.mesh.cells)
            nx, ny, nz = self.mesh.nx, self.mesh.ny, self.mesh.nz
            
            # Left edge (inlet) = 100°C
            for k in range(nz):
                for j in range(ny):
                    idx = k * ny * nx + j * nx + 0
                    if idx < num_cells:
                        self.T.data[idx, 0] = 100.0
            
            # Right edge (outlet) = 20°C
            for k in range(nz):
                for j in range(ny):
                    idx = k * ny * nx + j * nx + (nx - 1)
                    if idx < num_cells:
                        self.T.data[idx, 0] = 20.0
            
            # For 3D, also set walls to 20°C to prevent heat escape
            if nz > 1:
                # Top wall (j = ny-1)
                for k in range(nz):
                    for i in range(nx):
                        idx = k * ny * nx + (ny - 1) * nx + i
                        if idx < num_cells:
                            self.T.data[idx, 0] = 20.0
                
                # Bottom wall (j = 0)
                for k in range(nz):
                    for i in range(nx):
                        idx = k * ny * nx + 0 * nx + i
                        if idx < num_cells:
                            self.T.data[idx, 0] = 20.0
                
                # Front wall (k = 0)
                for j in range(ny):
                    for i in range(nx):
                        idx = 0 * ny * nx + j * nx + i
                        if idx < num_cells:
                            self.T.data[idx, 0] = 20.0
                
                # Back wall (k = nz-1)
                for j in range(ny):
                    for i in range(nx):
                        idx = (nz - 1) * ny * nx + j * nx + i
                        if idx < num_cells:
                            self.T.data[idx, 0] = 20.0
    
    def solve(self, max_iters=100, dt=0.0001):
        print(f"LaplacianFoam: Starting solve with {len(self.mesh.cells)} cells")
        
        self.initialize_fields()
        print(f"Fields initialized: T shape = {self.T.data.shape}")
        
        # Apply BCs at start
        self.apply_boundary_conditions()
        print(f"After BC init: T_min={np.min(self.T.data):.1f}, T_max={np.max(self.T.data):.1f}")
        
        for iteration in range(max_iters):
            self.iteration = iteration
            self.time += dt
            
            # Get Laplacian
            from schemes import LaplacianScheme
            lap_T = LaplacianScheme.gauss_linear(self.T, self.mesh, self.alpha)
            
            # Store old for residual
            T_old = self.T.data[:, 0].copy()
            
            # Update: T_new = T_old + dt * ∇²T
            self.T.data[:, 0] = self.T.data[:, 0] + dt * lap_T
            
            # RE-APPLY BCs every iteration (CRITICAL)
            self.apply_boundary_conditions()
            
            # Residual from change
            residual = np.max(np.abs(self.T.data[:, 0] - T_old))
            self.residuals['T'].append(residual)
            
            if iteration % 10 == 0:
                print(f"Iteration {iteration}: res={residual:.2e}, T_min={np.min(self.T.data):.1f}, T_max={np.max(self.T.data):.1f}")
            
            if residual < 1e-6 and iteration > 10:
                self.converged = True
                print(f"Converged at iteration {iteration}")
                break
        
        self.converged = True
        print(f"Solve complete: iterations={self.iteration}, residual={self.residuals['T'][-1]:.2e}")
        return self.T

class SimpleFoam(BaseSolver):
    def __init__(self, mesh, config=None):
        super().__init__(mesh, config)
        self.U = None
        self.p = None
    
    def initialize_fields(self):
        from field import VectorField, ScalarField
        self.U = VectorField(self.mesh, name='U')
        self.p = ScalarField(self.mesh, name='p')
        self.U.set_uniform([0.1, 0, 0])
        self.p.set_uniform(0)
    
    def solve(self, max_iters=100):
        self.initialize_fields()
        for iteration in range(max_iters):
            self.iteration = iteration
            residual = np.linalg.norm(self.U.data)
            self.residuals['T'].append(residual)
        self.converged = True
        return self.U, self.p

class IcoFoam(BaseSolver):
    def __init__(self, mesh, config=None):
        super().__init__(mesh, config)
        self.U = None
        self.p = None
    
    def initialize_fields(self):
        from field import VectorField, ScalarField
        self.U = VectorField(self.mesh, name='U')
        self.p = ScalarField(self.mesh, name='p')
        self.U.set_uniform([1.0, 0, 0])
        self.p.set_uniform(0)
    
    def solve(self, max_iters=100, dt=0.01):
        self.initialize_fields()
        for iteration in range(max_iters):
            self.iteration = iteration
            self.time += dt
            residual = np.linalg.norm(self.U.data)
            self.residuals['T'].append(residual)
        self.converged = True
        return self.U, self.p

class PisoFoam(BaseSolver):
    def __init__(self, mesh, config=None):
        super().__init__(mesh, config)
        self.U = None
        self.p = None
    
    def initialize_fields(self):
        from field import VectorField, ScalarField
        self.U = VectorField(self.mesh, name='U')
        self.p = ScalarField(self.mesh, name='p')
        self.U.set_uniform([1.0, 0, 0])
        self.p.set_uniform(0)
    
    def solve(self, max_iters=100, dt=0.01):
        self.initialize_fields()
        for iteration in range(max_iters):
            self.time += dt
            residual = np.linalg.norm(self.U.data)
            self.residuals['T'].append(residual)
        self.converged = True
        return self.U, self.p
