"""
OpenFOAM Clone — Flask API
All simulation logic delegated to OpenFOAM via openfoam_backend.py

Dictionary generation flows through:
    API Route → services/case_service → services/dictionary_service
             → dict_engine (AST → OpenFOAM text)
"""
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os, sys, json, shutil, threading, time

sys.path.insert(0, os.path.dirname(__file__))

from openfoam_backend import (
    get_runner, build_case, CASES_ROOT,
    parse_residuals_log, parse_execution_time,
    read_field_as_heatmap, get_latest_time_dir,
    OF_ROOT, OF_BASHRC, run_of_cmd,
)
from services.dictionary_service import DictionaryService

app = Flask(__name__,
    static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend'),
    static_url_path='')
CORS(app)

# Active case state
_active_case    = "default"
_active_params  = {}
_active_solver  = "icoFoam"
_mesh_params    = {}

# ── Helpers ──────────────────────────────────────────────────────
def ok(**kw):
    return jsonify({"status": "success", **kw}), 200

def err(msg, code=400):
    return jsonify({"status": "error", "message": str(msg)}), code

def active_runner(create=True):
    return get_runner(_active_case, create)

def safe_residuals(res_dict):
    """Strip NaN/Inf from residual lists."""
    import math
    return {k: [v for v in vs if math.isfinite(v)] for k, vs in res_dict.items()}

# ── Root ─────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def home():
    frontend = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    return send_file(os.path.abspath(frontend))

@app.route("/api", methods=["GET"])
def api_home():
    of_found = OF_BASHRC is not None
    return ok(
        message    = "OpenFOAM Clone API",
        openfoam   = OF_ROOT if of_found else "NOT FOUND",
        of_status  = "ready" if of_found else "OpenFOAM not installed",
        endpoints  = [
            "POST /api/case/new",
            "POST /api/mesh/create",
            "POST /api/solver/create",
            "POST /api/bc/set",
            "POST /api/simulate/run",
            "POST /api/simulate/run_async",
            "GET  /api/simulate/status",
            "GET  /api/simulate/log",
            "GET  /api/results/heatmap3d",
            "GET  /api/results/residuals",
            "POST /api/results/export",
            "POST /api/case/save",
            "POST /api/case/load",
        ]
    )

# ── Case management ──────────────────────────────────────────────
@app.route("/api/case/new", methods=["POST"])
def new_case():
    global _active_case, _active_params, _mesh_params, _active_solver
    data = request.get_json() or {}
    name = data.get("name", "default").strip().replace(" ", "_")
    _active_case   = name
    _active_params = {}
    _mesh_params   = {}
    _active_solver = "icoFoam"
    # Clean old case dir if exists
    case_dir = os.path.join(CASES_ROOT, name)
    if os.path.exists(case_dir):
        shutil.rmtree(case_dir)
    os.makedirs(case_dir)
    return ok(case=name, message=f"Case '{name}' created")

@app.route("/api/case/save", methods=["POST"])
def save_case():
    global _active_params, _mesh_params, _active_solver
    data = request.get_json() or {}
    name = data.get("name", _active_case)
    meta = {
        "case_name":    name,
        "solver_type":  _active_solver,
        "params":       _active_params,
        "mesh_params":  _mesh_params,
    }
    meta_path = os.path.join(CASES_ROOT, _active_case, "case_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    return ok(file=meta_path, message="Case saved")

@app.route("/api/case/load", methods=["POST"])
def load_case():
    global _active_case, _active_params, _mesh_params, _active_solver
    data = request.get_json() or {}
    name = data.get("name", "default")
    meta_path = os.path.join(CASES_ROOT, name, "case_meta.json")
    if not os.path.exists(meta_path):
        return err(f"Case '{name}' not found")
    with open(meta_path) as f:
        meta = json.load(f)
    _active_case   = name
    _active_solver = meta.get("solver_type", "icoFoam")
    _active_params = meta.get("params", {})
    _mesh_params   = meta.get("mesh_params", {})
    return ok(case=name, solver=_active_solver, params=_active_params)

# ── Mesh ─────────────────────────────────────────────────────────
@app.route("/api/mesh/create", methods=["POST"])
def create_mesh():
    global _mesh_params
    data = request.get_json() or {}
    nx = int(data.get("nx", 20))
    ny = int(data.get("ny", 20))
    nz = int(data.get("nz", 1))
    domain = data.get("domain", [1.0, 1.0, 0.1])
    Lx, Ly = float(domain[0]), float(domain[1])
    Lz = float(domain[2]) if len(domain) > 2 else 0.1

    _mesh_params = {"nx":nx,"ny":ny,"nz":nz,"Lx":Lx,"Ly":Ly,"Lz":Lz}
    _active_params.update(_mesh_params)

    cells   = nx * ny * nz
    dx = Lx/nx; dy = Ly/ny; dz = Lz/nz if nz > 1 else Lz

    return ok(
        mesh={
            "nx":nx,"ny":ny,"nz":nz,
            "Lx":Lx,"Ly":Ly,"Lz":Lz,
            "cells":cells,"dx":round(dx,6),"dy":round(dy,6)
        },
        message=f"Mesh configured: {nx}×{ny}×{nz} ({cells} cells)"
    )

@app.route("/api/mesh/info", methods=["GET"])
def mesh_info():
    return ok(mesh=_mesh_params)

# ── Solver ───────────────────────────────────────────────────────
@app.route("/api/solver/list", methods=["GET"])
def list_solvers():
    return ok(solvers=[
        {"name":"icoFoam",           "desc":"Transient laminar incompressible (PISO). Cavity/channel flow."},
        {"name":"simpleFoam",        "desc":"Steady-state incompressible (SIMPLE). Channel/pipe flow."},
        {"name":"pisoFoam",          "desc":"Transient laminar incompressible (PISO). Like icoFoam."},
        {"name":"pimpleFoam",        "desc":"Transient incompressible (PIMPLE). Large time steps."},
        {"name":"buoyantSimpleFoam", "desc":"Steady natural convection. Boussinesq buoyancy."},
        {"name":"laplacianFoam",     "desc":"Scalar diffusion (heat conduction). Simplest case."},
    ])

@app.route("/api/solver/create", methods=["POST"])
def create_solver():
    global _active_solver, _active_params
    data = request.get_json() or {}
    solver = data.get("type", "icoFoam")
    config = data.get("config", {})
    _active_solver = solver
    _active_params.update(config)
    _active_params.update(_mesh_params)  # ensure mesh params present
    return ok(solver=solver, config=config, message=f"{solver} configured")

# ── Boundary Conditions ──────────────────────────────────────────
@app.route("/api/bc/set", methods=["POST"])
def set_bc():
    data = request.get_json() or {}
    patch = data.get("patch","")
    bc_type = data.get("type","fixedValue")
    value   = data.get("value", 0.0)

    # Map BC values into _active_params for file generation
    bc_map = {
        "movingWall": "lid_velocity",
        "inlet":      "U_inlet",
        "hotWall":    "T_hot",
        "coldWall":   "T_cold",
        "left":       "T_hot",
        "right":      "T_cold",
        "outlet_p":   "p_outlet",
    }
    if patch in bc_map:
        _active_params[bc_map[patch]] = value
    _active_params.setdefault("bcs", {})[patch] = {"type": bc_type, "value": value}
    return ok(patch=patch, type=bc_type, value=value)

@app.route("/api/bc/list", methods=["GET"])
def list_bcs():
    return ok(bcs=_active_params.get("bcs", {}))

@app.route("/api/fields/initialize", methods=["POST"])
def init_fields():
    data = request.get_json() or {}
    _active_params.update({
        "internal_field_U": data.get("U", [0,0,0]),
        "internal_field_p": data.get("p", 0.0),
        "T_init":           data.get("T", 300.0),
    })
    return ok(message="Initial conditions stored")

# ── Simulation ───────────────────────────────────────────────────
def _merged_params(user_data):
    """Merge stored params with per-request overrides."""
    p = _active_params.copy()
    p.update(_mesh_params)
    # controlDict overrides from request
    for key in ["endTime","deltaT","startTime","writeInterval","writeControl",
                "nCorrectors","nNonOrthogonalCorrectors","purgeWrite",
                "p_solver","U_solver","p_tolerance","U_tolerance",
                "relaxation_U","relaxation_p",
                "ddtScheme","gradScheme","divScheme_U","laplacianScheme",
                "turbulence","ras_model",
                "nu","rho","alpha","beta","T_ref","T_hot","T_cold","g",
                "lid_velocity","U_inlet","inlet_profile","p_outlet",
                "Cp","kappa"]:
        if key in user_data:
            p[key] = user_data[key]

    if "max_iters" in user_data and "endTime" not in user_data:
        # Convert max_iters → endTime for icoFoam
        dt = float(p.get("deltaT", 0.005))
        p["endTime"] = round(int(user_data["max_iters"]) * dt, 6)

    return p


@app.route("/api/simulate/run", methods=["POST"])
def run_simulation():
    """Synchronous run — builds case, runs OpenFOAM, returns when done."""
    if OF_BASHRC is None:
        return err("OpenFOAM not found on this machine. Install OpenFOAM first.", 503)

    data   = request.get_json() or {}
    params = _merged_params(data)
    solver = _active_solver
    runner = active_runner()

    # Clean previous run in case dir
    case_dir = runner.case_dir
    for d in os.listdir(case_dir):
        dp = os.path.join(case_dir, d)
        if os.path.isdir(dp) and d not in ("0","constant","system","processor0"):
            try: shutil.rmtree(dp)
            except: pass

    try:
        written = runner.build(solver, params)
        runner._run_blockmesh(timeout=60)
        runner._run_solver(solver, params, timeout=1800)
    except RuntimeError as e:
        log_tail = runner.tail_log(30)
        return err(f"{e}\n\nLog tail:\n{log_tail}", 500)

    res = safe_residuals(runner.residuals)
    nx = int(params.get("nx",20)); ny=int(params.get("ny",20)); nz=int(params.get("nz",1))
    latest = get_latest_time_dir(runner.case_dir)

    return ok(
        converged    = runner.status == "done",
        iterations   = max((len(v) for v in res.values()), default=0),
        exec_time    = runner.exec_time,
        residuals    = {k: v[-5:] for k,v in res.items()},
        latest_time  = os.path.basename(latest) if latest else None,
        files_written= written,
        message      = "Simulation complete" if runner.status=="done" else runner.error_msg
    )


@app.route("/api/simulate/run_async", methods=["POST"])
def run_async():
    """Non-blocking: starts simulation in background thread."""
    if OF_BASHRC is None:
        return err("OpenFOAM not found", 503)

    data   = request.get_json() or {}
    params = _merged_params(data)
    solver = _active_solver
    runner = active_runner()

    if runner.is_running():
        return err("Simulation already running")

    runner.run_async(solver, params)
    return ok(message="Simulation started async", status="running")


@app.route("/api/simulate/status", methods=["GET"])
def sim_status():
    runner = active_runner(create=False)
    if runner is None:
        return ok(status="idle", iterations=0, residuals={})

    res = safe_residuals(runner.residuals)
    last_res = {k: v[-1] if v else None for k, v in res.items()}

    return ok(
        status     = runner.status,
        progress   = round(runner.progress, 1),
        iterations = max((len(v) for v in res.values()), default=0),
        converged  = runner.status == "done",
        residuals  = last_res,
        exec_time  = runner.exec_time,
        error      = runner.error_msg if runner.status=="error" else None
    )


@app.route("/api/simulate/log", methods=["GET"])
def sim_log():
    """Stream last N lines of OpenFOAM log."""
    n = int(request.args.get("lines", 50))
    runner = active_runner(create=False)
    if runner is None:
        return ok(log="No simulation run yet")
    return ok(log=runner.tail_log(n))

# ── Mesh import ──────────────────────────────────────────────────
@app.route("/api/mesh/import", methods=["POST"])
def import_mesh():
    """
    Import an OpenFOAM mesh from uploaded files.
    Accepts: blockMeshDict file OR a zipped constant/polyMesh folder.
    Frontend sends multipart/form-data with file field 'mesh_file'.
    """
    from werkzeug.utils import secure_filename
    import zipfile, tempfile

    if 'mesh_file' not in request.files:
        return err("No file uploaded. Send file in 'mesh_file' field.")

    f = request.files['mesh_file']
    filename = secure_filename(f.filename)
    runner   = active_runner()
    case_dir = runner.case_dir

    # Ensure case dirs exist
    os.makedirs(os.path.join(case_dir, "system"),            exist_ok=True)
    os.makedirs(os.path.join(case_dir, "constant","polyMesh"),exist_ok=True)

    if filename.endswith('.zip'):
        # Zip containing polyMesh or full case structure
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, filename)
            f.save(zip_path)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(tmp)
            # Find blockMeshDict or polyMesh
            for root, dirs, files in os.walk(tmp):
                for fname in files:
                    src = os.path.join(root, fname)
                    if fname == 'blockMeshDict':
                        dst = os.path.join(case_dir, 'system', 'blockMeshDict')
                        shutil.copy2(src, dst)
                        _active_params['mesh_imported'] = True
                        return ok(message="blockMeshDict imported from zip", file=dst)
                    if fname in ('points','faces','owner','neighbour','boundary'):
                        dst = os.path.join(case_dir, 'constant', 'polyMesh', fname)
                        shutil.copy2(src, dst)
        # Check if polyMesh was populated
        pm = os.path.join(case_dir, 'constant', 'polyMesh', 'points')
        if os.path.exists(pm):
            _active_params['mesh_imported'] = True
            return ok(message="polyMesh imported from zip")
        return err("No blockMeshDict or polyMesh found in zip")

    elif filename == 'blockMeshDict' or filename.endswith('Dict'):
        # Raw blockMeshDict file
        dst = os.path.join(case_dir, 'system', 'blockMeshDict')
        f.save(dst)
        # Try to extract mesh dimensions from blockMeshDict
        content = open(dst).read()
        import re
        m = re.search(r'hex\s*\([^)]+\)\s*\((\d+)\s+(\d+)\s+(\d+)\)', content)
        if m:
            nx,ny,nz = int(m.group(1)),int(m.group(2)),int(m.group(3))
            _mesh_params.update({'nx':nx,'ny':ny,'nz':nz})
            _active_params.update(_mesh_params)
        _active_params['mesh_imported'] = True
        return ok(message="blockMeshDict imported", nx=_mesh_params.get('nx'), ny=_mesh_params.get('ny'))

    else:
        # Try saving as blockMeshDict anyway
        dst = os.path.join(case_dir, 'system', 'blockMeshDict')
        f.save(dst)
        _active_params['mesh_imported'] = True
        return ok(message=f"File saved as blockMeshDict: {filename}")


@app.route("/api/mesh/run_blockmesh", methods=["POST"])
def run_blockmesh_only():
    """Run blockMesh on imported mesh file."""
    if OF_BASHRC is None:
        return err("OpenFOAM not found", 503)
    runner = active_runner()
    try:
        runner._run_blockmesh(timeout=120)
        return ok(message="blockMesh completed successfully")
    except RuntimeError as e:
        return err(str(e) + "\n\n" + runner.tail_log(20))


# ── Results ──────────────────────────────────────────────────────
@app.route("/api/results/fields", methods=["GET"])
def list_fields():
    """Return list of available fields in latest time step."""
    from openfoam_backend import list_available_fields
    runner = active_runner(create=False)
    if runner is None:
        return ok(fields=[])
    fields = list_available_fields(runner.case_dir)
    return ok(fields=fields)


@app.route("/api/results/heatmap3d", methods=["GET"])
def heatmap3d():
    field  = request.args.get("field", "U")
    runner = active_runner(create=False)
    if runner is None or runner.status not in ("done","running"):
        return err("No results available. Run simulation first.")

    nx=int(_active_params.get("nx",20))
    ny=int(_active_params.get("ny",20))
    nz=int(_active_params.get("nz",1))

    hm = runner.get_heatmap(field, nx, ny, nz)
    if hm is None:
        from openfoam_backend import list_available_fields
        available = list_available_fields(runner.case_dir)
        return err(f"Field '{field}' not found. Available: {available}")

    return ok(heatmap=hm)

@app.route("/api/results/heatmap", methods=["GET"])
def heatmap():
    return heatmap3d()

@app.route("/api/results/residuals", methods=["GET"])
def residuals():
    runner = active_runner(create=False)
    if runner is None:
        return ok(residuals={})
    return ok(residuals=safe_residuals(runner.residuals))

@app.route("/api/results/field/<field_name>", methods=["GET"])
def get_field(field_name):
    runner = active_runner(create=False)
    if runner is None:
        return err("No results")
    nx=int(_active_params.get("nx",20))
    ny=int(_active_params.get("ny",20))
    nz=int(_active_params.get("nz",1))
    hm = runner.get_heatmap(field_name, nx, ny, nz)
    if hm is None:
        return err(f"Field {field_name} not found")
    return ok(heatmap=hm)

@app.route("/api/results/export", methods=["POST"])
def export_results():
    data   = request.get_json() or {}
    fmt    = data.get("format","vtk")
    runner = active_runner(create=False)
    if runner is None:
        return err("No results to export")

    latest = get_latest_time_dir(runner.case_dir)
    if latest is None:
        return err("No time steps found")

    exports_dir = os.path.join(os.path.dirname(__file__), "exports")
    os.makedirs(exports_dir, exist_ok=True)

    if fmt == "vtk":
        # Run foamToVTK if available
        rc, out = run_of_cmd("foamToVTK", runner.case_dir, timeout=60)
        vtk_dir = os.path.join(runner.case_dir, "VTK")
        if os.path.exists(vtk_dir):
            dst = os.path.join(exports_dir, f"{_active_case}.vtk.tar.gz")
            import tarfile
            with tarfile.open(dst,"w:gz") as tar:
                tar.add(vtk_dir, arcname="VTK")
            return ok(file=dst, message="VTK export complete")
        else:
            return err(f"foamToVTK failed: {out[:200]}")

    elif fmt == "csv":
        import csv
        nx=int(_active_params.get("nx",20))
        ny=int(_active_params.get("ny",20))
        nz=int(_active_params.get("nz",1))
        dst = os.path.join(exports_dir, f"{_active_case}_results.csv")
        with open(dst,"w",newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["field","i","j","k","value"])
            for field in ["U","p","T"]:
                hm = runner.get_heatmap(field,nx,ny,nz)
                if hm:
                    import numpy as np
                    arr = np.array(hm["data"])
                    for k in range(nz):
                        for j in range(ny):
                            for i in range(nx):
                                writer.writerow([field,i,j,k,arr[k,j,i]])
        return ok(file=dst, message="CSV export complete")

    elif fmt == "json":
        dst = os.path.join(exports_dir, f"{_active_case}_results.json")
        nx=int(_active_params.get("nx",20)); ny=int(_active_params.get("ny",20)); nz=int(_active_params.get("nz",1))
        out_data = {"case": _active_case, "solver": _active_solver, "params": _active_params, "fields": {}}
        for field in ["U","p","T"]:
            hm = runner.get_heatmap(field,nx,ny,nz)
            if hm:
                out_data["fields"][field] = hm
        with open(dst,"w") as f:
            json.dump(out_data, f)
        return ok(file=dst, message="JSON export complete")

    return err(f"Unknown format: {fmt}")

# ── OpenFOAM info ────────────────────────────────────────────────
@app.route("/api/openfoam/info", methods=["GET"])
def of_info():
    return ok(
        found   = OF_BASHRC is not None,
        root    = OF_ROOT,
        bashrc  = OF_BASHRC,
        message = "OpenFOAM ready" if OF_BASHRC else "OpenFOAM not found"
    )

if __name__ == "__main__":
    print(f"OpenFOAM: {OF_ROOT or 'NOT FOUND'}")
    print(f"Cases dir: {CASES_ROOT}")
    app.run(host="0.0.0.0", port=5000, debug=False)
