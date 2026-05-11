from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import numpy as np
import json
import os
import sys

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)

# Global state
current_mesh = None
current_solver = None
current_case = {}

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'app': 'OpenFOAM Clone',
        'version': '1.0',
        'status': 'running',
        'endpoints': [
            '/api/mesh/create', '/api/mesh/create3d', '/api/mesh/import', '/api/solver/list', '/api/solver/info', '/api/solver/create',
            '/api/bc/set', '/api/simulate/run', '/api/simulate/status', '/api/results/heatmap', '/api/results/heatmap3d', '/api/results/export',
            '/api/case/save', '/api/case/load'
        ]
    })

# ADD these routes to app.py for 3D support

@app.route('/api/mesh/create3d', methods=['POST'])
def create_mesh_3d():
    global current_mesh
    data = request.json
    nx, ny, nz = data.get('nx', 50), data.get('ny', 50), data.get('nz', 10)
    domain = tuple(data.get('domain', [1.0, 1.0, 0.2]))
    
    try:
        from mesh import Mesh
        current_mesh = Mesh(nx, ny, nz, domain)
        return jsonify({
            'status': 'success',
            'mesh': current_mesh.to_dict(),
            'message': f'3D Mesh created: {nx}x{ny}x{nz} = {len(current_mesh.cells)} cells'
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

# ========== MESH ROUTES ==========
@app.route('/api/mesh/create', methods=['POST'])
def create_mesh():
    global current_mesh
    data = request.json
    nx, ny, nz = data.get('nx', 50), data.get('ny', 50), data.get('nz', 1)
    domain = tuple(data.get('domain', [1.0, 1.0, 1.0]))
    mesh_type = data.get('mesh_type', 'structured')
    
    try:
        from mesh import Mesh
        current_mesh = Mesh(nx, ny, nz, domain)
        current_mesh.mesh_type = mesh_type
        return jsonify({
            'status': 'success',
            'mesh': current_mesh.to_dict(),
            'message': f'Mesh created: {nx}x{ny}x{nz}'
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/mesh/info', methods=['GET'])
def mesh_info():
    if current_mesh is None:
        return jsonify({'status': 'error', 'message': 'No mesh created'}), 400
    
    return jsonify({
        'status': 'success',
        'mesh': current_mesh.to_dict()
    }), 200

@app.route('/api/mesh/import', methods=['POST'])
def import_mesh():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No mesh file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No mesh file selected'}), 400

    return jsonify({
        'status': 'error',
        'message': 'Mesh import is not supported yet. Use Create Mesh instead.'
    }), 400

# ========== SOLVER ROUTES ==========
@app.route('/api/solver/list', methods=['GET'])
def list_solvers():
    solvers = {
        'Supported': ['simpleFoam', 'pisoFoam', 'icoFoam', 'laplacianFoam']
    }
    return jsonify({
        'status': 'success',
        'solvers': solvers,
        'total': sum(len(v) for v in solvers.values())
    }), 200

@app.route('/api/solver/info', methods=['GET'])
def solver_info():
    if current_solver is None:
        return jsonify({'status': 'error', 'message': 'No solver created'}), 400

    return jsonify({
        'status': 'success',
        'solver': current_case.get('solver'),
        'config': current_case.get('config', {}),
        'class': current_solver.__class__.__name__
    }), 200

@app.route('/api/solver/create', methods=['POST'])
def create_solver():
    global current_solver, current_mesh
    
    if current_mesh is None:
        return jsonify({'status': 'error', 'message': 'Create mesh first'}), 400
    
    data = request.json
    solver_type = data.get('type', 'simpleFoam')
    config = data.get('config', {})
    
    try:
        if solver_type == 'simpleFoam':
            from solvers import SimpleFoam
            current_solver = SimpleFoam(current_mesh, config)
        elif solver_type == 'laplacianFoam':
            from solvers import LaplacianFoam
            current_solver = LaplacianFoam(current_mesh, config)
        elif solver_type == 'icoFoam':
            from solvers import IcoFoam
            current_solver = IcoFoam(current_mesh, config)
        elif solver_type == 'pisoFoam':
            from solvers import PisoFoam
            current_solver = PisoFoam(current_mesh, config)
        else:
            return jsonify({'status': 'error', 'message': f'Unknown solver: {solver_type}'}), 400
        
        current_case['solver'] = solver_type
        current_case['config'] = config
        
        return jsonify({
            'status': 'success',
            'solver': solver_type,
            'message': f'{solver_type} created'
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/bc/set', methods=['POST'])
def set_boundary_condition():
    if current_mesh is None:
        return jsonify({'status': 'error', 'message': 'No mesh'}), 400
    
    data = request.json
    patch_name = data.get('patch', 'wall')
    bc_type = data.get('type', 'dirichlet')
    bc_value = data.get('value', 0.0)
    
    try:
        from boundary_conditions import (
            DirichletBC, NeumannBC, WallBC, InletBC, OutletBC,
            BoundaryManager
        )
        
        # Create BC manager if it doesn't exist
        if not hasattr(current_mesh, 'bc_manager') or current_mesh.bc_manager is None:
            current_mesh.bc_manager = BoundaryManager(current_mesh)
        
        if bc_type == 'dirichlet':
            bc = DirichletBC(patch_name, bc_value)
        elif bc_type == 'neumann':
            bc = NeumannBC(patch_name, bc_value)
        elif bc_type == 'wall':
            bc = WallBC(patch_name)
        elif bc_type == 'inlet':
            bc = InletBC(patch_name, bc_value)
        elif bc_type == 'outlet':
            bc = OutletBC(patch_name)
        else:
            return jsonify({'status': 'error', 'message': f'Unknown BC type: {bc_type}'}), 400
        
        # Add BC to manager
        current_mesh.bc_manager.add_bc(patch_name, bc)
        
        if 'boundary_conditions' not in current_case:
            current_case['boundary_conditions'] = {}
        current_case['boundary_conditions'][patch_name] = {'type': bc_type, 'value': bc_value}
        
        return jsonify({
            'status': 'success',
            'patch': patch_name,
            'type': bc_type,
            'message': f'BC set on {patch_name}'
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/bc/list', methods=['GET'])
def list_bcs():
    if current_mesh is None or not hasattr(current_mesh, 'bc_manager'):
        return jsonify({'boundary_conditions': {}}), 200
    
    bcs = current_mesh.bc_manager.list_bcs()
    return jsonify({'status': 'success', 'boundary_conditions': bcs}), 200

# ========== SIMULATION ROUTES ==========
@app.route('/api/simulate/run', methods=['POST'])
def run_simulation():

    global current_solver, current_mesh

    if current_solver is None:
        return jsonify({
            'status': 'error',
            'message': 'Create solver first'
        }), 400

    data = request.json
    max_iters = data.get('max_iters', 100)
    dt = data.get('dt', 0.01)
    tolerance = data.get('tolerance', 1e-5)
    sample_interval = data.get('sample_interval', 10)

    try:

        # Attach boundary manager to solver
        if current_mesh and hasattr(current_mesh, 'bc_manager'):
            current_solver.bc_manager = current_mesh.bc_manager

        # Run solver
        if hasattr(current_solver, 'solve'):
            current_solver.tolerance = tolerance
            current_solver.sample_interval = sample_interval

            solver_name = current_solver.__class__.__name__
            if solver_name == 'SimpleFoam':
                result = current_solver.solve(max_iters)
            elif solver_name == 'LaplacianFoam':
                # Let solver pick stable dt automatically (dt=None)
                result = current_solver.solve(max_iters, dt=None)
            else:
                result = current_solver.solve(max_iters, dt=None)

            residuals = current_solver.get_residuals()

            return jsonify({
                'status': 'success',
                'converged': current_solver.converged,
                'iterations': current_solver.iteration,
                'residuals': {
                    k: v[-5:] if v else []
                    for k, v in residuals.items()
                },
                'message': 'Simulation completed'
            }), 200

        else:
            return jsonify({
                'status': 'error',
                'message': 'Solver not ready'
            }), 400

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

@app.route('/api/simulate/status', methods=['GET'])
def simulation_status():
    if current_solver is None:
        return jsonify({'status': 'no_solver'}), 200

    residuals = current_solver.get_residuals()
    # Return last residual values for monitor display
    last_residuals = {k: v[-1] if v else None for k, v in residuals.items()}

    return jsonify({
        'status': 'running' if not current_solver.converged else 'converged',
        'iterations': current_solver.iteration,
        'converged': current_solver.converged,
        'time': current_solver.time,
        'residuals': last_residuals
    }), 200

# ========== RESULTS ROUTES ==========
@app.route('/api/results/field/<field_name>', methods=['GET'])
def get_field(field_name):
    if current_solver is None:
        return jsonify({'status': 'error', 'message': 'No solver'}), 400
    
    try:
        field = getattr(current_solver, field_name, None)
        if field is None:
            return jsonify({'status': 'error', 'message': f'Field {field_name} not found'}), 404
        
        return jsonify({
            'status': 'success',
            'field': field_name,
            'data': field.data.tolist() if hasattr(field, 'data') else str(field),
            'metadata': field.to_dict() if hasattr(field, 'to_dict') else {}
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

def _get_scalar_field(solver, field_name):
    """Helper: get scalar numpy array from solver field, with NaN safety."""
    field = getattr(solver, field_name, None)
    if field is None or not hasattr(field, 'data') or field.data is None or field.data.size == 0:
        for fname in ['T', 'p', 'U']:
            field = getattr(solver, fname, None)
            if field is not None and hasattr(field, 'data') and field.data is not None and field.data.size > 0:
                break
    if field is None or not hasattr(field, 'data') or field.data is None or field.data.size == 0:
        return None, 'No field data available'

    raw = field.data
    if raw.shape[1] > 1:
        scalar = np.linalg.norm(raw, axis=1)
    else:
        scalar = raw[:, 0].copy()

    # Replace NaN/Inf with interpolated or zero — critical fix
    bad = ~np.isfinite(scalar)
    if bad.all():
        return None, 'All field values are NaN/Inf — solver may have diverged'
    if bad.any():
        scalar[bad] = np.interp(np.flatnonzero(bad), np.flatnonzero(~bad), scalar[~bad])

    return scalar, None


@app.route('/api/results/heatmap', methods=['GET'])
def get_heatmap():
    if current_solver is None or current_mesh is None:
        return jsonify({'status': 'error', 'message': 'No simulation'}), 400

    try:
        field_name = request.args.get('field', 'T')
        scalar, err = _get_scalar_field(current_solver, field_name)
        if scalar is None:
            return jsonify({'status': 'error', 'message': err}), 400

        nx, ny, nz = current_mesh.nx, current_mesh.ny, current_mesh.nz
        is_3d = nz > 1

        # Always return 3D shape [nz, ny, nx] — frontend handles both cases
        data = scalar.reshape((nz, ny, nx)).tolist()

        vmin, vmax = float(scalar.min()), float(scalar.max())
        heatmap = {
            'data': data,
            'min': vmin,
            'max': vmax,
            'shape': [nz, ny, nx],
            'is_3d': is_3d,
            'field': field_name
        }
        return jsonify({'status': 'success', 'heatmap': heatmap}), 200
    except Exception as e:
        import traceback
        return jsonify({'status': 'error', 'message': str(e), 'trace': traceback.format_exc()}), 400


@app.route('/api/results/heatmap3d', methods=['GET'])
def get_heatmap3d():
    """Dedicated endpoint for 3D heatmap data — always returns [nz][ny][nx] shape."""
    if current_solver is None or current_mesh is None:
        return jsonify({'status': 'error', 'message': 'No simulation'}), 400

    try:
        field_name = request.args.get('field', 'T')
        scalar, err = _get_scalar_field(current_solver, field_name)
        if scalar is None:
            return jsonify({'status': 'error', 'message': err}), 400

        nx, ny, nz = current_mesh.nx, current_mesh.ny, current_mesh.nz
        is_3d = nz > 1
        data = scalar.reshape((nz, ny, nx)).tolist()

        heatmap = {
            'data': data,
            'min': float(scalar.min()),
            'max': float(scalar.max()),
            'shape': [nz, ny, nx],
            'is_3d': is_3d,
            'field': field_name
        }
        return jsonify({'status': 'success', 'heatmap': heatmap}), 200
    except Exception as e:
        import traceback
        return jsonify({'status': 'error', 'message': str(e), 'trace': traceback.format_exc()}), 400

@app.route('/api/results/export', methods=['POST'])
def export_results():
    global current_solver, current_mesh
    
    if current_solver is None:
        return jsonify({'status': 'error', 'message': 'No results to export'}), 400
    
    data = request.json
    fmt = data.get('format', 'json').lower()
    
    if fmt not in ['json', 'csv', 'vtk']:
        return jsonify({'status': 'error', 'message': f'Format {fmt} not supported. Use: json, csv, vtk'}), 400
    
    try:
        from postprocessing import DataExport
        
        os.makedirs('exports', exist_ok=True)
        filename = os.path.join('exports', f'export.{fmt}')
        
        if fmt == 'json':
            export_data = {
                'solver': current_solver.__class__.__name__,
                'converged': current_solver.converged,
                'iterations': current_solver.iteration,
                'residuals': current_solver.get_residuals()
            }
            
            # Add field data
            if hasattr(current_solver, 'T'):
                field_T = current_solver.T
                export_data['temperature'] = {
                    'min': float(np.min(field_T.data)),
                    'max': float(np.max(field_T.data)),
                    'mean': float(np.mean(field_T.data)),
                    'data_shape': list(field_T.data.shape)
                }
            
            DataExport.to_json(export_data, filename)
            
        elif fmt == 'csv':
            # Export temperature field as CSV
            if hasattr(current_solver, 'T'):
                success = DataExport.to_csv(current_solver.T, filename)
                if not success:
                    return jsonify({'status': 'error', 'message': 'CSV export failed'}), 400
            else:
                return jsonify({'status': 'error', 'message': 'No temperature field to export'}), 400
        
        elif fmt == 'vtk':
            if hasattr(current_solver, 'T') and current_mesh:
                DataExport.to_vtk(current_solver.T, filename, current_mesh)
            else:
                return jsonify({'status': 'error', 'message': 'Missing field or mesh for VTK'}), 400
        
        return jsonify({
            'status': 'success',
            'format': fmt,
            'file': filename,
            'message': f'Exported to {fmt.upper()}'
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Export failed: {str(e)}'}), 400

@app.route('/api/case/save', methods=['POST'])
def save_case():

    data = request.json
    case_name = data.get('name', 'case1')

    try:

        case_data = {
            'name': case_name,
            'mesh': current_mesh.to_dict() if current_mesh else None,
            'solver': current_case.get('solver'),
            'config': current_case.get('config'),
            'bcs': current_case.get('boundary_conditions', {})
        }

        os.makedirs('cases', exist_ok=True)

        filename = os.path.join('cases', f'{case_name}.json')

        with open(filename, 'w') as f:
            json.dump(case_data, f, indent=2)

        return jsonify({
            'status': 'success',
            'case': case_name,
            'file': filename
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

@app.route('/api/case/load', methods=['POST'])
def load_case():
    global current_mesh, current_solver, current_case

    data = request.json
    case_name = data.get('name')
    if not case_name:
        return jsonify({'status': 'error', 'message': 'Case name required'}), 400

    filename = os.path.join('cases', f'{case_name}.json')
    if not os.path.exists(filename):
        return jsonify({'status': 'error', 'message': f'Case {case_name} not found'}), 404

    try:
        with open(filename, 'r') as f:
            case_data = json.load(f)

        from mesh import Mesh
        from boundary_conditions import (
            DirichletBC, NeumannBC, WallBC, InletBC, OutletBC,
            BoundaryManager
        )

        mesh_data = case_data.get('mesh')
        if mesh_data is None:
            return jsonify({'status': 'error', 'message': 'Saved case has no mesh data'}), 400

        current_mesh = Mesh(mesh_data.get('nx', 50), mesh_data.get('ny', 50), mesh_data.get('nz', 1), tuple(mesh_data.get('domain', [1.0, 1.0, 1.0])))
        current_mesh.mesh_type = mesh_data.get('mesh_type', 'structured')
        current_case = {
            'solver': case_data.get('solver'),
            'config': case_data.get('config', {}),
            'boundary_conditions': case_data.get('bcs', {})
        }

        solver_type = current_case.get('solver')
        if solver_type:
            data = {'type': solver_type, 'config': current_case.get('config', {})}
            if solver_type == 'simpleFoam':
                from solvers import SimpleFoam
                current_solver = SimpleFoam(current_mesh, current_case.get('config', {}))
            elif solver_type == 'laplacianFoam':
                from solvers import LaplacianFoam
                current_solver = LaplacianFoam(current_mesh, current_case.get('config', {}))
            elif solver_type == 'icoFoam':
                from solvers import IcoFoam
                current_solver = IcoFoam(current_mesh, current_case.get('config', {}))
            elif solver_type == 'pisoFoam':
                from solvers import PisoFoam
                current_solver = PisoFoam(current_mesh, current_case.get('config', {}))
            else:
                current_solver = None

        if current_mesh and hasattr(current_mesh, 'boundary_patches'):
            current_mesh.bc_manager = BoundaryManager(current_mesh)
            for patch_name, bc_data in current_case.get('boundary_conditions', {}).items():
                bc_type = bc_data.get('type')
                bc_value = bc_data.get('value', 0.0)

                if bc_type == 'dirichlet':
                    bc = DirichletBC(patch_name, bc_value)
                elif bc_type == 'neumann':
                    bc = NeumannBC(patch_name, bc_value)
                elif bc_type == 'wall':
                    bc = WallBC(patch_name)
                elif bc_type == 'inlet':
                    bc = InletBC(patch_name, bc_value)
                elif bc_type == 'outlet':
                    bc = OutletBC(patch_name)
                else:
                    continue

                current_mesh.bc_manager.add_bc(patch_name, bc)

        fields = case_data.get('fields', {})
        if current_solver is not None and fields:
            from field import VectorField, ScalarField
            current_solver.U = VectorField(current_mesh, 'U')
            current_solver.U.set_uniform(fields.get('U', [0, 0, 0]))
            current_solver.p = ScalarField(current_mesh, 'p')
            current_solver.p.set_uniform(fields.get('p', 0.0))
            current_solver.T = ScalarField(current_mesh, 'T')
            current_solver.T.set_uniform(fields.get('T', 300))

        return jsonify({
            'status': 'success',
            'case': case_name,
            'message': 'Case loaded successfully'
        }), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


# ========== FIELD ROUTES ==========

@app.route('/api/fields/initialize', methods=['POST'])
def initialize_fields():

    global current_solver, current_mesh

    if current_mesh is None:
        return jsonify({
            'status': 'error',
            'message': 'Create mesh first'
        }), 400

    try:

        data = request.json

        U = data.get('U', [0, 0, 0])
        p = data.get('p', 0.0)
        T = data.get('T', 300)

        from field import VectorField, ScalarField

        velocity = VectorField(current_mesh, "U")
        pressure = ScalarField(current_mesh, "p")
        temperature = ScalarField(current_mesh, "T")

        velocity.set_uniform(U)
        pressure.set_uniform(p)
        temperature.set_uniform(T)

        if current_solver is not None:
            current_solver.U = velocity
            current_solver.p = pressure
            current_solver.T = temperature

        current_case['fields'] = {
            'U': U,
            'p': p,
            'T': T
        }

        return jsonify({
            'status': 'success',
            'message': 'Fields initialized successfully'
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400        

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
