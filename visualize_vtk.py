import pyvista as pv
import numpy as np

# Load the VTK file
import os
vtk_file = os.path.join(os.path.dirname(__file__), 'backend', 'exports', 'test.vtk')
mesh = pv.read(vtk_file)

print(f"Mesh loaded with {mesh.n_points} points and {mesh.n_cells} cells")
print(f"Temperature range: {mesh['T'].min():.2f} - {mesh['T'].max():.2f}")

# Create a plotter
plotter = pv.Plotter()

# Add the mesh with temperature data
plotter.add_mesh(mesh, scalars='T', cmap='coolwarm', show_edges=False)

# Add a scalar bar
plotter.add_scalar_bar(title='Temperature (K)')

# Set camera position for better view
plotter.view_isometric()

# Show the plot
plotter.show()