import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from mesh import Mesh
from field import ScalarField
from postprocessing import DataExport

# Create a simple test mesh and field
mesh = Mesh(nx=5, ny=5, nz=3)
field = ScalarField(mesh, name='T')

# Set some test data with a gradient
for i, cell in enumerate(mesh.cells):
    x, y, z = cell['center']
    # Create a temperature gradient from left to right
    temp = 300 + 50 * x  # 300K to 350K
    field.data[i, 0] = temp

# Export to VTK
export_path = os.path.join(os.path.dirname(__file__), 'backend', 'exports', 'test.vtk')
DataExport.to_vtk(field, export_path, mesh)
print(f"Test VTK file created: {export_path}")