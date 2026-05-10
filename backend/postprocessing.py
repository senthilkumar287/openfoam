import numpy as np
import json
import csv
import os

class DataExport:
    """Export data to various formats - FIXED CSV SUPPORT"""
    
    @staticmethod
    def to_vtk(field, filename, mesh):
        """Export to VTK format (for ParaView)"""
        with open(filename, 'w') as f:
            # VTK header
            f.write("# vtk DataFile Version 3.0\n")
            f.write("OpenFOAM Export\n")
            f.write("ASCII\n")
            f.write("DATASET UNSTRUCTURED_GRID\n")
            
            # Points
            f.write(f"POINTS {len(mesh.cells)} float\n")
            for cell in mesh.cells:
                x, y, z = cell['center']
                f.write(f"{x:.6f} {y:.6f} {z:.6f}\n")
            
            # Cells (assuming hexahedral cells for structured mesh)
            f.write(f"CELLS {len(mesh.cells)} {len(mesh.cells) * 9}\n")  # 8 vertices + 1 for count
            vertex_id = 0
            for cell in mesh.cells:
                f.write(f"8 {vertex_id} {vertex_id+1} {vertex_id+2} {vertex_id+3} {vertex_id+4} {vertex_id+5} {vertex_id+6} {vertex_id+7}\n")
                vertex_id += 8
            
            # Cell types (hexahedral = 12)
            f.write(f"CELL_TYPES {len(mesh.cells)}\n")
            for _ in mesh.cells:
                f.write("12\n")
            
            # Point data
            f.write(f"POINT_DATA {len(mesh.cells)}\n")
            f.write(f"SCALARS {field.name} float 1\n")
            f.write("LOOKUP_TABLE default\n")
            for value in field.data:
                f.write(f"{value[0]:.6f}\n")
    
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
    """Helper for visualization - IMPROVED"""
    
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