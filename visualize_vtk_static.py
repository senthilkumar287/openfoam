import pyvista as pv
import matplotlib.pyplot as plt
import os

# Load the VTK file
vtk_file = os.path.join(os.path.dirname(__file__), 'backend', 'exports', 'test.vtk')
mesh = pv.read(vtk_file)

# Create a static image instead of interactive window
p = pv.Plotter(off_screen=True)  # off_screen mode = no window, just image
p.add_mesh(mesh, scalars='T', cmap='coolwarm', show_edges=False)
p.add_scalar_bar(title='Temperature (K)')
p.view_isometric()

# Save as PNG instead
output_file = os.path.join(os.path.dirname(__file__), 'backend', 'exports', 'visualization.png')
p.screenshot(output_file)
print(f"✓ Visualization saved to: {output_file}")
p.close()
