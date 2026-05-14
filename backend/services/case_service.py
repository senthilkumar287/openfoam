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
    "simpleFoam":           "simpleFoam",
    "pimpleFoam":           "pimpleFoam",
    "rhoSimpleFoam":        "rhoSimpleFoam",
    "rhoPimpleFoam":        "rhoPimpleFoam",
    "buoyantSimpleFoam":    "buoyantSimpleFoam",
    "buoyantPimpleFoam":    "buoyantPimpleFoam",
    "chtMultiRegionFoam":   "chtMultiRegionFoam",
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

    is_simple    = solver_type in ("simpleFoam", "rhoSimpleFoam")
    is_pimple    = solver_type in ("pimpleFoam", "rhoPimpleFoam")
    is_buoyant   = solver_type in ("buoyantSimpleFoam", "buoyantPimpleFoam")
    is_cht       = solver_type == "chtMultiRegionFoam"
    is_compressible = solver_type in ("rhoSimpleFoam", "rhoPimpleFoam",
                                      "buoyantSimpleFoam", "buoyantPimpleFoam",
                                      "chtMultiRegionFoam")

    # ── system/blockMeshDict ──────────────────────────────────────────────
    if is_cht:
        ds.write_block_mesh_dict_buoyant(case_dir, params)
        ds.write_region_properties(case_dir, params)
    elif is_buoyant:
        ds.write_block_mesh_dict_buoyant(case_dir, params)
    else:
        ds.write_block_mesh_dict_channel(case_dir, params)  # channel geometry
    written.append("system/blockMeshDict")
    if is_cht:
        written.append("constant/regionProperties")

    # ── 0/ initial fields ─────────────────────────────────────────────────
    is_rho_channel = solver_type in ("rhoSimpleFoam", "rhoPimpleFoam")
    if is_buoyant or is_cht:
        ds.write_U_buoyant(case_dir, params)
        ds.write_p_rgh_buoyant(case_dir, params)
        ds.write_p_buoyant(case_dir, params)
        ds.write_T_buoyant(case_dir, params)
        written += ["0/U", "0/p_rgh", "0/p", "0/T"]
    else:
        ds.write_U_channel(case_dir, params)
        ds.write_p_channel(case_dir, params)
        written += ["0/U", "0/p"]
        if is_rho_channel:
            ds.write_T_channel(case_dir, params)
            written.append("0/T")

    # RAS turbulence initial fields (no-op for laminar)
    ds.write_turbulence_initial_fields(case_dir, params)

    # ── constant/ ─────────────────────────────────────────────────────────
    ds.write_transport_properties(case_dir, params)
    ds.write_turbulence_properties(case_dir, params)
    written += ["constant/transportProperties", "constant/turbulenceProperties"]

    if is_compressible:
        ds.write_thermophysical_properties(case_dir, params)
        ds.write_g_file(case_dir, params)
        written += ["constant/thermophysicalProperties", "constant/g"]

    # ── system/ ───────────────────────────────────────────────────────────
    ds.write_control_dict(case_dir, params)
    ds.write_fv_schemes(case_dir, params)
    ds.write_fv_solution(case_dir, params)
    written += ["system/controlDict", "system/fvSchemes", "system/fvSolution"]

    return written
