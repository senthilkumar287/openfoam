import os
import json
import numpy as np
import matplotlib.pyplot as plt
from app import app

OUTPUT_DIR = os.path.abspath(os.path.dirname(__file__))
IMAGE_PATH = os.path.join(OUTPUT_DIR, 'test_output_heatmap.png')
REPORT_PATH = os.path.join(OUTPUT_DIR, 'test_case_report.md')
RESULTS_PATH = os.path.join(OUTPUT_DIR, 'test_case_results.json')

client = app.test_client()


def api_post(path, payload):
    resp = client.post(path, json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"{path} failed: {resp.status_code} {resp.json}")
    return resp.json


def api_get(path, params=None):
    if params:
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        path = f'{path}?{query}'
    resp = client.get(path)
    if resp.status_code != 200:
        raise RuntimeError(f"{path} failed: {resp.status_code} {resp.json}")
    return resp.json


def main():
    results = {}

    # 1) Create mesh
    mesh_payload = {'nx': 20, 'ny': 20, 'nz': 1, 'domain': [1.0, 1.0, 1.0], 'mesh_type': 'structured'}
    results['mesh_create'] = api_post('/api/mesh/create', mesh_payload)

    # 2) Create solver
    solver_payload = {'type': 'laplacianFoam', 'config': {'alpha': 1.0, 'tolerance': 1e-6}}
    results['solver_create'] = api_post('/api/solver/create', solver_payload)

    # 3) Initialize fields
    field_payload = {'U': [0.0, 0.0, 0.0], 'p': 101325.0, 'T': 20.0}
    results['fields_init'] = api_post('/api/fields/initialize', field_payload)

    # 4) Apply boundary conditions
    bcs = [
        {'patch': 'left', 'type': 'dirichlet', 'value': 100.0},
        {'patch': 'right', 'type': 'dirichlet', 'value': 0.0},
        {'patch': 'top', 'type': 'dirichlet', 'value': 20.0},
        {'patch': 'bottom', 'type': 'dirichlet', 'value': 20.0}
    ]
    results['boundary_conditions'] = []
    for bc in bcs:
        results['boundary_conditions'].append(api_post('/api/bc/set', bc))

    # 5) Run simulation
    sim_payload = {'max_iters': 200, 'dt': 0.0001, 'tolerance': 1e-6, 'sample_interval': 10}
    results['simulation'] = api_post('/api/simulate/run', sim_payload)

    # 6) Get heatmap
    heatmap = api_get('/api/results/heatmap')
    results['heatmap'] = heatmap

    # Save numeric results
    with open(RESULTS_PATH, 'w') as f:
        json.dump(results, f, indent=2)

    # Generate heatmap image
    heatmap_data = np.array(heatmap['heatmap']['data'])
    plt.figure(figsize=(6, 5))
    plt.imshow(heatmap_data, origin='lower', cmap='inferno', aspect='auto')
    plt.colorbar(label='Temperature')
    plt.title('LaplacianFoam Heatmap - Test Case')
    plt.xlabel('x index')
    plt.ylabel('y index')
    plt.tight_layout()
    plt.savefig(IMAGE_PATH, dpi=150)
    plt.close()

    # Write markdown report
    report_text = f"""# Test Case Report\n\n"""
    report_text += "## Case Summary\n"
    report_text += "- Solver: laplacianFoam\n"
    report_text += "- Mesh: 20 x 20 x 1, structured\n"
    report_text += "- Domain: [1.0, 1.0, 1.0] meters\n"
    report_text += "- Initial fields: U=[0,0,0], p=101325 Pa, T=20 °C\n"
    report_text += "- Boundary conditions:\n"
    for bc in bcs:
        report_text += f"  - {bc['patch']}: {bc['type']} = {bc['value']}\n"
    report_text += "- Simulation: max_iters=200, dt=0.001, tolerance=1e-6\n\n"
    report_text += "## Simulation Results\n"
    report_text += f"- Converged: {results['simulation']['converged']}\n"
    report_text += f"- Iterations: {results['simulation']['iterations']}\n"
    report_text += f"- Residuals (last 5): {results['simulation']['residuals']['T']}\n"
    report_text += f"- Heatmap min: {heatmap['heatmap']['min']}\n"
    report_text += f"- Heatmap max: {heatmap['heatmap']['max']}\n"
    report_text += f"- Heatmap mean: {heatmap['heatmap']['mean']}\n\n"
    report_text += "## Heatmap Image\n"
    report_text += f"![Heatmap]({os.path.basename(IMAGE_PATH)})\n"

    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report_text)

    print('Report generated:')
    print(' - ', REPORT_PATH)
    print(' - ', IMAGE_PATH)
    print(' - ', RESULTS_PATH)


if __name__ == '__main__':
    main()
