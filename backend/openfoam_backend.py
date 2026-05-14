"""
OpenFOAM Backend — execution engine + result parser.

Architecture (after Dictionary Engine integration)
===================================================
  API Route
    → services/case_service.py        (what files to write)
      → services/dictionary_service.py (how — via Dictionary Engine)
        → dict_engine/                 (AST → OpenFOAM text)
    → CaseRunner._run_blockmesh()      (subprocess: blockMesh)
    → CaseRunner._run_solver()         (subprocess: icoFoam / simpleFoam …)
    → parse_of_*() / read_field_*()    (read results back)

What lives here
---------------
  - OpenFOAM environment discovery  (find_openfoam, of_env, run_of_cmd)
  - CaseRunner                      (thread-safe lifecycle manager)
  - Result parsers                   (parse_of_scalar_field, read_field_as_heatmap …)
  - Global runner registry           (get_runner)

What no longer lives here
--------------------------
  All write_*() functions and build_case() have moved to:
    services/dictionary_service.py  — Dictionary Engine-backed file writers
    services/case_service.py        — case orchestration (what files to write)
    services/solver_service.py      — subprocess delegation
"""

import os
import sys
import subprocess
import shutil
import json
import re
import time
import threading
import glob

import numpy as np
from pathlib import Path

# ── ensure services and dict_engine are importable ───────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from services.case_service import build_case, SOLVER_APPS
from services.solver_service import SolverService


# ══════════════════════════════════════════════════════════════════════════════
#  OpenFOAM environment
# ══════════════════════════════════════════════════════════════════════════════

def find_openfoam():
    """Locate OpenFOAM installation."""
    here = os.path.dirname(os.path.abspath(__file__))
    cfg  = os.path.join(here, "of_config.json")

    if os.path.exists(cfg):
        try:
            d = json.load(open(cfg))
            bashrc = d.get("OF_BASHRC", "")
            root   = d.get("OF_ROOT",   "")
            if bashrc and os.path.exists(bashrc):
                return root, bashrc
        except Exception:
            pass

    wm = os.environ.get("WM_PROJECT_DIR", "")
    if wm:
        bashrc = os.path.join(wm, "etc", "bashrc")
        if os.path.exists(bashrc):
            return wm, bashrc

    candidates = [
        "/opt/openfoam11", "/opt/openfoam10", "/opt/openfoam9",
        "/opt/openfoam8",  "/opt/openfoam7",  "/opt/openfoam6",
        "/opt/openfoam2312", "/opt/openfoam2306", "/opt/openfoam2212",
        "/opt/openfoam2112",
        "/usr/lib/openfoam/openfoam2312",
        "/usr/lib/openfoam/openfoam2212",
        "/usr/lib/openfoam/openfoam11",
    ]
    for path in candidates:
        etc = os.path.join(path, "etc", "bashrc")
        if os.path.exists(etc):
            return path, etc

    return None, None


OF_ROOT, OF_BASHRC = find_openfoam()


def of_env():
    if OF_BASHRC is None:
        raise RuntimeError(
            "OpenFOAM not found. Install OpenFOAM and ensure /opt/openfoamXX exists."
        )
    cmd    = f'source "{OF_BASHRC}" && env'
    result = subprocess.run(
        ["bash", "-c", cmd], capture_output=True, text=True, timeout=30
    )
    env = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            env[k] = v
    return env


_of_env_cache = None


def get_of_env():
    global _of_env_cache
    if _of_env_cache is None:
        _of_env_cache = of_env()
    return _of_env_cache


def run_of_cmd(cmd, cwd, timeout=600, log_file=None):
    """Run an OpenFOAM command (blockMesh, icoFoam, …) with sourced env."""
    get_of_env()
    full_cmd = f'source "{OF_BASHRC}" && cd "{cwd}" && {cmd}'
    proc = subprocess.Popen(
        ["bash", "-c", full_cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=os.environ.copy(),
    )
    output_lines = []
    for line in proc.stdout:
        output_lines.append(line)
        if log_file:
            with open(log_file, "a") as f:
                f.write(line)
    proc.wait(timeout=timeout)
    return proc.returncode, "".join(output_lines)


# ══════════════════════════════════════════════════════════════════════════════
#  Result parsers
# ══════════════════════════════════════════════════════════════════════════════

def parse_of_scalar_field(filepath):
    with open(filepath) as f:
        text = f.read()
    m = re.search(
        r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([^)]+)\)",
        text, re.DOTALL,
    )
    if m:
        return np.array([float(x) for x in m.group(2).split()], dtype=float)
    m = re.search(r"internalField\s+uniform\s+([\d.eE+\-]+)", text)
    if m:
        return np.array([float(m.group(1))])
    return None


def parse_of_vector_field(filepath, component=0):
    with open(filepath) as f:
        text = f.read()
    m = re.search(
        r"internalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(([^;]+)\)",
        text, re.DOTALL,
    )
    if m:
        raw    = m.group(2).strip()
        tuples = re.findall(
            r"\(\s*([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s*\)", raw
        )
        arr = np.array([[float(x), float(y), float(z)] for x, y, z in tuples], dtype=float)
        if component == "mag":
            return np.linalg.norm(arr, axis=1)
        return arr[:, component]
    m = re.search(
        r"internalField\s+uniform\s+\(\s*([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s*\)",
        text,
    )
    if m:
        vals = [float(m.group(i + 1)) for i in range(3)]
        if component == "mag":
            return np.array([np.linalg.norm(vals)])
        return np.array([vals[component]])
    return None


def get_latest_time_dir(case_dir):
    dirs = []
    for d in os.listdir(case_dir):
        try:
            t = float(d)
            if t > 0:
                dirs.append((t, d))
        except ValueError:
            pass
    if not dirs:
        return None
    dirs.sort()
    return os.path.join(case_dir, dirs[-1][1])


def list_available_fields(case_dir):
    latest = get_latest_time_dir(case_dir)
    if latest is None:
        zero = os.path.join(case_dir, "0")
        if os.path.exists(zero):
            return [
                f for f in os.listdir(zero)
                if os.path.isfile(os.path.join(zero, f)) and not f.startswith(".")
            ]
        return []
    skip = {"uniform", "polyMesh", "sets", "surfaces"}
    fields = []
    for f in os.listdir(latest):
        if f in skip or f.startswith("."):
            continue
        if os.path.isfile(os.path.join(latest, f)):
            fields.append(f)
    return sorted(fields)


def _best_field(case_dir, requested):
    available = list_available_fields(case_dir)
    if not available:
        return None
    if requested in available:
        return requested
    aliases = {
        "T":           ["T", "p", "U"],
        "temperature": ["T", "p"],
        "p":           ["p", "p_rgh"],
        "pressure":    ["p", "p_rgh"],
        "U":           ["U"],
        "Umag":        ["U"],
        "velocity":    ["U"],
        "k":           ["k"],
        "epsilon":     ["epsilon"],
        "omega":       ["omega"],
    }
    for candidate in aliases.get(requested, [requested]):
        if candidate in available:
            return candidate
    for f in available:
        if f not in ("polyMesh",):
            return f
    return None


def read_field_as_heatmap(case_dir, field_name, nx, ny, nz=1):
    latest = get_latest_time_dir(case_dir)
    if latest is None:
        return None
    resolved = _best_field(case_dir, field_name)
    if resolved is None:
        return None
    fpath = os.path.join(latest, resolved)
    if not os.path.exists(fpath):
        return None

    arr = parse_of_scalar_field(fpath)
    if arr is None:
        arr = parse_of_vector_field(fpath, component="mag")
    if arr is None:
        return None

    if arr.size == 1:
        arr = np.full(nx * ny * nz, arr[0])
    arr = arr.astype(float)
    bad = ~np.isfinite(arr)
    if bad.any() and not bad.all():
        good = np.flatnonzero(~bad)
        arr[np.flatnonzero(bad)] = np.interp(np.flatnonzero(bad), good, arr[good])
    elif bad.all():
        arr[:] = 0.0

    total = nx * ny * nz
    if arr.size < total:
        arr = np.resize(arr, total)
    elif arr.size > total:
        arr = arr[:total]
    arr  = arr.reshape(nz, ny, nx)

    return {
        "data":      arr.tolist(),
        "min":       float(arr.min()),
        "max":       float(arr.max()),
        "shape":     [nz, ny, nx],
        "is_3d":     nz > 1,
        "field":     field_name,
        "requested": field_name,
        "time_dir":  os.path.basename(latest),
    }


def parse_residuals_log(log_path):
    residuals = {}
    if not os.path.exists(log_path):
        return residuals
    pattern = re.compile(
        r"Solving for (\w+).*?Initial residual = ([\d.eE+\-]+)", re.IGNORECASE
    )
    with open(log_path) as f:
        for line in f:
            m = pattern.search(line)
            if m:
                name = m.group(1)
                val  = float(m.group(2))
                if np.isfinite(val):
                    residuals.setdefault(name, []).append(val)
    return residuals


def parse_execution_time(log_path):
    if not os.path.exists(log_path):
        return None
    with open(log_path) as f:
        text = f.read()
    m = re.findall(r"ExecutionTime\s*=\s*([\d.]+)\s*s", text)
    return float(m[-1]) if m else None


# ══════════════════════════════════════════════════════════════════════════════
#  CaseRunner
# ══════════════════════════════════════════════════════════════════════════════

class CaseRunner:
    """
    Manages one OpenFOAM case: build → mesh → solve → parse.

    Dictionary generation is fully delegated through the service layer
    to the Dictionary Engine.  No file-writing occurs here.
    """

    def __init__(self, case_dir):
        self.case_dir  = case_dir
        self.status    = "idle"
        self.log_path  = os.path.join(case_dir, "foam.log")
        self.progress  = 0.0
        self.error_msg = ""
        self.residuals = {}
        self.exec_time = None
        self._params   = {}
        self._thread   = None

    def build(self, solver_type: str, params: dict) -> list[str]:
        """Write all case files via the Dictionary Engine."""
        return SolverService.build(self, solver_type, params)

    def run_async(self, solver_type: str, params: dict) -> None:
        SolverService.run_async(self, solver_type, params)

    def run_sync(self, solver_type: str, params: dict, timeout: int = 600) -> None:
        SolverService.run_sync(self, solver_type, params, timeout=timeout)

    # Called by SolverService ─────────────────────────────────────────────────
    def _run_blockmesh(self, timeout: int = 60) -> None:
        self.status   = "meshing"
        self.progress = 5.0
        if os.path.exists(self.log_path):
            os.remove(self.log_path)
        rc, out = run_of_cmd(
            "blockMesh", self.case_dir, timeout=timeout, log_file=self.log_path
        )
        if rc != 0:
            self.status    = "error"
            self.error_msg = f"blockMesh failed (rc={rc}). Check {self.log_path}"
            raise RuntimeError(self.error_msg)
        self.progress = 15.0

    def _run_solver(self, solver_type: str, params: dict, timeout: int = 600) -> None:
        self.status = "running"
        app = SOLVER_APPS.get(solver_type, solver_type)
        rc, out = run_of_cmd(
            app, self.case_dir, timeout=timeout, log_file=self.log_path
        )
        self.residuals = parse_residuals_log(self.log_path)
        self.exec_time = parse_execution_time(self.log_path)
        self.progress  = 100.0
        if rc != 0:
            self.status    = "error"
            self.error_msg = f"{app} failed (rc={rc}). Check {self.log_path}"
            raise RuntimeError(self.error_msg)
        self.status = "done"

    # Result helpers ──────────────────────────────────────────────────────────
    def get_heatmap(self, field_name: str, nx: int, ny: int, nz: int = 1):
        return read_field_as_heatmap(self.case_dir, field_name, nx, ny, nz)

    def tail_log(self, n: int = 40) -> str:
        if not os.path.exists(self.log_path):
            return ""
        with open(self.log_path) as f:
            lines = f.readlines()
        return "".join(lines[-n:])

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


# ══════════════════════════════════════════════════════════════════════════════
#  Global runner registry
# ══════════════════════════════════════════════════════════════════════════════

CASES_ROOT = os.path.join(os.path.dirname(__file__), "of_cases")
os.makedirs(CASES_ROOT, exist_ok=True)

_runners: dict = {}


def get_runner(name: str, create: bool = True):
    if name not in _runners and create:
        case_dir = os.path.join(CASES_ROOT, name)
        os.makedirs(case_dir, exist_ok=True)
        _runners[name] = CaseRunner(case_dir)
    return _runners.get(name)
