import numpy as np
import json
import csv
import os


class DataExport:
    """Export data to various formats"""

    @staticmethod
    def to_vtk(field, filename, mesh):
        """Export to VTK format (for ParaView) - FIXED: proper structured grid"""
        nx, ny, nz = mesh.nx, mesh.ny, mesh.nz

        # Number of points (corners of cells) = (nx)*(ny)*(nz) for cell-center data
        # We write a STRUCTURED_POINTS grid which is simplest and correct for regular meshes
        with open(filename, 'w') as f:
            f.write("# vtk DataFile Version 3.0\n")
            f.write("OpenFOAM Export\n")
            f.write("ASCII\n")
            f.write("DATASET STRUCTURED_POINTS\n")
            f.write(f"DIMENSIONS {nx} {ny} {nz}\n")
            f.write(f"ORIGIN 0.0 0.0 0.0\n")
            f.write(f"SPACING {mesh.dx:.6f} {mesh.dy:.6f} {mesh.dz:.6f}\n")

            num_cells = nx * ny * nz
            f.write(f"POINT_DATA {num_cells}\n")
            f.write(f"SCALARS {field.name} float 1\n")
            f.write("LOOKUP_TABLE default\n")

            data_flat = field.data[:, 0]
            for value in data_flat:
                f.write(f"{value:.6f}\n")

    @staticmethod
    def to_csv(field, filename):
        """Export to CSV - FIXED VERSION"""
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)

                # Header
                if field.data.shape[1] == 1:
                    writer.writerow([field.name])
                else:
                    writer.writerow([f'{field.name}_{i}' for i in range(field.data.shape[1])])

                # Data
                for row in field.data:
                    writer.writerow(row)

            return True
        except Exception as e:
            print(f"CSV export error: {e}")
            return False

    @staticmethod
    def to_json(data, filename):
        """Export to JSON"""
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            print(f"JSON export error: {e}")
            return False

    @staticmethod
    def to_hdf5(field, filename):
        """Export to HDF5 (binary)"""
        try:
            import h5py
            with h5py.File(filename, 'w') as f:
                f.create_dataset('field_data', data=field.data)
            return True
        except ImportError:
            print("HDF5 not available")
            return False
        except Exception as e:
            print(f"HDF5 export error: {e}")
            return False


class Visualization:
    """Helper for visualization"""

    @staticmethod
    def create_heatmap_data(field, mesh):
        """Create heatmap for plotting"""
        try:
            nx, ny = mesh.nx, mesh.ny
            data = field.data[:, 0].reshape(ny, nx)
            return {
                'data': data.tolist(),
                'min': float(np.min(data)),
                'max': float(np.max(data)),
                'mean': float(np.mean(data))
            }
        except Exception as e:
            print(f"Heatmap error: {e}")
            return {'data': [], 'min': 0, 'max': 1}

    @staticmethod
    def create_heatmap_data_3d(field, mesh):
        """Create 3D heatmap data shaped as [nz, ny, nx]"""
        try:
            nx, ny, nz = mesh.nx, mesh.ny, mesh.nz
            data = field.data[:, 0].reshape(nz, ny, nx)
            return {
                'data': data.tolist(),
                'min': float(np.min(data)),
                'max': float(np.max(data)),
                'mean': float(np.mean(data)),
                'shape': [nz, ny, nx]
            }
        except Exception as e:
            print(f"3D Heatmap error: {e}")
            return {'data': [], 'min': 0, 'max': 1, 'shape': [1, 1, 1]}

    @staticmethod
    def create_vector_plot(vector_field, mesh, skip=1):
        """Create vector field plot data"""
        cells = mesh.cells
        vectors = []

        try:
            for i in range(0, len(cells), skip):
                x, y, z = cells[i]['center']
                u, v, w = vector_field.data[i]
                vectors.append({
                    'x': float(x),
                    'y': float(y),
                    'u': float(u),
                    'v': float(v)
                })
        except Exception as e:
            print(f"Vector plot error: {e}")

        return vectors

    @staticmethod
    def create_contour_plot(field, mesh, num_levels=10):
        """Create contour plot data"""
        try:
            nx, ny = mesh.nx, mesh.ny
            data = field.data[:, 0].reshape(ny, nx)

            levels = np.linspace(np.min(data), np.max(data), num_levels)
            return {
                'data': data.tolist(),
                'levels': levels.tolist()
            }
        except Exception as e:
            print(f"Contour plot error: {e}")
            return {'data': [], 'levels': []}


class FieldOperations:
    """Post-processing field operations"""

    @staticmethod
    def gradient(field, mesh):
        """Compute gradient of field"""
        grad = np.zeros((len(mesh.cells), 3))
        for i in range(len(mesh.cells) - 1):
            grad[i, 0] = (field.data[i+1, 0] - field.data[i, 0]) / mesh.dx
        return grad

    @staticmethod
    def divergence(vector_field, mesh):
        """Compute divergence"""
        div = np.zeros(len(mesh.cells))
        for i in range(len(mesh.cells) - 1):
            div[i] = (vector_field.data[i+1, 0] - vector_field.data[i, 0]) / mesh.dx
        return div

    @staticmethod
    def magnitude(vector_field):
        """Magnitude of vector field"""
        return np.linalg.norm(vector_field.data, axis=1)


class Sampling:
    """Extract data along lines, planes, etc."""

    @staticmethod
    def sample_line(field, start, end, num_points=100):
        """Sample field along a line"""
        points = np.linspace(start, end, num_points)
        values = np.zeros(num_points)
        return {'points': points, 'values': values}

    @staticmethod
    def probe_point(field, point_index):
        """Extract field value at point"""
        return field.data[point_index].copy()


class Averaging:
    """Time and ensemble averaging"""

    def __init__(self, mesh):
        self.mesh = mesh
        self.field_sum = {}
        self.count = 0

    def accumulate(self, field_name, field):
        """Accumulate field for averaging"""
        if field_name not in self.field_sum:
            self.field_sum[field_name] = np.zeros_like(field.data)
        self.field_sum[field_name] += field.data
        self.count += 1

    def get_average(self, field_name):
        """Get time-averaged field"""
        if field_name in self.field_sum:
            return self.field_sum[field_name] / (self.count + 1e-10)
        return None


class MonitoringProbes:
    """Monitor specific points during simulation"""

    def __init__(self, mesh, point_indices):
        self.mesh = mesh
        self.point_indices = point_indices
        self.history = {idx: [] for idx in point_indices}

    def sample(self, field):
        """Sample field at probe points"""
        for idx in self.point_indices:
            value = field.data[idx, 0] if idx < len(field.data) else 0
            self.history[idx].append(value)

    def get_history(self, idx):
        """Get time history at probe"""
        return self.history.get(idx, [])
