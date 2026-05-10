import numpy as np
from typing import Union

class Field:
    """Generic field data structure (scalar or vector)"""
    def __init__(self, mesh, num_components=1, name="field"):
        self.mesh = mesh
        self.num_components = num_components
        self.name = name
        self.data = np.zeros((len(mesh.cells), num_components))
        self.boundary_values = {}
        
    def set_value(self, cell_id, value):
        """Set field value at cell"""
        if self.num_components == 1:
            self.data[cell_id, 0] = value
        else:
            self.data[cell_id, :] = value
    
    def get_value(self, cell_id):
        """Get field value at cell"""
        return self.data[cell_id].copy()
    
    def set_uniform(self, value):
        """Set uniform field"""
        if self.num_components == 1:
            self.data[:, 0] = value
        else:
            self.data[:, :] = value
    
    def set_boundary(self, patch_name, values):
        """Set boundary field values"""
        self.boundary_values[patch_name] = np.array(values)
    
    def get_boundary(self, patch_name):
        """Get boundary values"""
        return self.boundary_values.get(patch_name, np.array([]))
    
    def min(self):
        return np.min(self.data)
    
    def max(self):
        return np.max(self.data)
    
    def mean(self):
        return np.mean(self.data)
    
    def copy(self):
        """Create copy of field"""
        new_field = Field(self.mesh, self.num_components, self.name)
        new_field.data = self.data.copy()
        new_field.boundary_values = {k: v.copy() for k, v in self.boundary_values.items()}
        return new_field
    
    def to_dict(self):
        return {
            'name': self.name,
            'components': self.num_components,
            'min': float(self.min()),
            'max': float(self.max()),
            'mean': float(self.mean()),
            'data_shape': list(self.data.shape)
        }

class VectorField(Field):
    """Vector field (3 components)"""
    def __init__(self, mesh, name="velocity"):
        super().__init__(mesh, num_components=3, name=name)
    
    def set_velocity(self, ux, uy, uz=0):
        """Set velocity components"""
        self.data[:, 0] = ux
        self.data[:, 1] = uy
        self.data[:, 2] = uz if isinstance(uz, np.ndarray) else uz
    
    def get_magnitude(self):
        """Get velocity magnitude"""
        return np.linalg.norm(self.data, axis=1)
    
    def get_vorticity(self):
        """Compute vorticity (placeholder)"""
        pass

class ScalarField(Field):
    """Scalar field (1 component)"""
    def __init__(self, mesh, name="scalar"):
        super().__init__(mesh, num_components=1, name=name)

class FieldOperations:
    """Operations on fields"""
    
    @staticmethod
    def gradient(field, mesh, scheme='gauss'):
        """Compute gradient of field"""
        grad = np.zeros((len(mesh.cells), 3))
        for i, cell in enumerate(mesh.cells):
            cx, cy, cz = cell['center']
            if i < len(mesh.cells) - 1:
                cell_next = mesh.cells[i + 1]
                dcx = cell_next['center'][0] - cx
                if abs(dcx) > 1e-10:
                    grad[i, 0] = (field.data[i+1, 0] - field.data[i, 0]) / dcx
        return grad
    
    @staticmethod
    def divergence(vector_field, mesh):
        """Compute divergence of vector field"""
        div = np.zeros(len(mesh.cells))
        for i in range(len(mesh.cells) - 1):
            dux = (vector_field.data[i+1, 0] - vector_field.data[i, 0]) / mesh.dx
            div[i] = dux
        return div
    
    @staticmethod
    def laplacian(field, mesh, diffusivity=1.0):
        """Compute Laplacian (∇²φ)"""
        lap = np.zeros(len(mesh.cells))
        for i in range(1, len(mesh.cells) - 1):
            d2f = (field.data[i+1, 0] + field.data[i-1, 0] - 2*field.data[i, 0]) / (mesh.dx**2)
            lap[i] = diffusivity * d2f
        return lap
    
    @staticmethod
    def interpolate(field, position, mesh):
        """Interpolate field at arbitrary position (linear)"""
        pass

class FieldIO:
    """Field input/output"""
    
    @staticmethod
    def write_vtk(field, filename):
        """Write field in VTK format"""
        pass
    
    @staticmethod
    def write_csv(field, filename):
        """Write field as CSV"""
        np.savetxt(filename, field.data, delimiter=',')
    
    @staticmethod
    def read_csv(filename, mesh):
        """Read field from CSV"""
        data = np.loadtxt(filename, delimiter=',')
        field = Field(mesh, data.shape[1] if len(data.shape) > 1 else 1)
        field.data = data.reshape(field.data.shape)
        return field
