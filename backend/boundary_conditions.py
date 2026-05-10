import numpy as np
from abc import ABC, abstractmethod

class BoundaryCondition(ABC):
    """Base BC class"""
    def __init__(self, name, patch_type):
        self.name = name
        self.patch_type = patch_type
    
    @abstractmethod
    def apply(self, field, mesh, boundary_patch):
        pass
    
    def get_value(self):
        return {}

class DirichletBC(BoundaryCondition):
    """Fixed value boundary condition"""
    def __init__(self, name, value):
        super().__init__(name, 'dirichlet')
        self.value = value
    
    def apply(self, field, mesh, boundary_patch):
        """Set field to fixed value at boundary"""
        cells = boundary_patch.get('cells', [])
        field.data[cells, :] = self.value
    
    def get_value(self):
        return {'type': 'dirichlet', 'value': self.value}

class NeumannBC(BoundaryCondition):
    """Fixed gradient boundary condition"""
    def __init__(self, name, gradient):
        super().__init__(name, 'neumann')
        self.gradient = gradient
    
    def apply(self, field, mesh, boundary_patch):
        """Apply gradient BC"""
        cells = boundary_patch.get('cells', [])
        field.data[cells, :] = field.data[max(0, cells[0]-1), :] + self.gradient * mesh.dx

class RobinBC(BoundaryCondition):
    """Mixed boundary condition: aφ + b(∂φ/∂n) = c"""
    def __init__(self, name, a, b, c):
        super().__init__(name, 'robin')
        self.a = a
        self.b = b
        self.c = c
    
    def apply(self, field, mesh, boundary_patch):
        """Apply mixed BC"""
        cells = boundary_patch.get('cells', [])
        field.data[cells, :] = (self.c - self.b * self.gradient) / self.a

class PeriodicBC(BoundaryCondition):
    """Periodic boundary condition"""
    def __init__(self, name, patch1, patch2):
        super().__init__(name, 'periodic')
        self.patch1 = patch1
        self.patch2 = patch2
    
    def apply(self, field, mesh, boundary_patch):
        """Apply periodic BC between two patches"""
        cells1 = boundary_patch.get(self.patch1, {}).get('cells', [])
        cells2 = boundary_patch.get(self.patch2, {}).get('cells', [])
        if len(cells1) == len(cells2):
            field.data[cells2, :] = field.data[cells1, :]

class CyclicBC(BoundaryCondition):
    """Cyclic/rotational boundary condition"""
    def __init__(self, name, angle=None):
        super().__init__(name, 'cyclic')
        self.angle = angle
    
    def apply(self, field, mesh, boundary_patch):
        """Apply cyclic BC"""
        pass

class SymmetryBC(BoundaryCondition):
    """Symmetry plane"""
    def __init__(self, name):
        super().__init__(name, 'symmetry')
    
    def apply(self, field, mesh, boundary_patch):
        """Mirror field across symmetry plane"""
        cells = boundary_patch.get('cells', [])
        if len(cells) > 0:
            field.data[cells, :] = field.data[cells[0], :]

class WallBC(BoundaryCondition):
    """Wall boundary condition"""
    def __init__(self, name, slip=False):
        super().__init__(name, 'wall')
        self.slip = slip
    
    def apply(self, field, mesh, boundary_patch):
        """No-slip or slip wall"""
        cells = boundary_patch.get('cells', [])
        if not self.slip:
            field.data[cells, :] = 0  # No-slip: U = 0
        else:
            field.data[cells, 2] = 0  # Slip: only normal component = 0

class InletBC(BoundaryCondition):
    """Inlet boundary condition"""
    def __init__(self, name, velocity=None, profile=None):
        super().__init__(name, 'inlet')
        self.velocity = velocity
        self.profile = profile
    
    def apply(self, field, mesh, boundary_patch):
        """Apply inlet BC with optional profile"""
        cells = boundary_patch.get('cells', [])
        if self.velocity:
            if isinstance(self.velocity, (int, float)):
                field.data[cells, 0] = self.velocity
            elif isinstance(self.velocity, (list, np.ndarray)):
                field.data[cells, :] = self.velocity
    
    def set_profile(self, profile_func):
        """Set velocity profile function"""
        self.profile = profile_func

class OutletBC(BoundaryCondition):
    """Outlet boundary condition"""
    def __init__(self, name, pressure=None, zero_gradient=False):
        super().__init__(name, 'outlet')
        self.pressure = pressure
        self.zero_gradient = zero_gradient
    
    def apply(self, field, mesh, boundary_patch):
        """Apply outlet BC"""
        if self.zero_gradient:
            cells = boundary_patch.get('cells', [])
            if len(cells) > 0 and len(cells) < len(field.data):
                field.data[cells, :] = field.data[cells[0]-1, :]

class TimeVaryingBC(BoundaryCondition):
    """Time-varying boundary condition"""
    def __init__(self, name, func):
        super().__init__(name, 'time_varying')
        self.func = func
    
    def apply(self, field, mesh, boundary_patch, time=0):
        """Apply time-dependent BC"""
        cells = boundary_patch.get('cells', [])
        value = self.func(time)
        field.data[cells, :] = value

class BoundaryManager:
    """Manage all boundary conditions"""
    def __init__(self, mesh):
        self.mesh = mesh
        self.bcs = {}
    
    def add_bc(self, patch_name, bc):
        """Add boundary condition"""
        self.bcs[patch_name] = bc
    
    def apply_all(self, field):
        """Apply all BCs to field"""
        for patch_name, bc in self.bcs.items():
            if patch_name in self.mesh.boundary_patches:
                boundary_patch = self.mesh.boundary_patches[patch_name]
                bc.apply(field, self.mesh, boundary_patch)
    
    def get_bc(self, patch_name):
        """Get BC for patch"""
        return self.bcs.get(patch_name)
    
    def list_bcs(self):
        """List all BCs"""
        return {name: bc.get_value() for name, bc in self.bcs.items()}
