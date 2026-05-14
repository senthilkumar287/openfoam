"""
services/case_service.py

Orchestrates the full OpenFOAM case lifecycle:
    - directory scaffolding
    - delegates all dictionary writes to DictionaryService
    - knows which files belong to which solver type

This is the single place that decides WHAT files to write.
DictionaryService decides HOW to write them (via the Dictionary Engine).
No f-strings, no manual open()/write() calls here.
"""
from __future__ import annotations
import os
import shutil

from services.dictionary_service import DictionaryService


SOLVER_APPS = {
    "icoFoam":           "icoFoam",
    "simpleFoam":        "simpleFoam",
    "pisoFoam":          "pisoFoam",
    "pimpleFoam":        "pimpleFoam",
    "buoyantSimpleFoam": "buoyantSimpleFoam",
    "laplacianFoam":     "laplacianFoam",
}


def build_case(case_dir: str, solver_type: str, params: dict) -> list[str]:
    """
    Write a complete OpenFOAM case directory from user params.
    Every file is produced by DictionaryService → Dictionary Engine.
    Returns list of relative paths written.
    """
    # Ensure standard sub-dirs exist
    for sub in ("0", "constant", "system"):
        os.makedirs(os.path.join(case_dir, sub), exist_ok=True)

    app = SOLVER_APPS.get(solver_type, solver_type)
    params = dict(params)           # local copy — don't mutate caller's dict
    params["application"] = app

    written: list[str] = []
    ds = DictionaryService           # alias for brevity

    is_channel   = solver_type in ("simpleFoam", "pisoFoam", "pimpleFoam")
    is_buoyant   = solver_type == "buoyantSimpleFoam"
    is_laplacian = solver_type == "laplacianFoam"

    # ── system/blockMeshDict ──────────────────────────────────────────────
    if is_channel:
        ds.write_block_mesh_dict_channel(case_dir, params)
    else:
        ds.write_block_mesh_dict(case_dir, params)
    written.append("system/blockMeshDict")

    # ── 0/ initial fields ─────────────────────────────────────────────────
    if is_buoyant:
        ds.write_U_buoyant(case_dir, params)
        ds.write_p_rgh_buoyant(case_dir, params)
        ds.write_p_buoyant(case_dir, params)
        ds.write_T_buoyant(case_dir, params)
        written += ["0/U", "0/p_rgh", "0/p", "0/T"]
    elif is_laplacian:
        ds.write_T_laplacian(case_dir, params)
        written.append("0/T")
    elif is_channel:
        ds.write_U_channel(case_dir, params)
        ds.write_p_channel(case_dir, params)
        written += ["0/U", "0/p"]
    else:   # cavity — icoFoam / pisoFoam default
        ds.write_U_cavity(case_dir, params)
        ds.write_p_cavity(case_dir, params)
        written += ["0/U", "0/p"]

    # RAS turbulence initial fields (no-op for laminar)
    ds.write_turbulence_initial_fields(case_dir, params)

    # ── constant/ ─────────────────────────────────────────────────────────
    if is_laplacian:
        ds.write_transport_properties_laplacian(case_dir, params)
    else:
        ds.write_transport_properties(case_dir, params)
    ds.write_turbulence_properties(case_dir, params)
    written += ["constant/transportProperties", "constant/turbulenceProperties"]

    if is_buoyant:
        ds.write_thermophysical_properties(case_dir, params)
        ds.write_g_file(case_dir, params)
        written += ["constant/thermophysicalProperties", "constant/g"]

    # ── system/ ───────────────────────────────────────────────────────────
    ds.write_control_dict(case_dir, params)
    ds.write_fv_schemes(case_dir, params)
    ds.write_fv_solution(case_dir, params)
    written += ["system/controlDict", "system/fvSchemes", "system/fvSolution"]

    return written
