import numpy as np

class Mesh:
    def __init__(self, nx=50, ny=50, nz=1, domain=(1.0, 1.0, 1.0)):
        self.nx, self.ny, self.nz = nx, ny, nz
        self.lx, self.ly, self.lz = domain
        self.dx = self.lx / (nx - 1) if nx > 1 else self.lx
        self.dy = self.ly / (ny - 1) if ny > 1 else self.ly
        self.dz = self.lz / (nz - 1) if nz > 1 else self.lz
        self.cells = self.create_cells()
        self.faces = self.create_faces()
        self.boundary_patches = {}
        self.cell_volumes = self.compute_volumes()
        
    def create_cells(self):
        cells = []
        for k in range(self.nz):
            for j in range(self.ny):
                for i in range(self.nx):
                    x = i * self.dx
                    y = j * self.dy
                    z = k * self.dz
                    cells.append({'center': np.array([x, y, z]), 'id': len(cells)})
        return cells
    
    def create_faces(self):
        faces = {'interior': [], 'boundary': {}}
        for k in range(self.nz):
            for j in range(self.ny):
                for i in range(self.nx - 1):
                    c1 = k * self.ny * self.nx + j * self.nx + i
                    c2 = k * self.ny * self.nx + j * self.nx + (i + 1)
                    faces['interior'].append({'c1': c1, 'c2': c2, 'direction': 'x'})
        return faces
    
    def compute_volumes(self):
        return np.full(len(self.cells), self.dx * self.dy * self.dz)
    
    def add_boundary_patch(self, name, cell_indices, bc_type='wall'):
        self.boundary_patches[name] = {'cells': cell_indices, 'type': bc_type}
        
    def get_cell_center(self, cell_id):
        return self.cells[cell_id]['center'].copy()
    
    def to_dict(self):
        return {
            'nx': self.nx, 'ny': self.ny, 'nz': self.nz,
            'domain': [self.lx, self.ly, self.lz],
            'num_cells': len(self.cells),
            'cell_volumes': self.cell_volumes.tolist()
        }
