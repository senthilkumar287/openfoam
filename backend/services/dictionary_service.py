"""
services/dictionary_service.py

Central service for all OpenFOAM dictionary generation and manipulation.
Every byte written into a case directory flows through here via the
Dictionary Engine.  No f-string OpenFOAM templates anywhere below this layer.

Public surface
--------------
    DictionaryService.write_control_dict(case_dir, params)
    DictionaryService.write_fv_schemes(case_dir, params)
    DictionaryService.write_fv_solution(case_dir, params)
    DictionaryService.write_block_mesh_dict(case_dir, params)
    DictionaryService.write_block_mesh_dict_channel(case_dir, params)
    DictionaryService.write_transport_properties(case_dir, params)
    DictionaryService.write_transport_properties_laplacian(case_dir, params)
    DictionaryService.write_turbulence_properties(case_dir, params)
    DictionaryService.write_thermophysical_properties(case_dir, params)
    DictionaryService.write_g_file(case_dir, params)
    DictionaryService.write_U_cavity(case_dir, params)
    DictionaryService.write_U_channel(case_dir, params)
    DictionaryService.write_p_cavity(case_dir, params)
    DictionaryService.write_p_channel(case_dir, params)
    DictionaryService.write_p_rgh_buoyant(case_dir, params)
    DictionaryService.write_p_buoyant(case_dir, params)
    DictionaryService.write_T_buoyant(case_dir, params)
    DictionaryService.write_T_laplacian(case_dir, params)
    DictionaryService.write_turbulence_initial_fields(case_dir, params)
    DictionaryService.patch_dict(path, updates)   ← load-modify-write
"""
from __future__ import annotations
import os
import sys

# Make sure the dict_engine is importable whether we are called from inside
# the backend package or from outside it.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from dict_engine import (
    Dict_, Scalar, Vector, Dimensioned, FieldValue, List_, KeyValueList,
    parse_file, write_dict_file, make_foam_file_header,
)


# ── internal helpers ──────────────────────────────────────────────────────────

def _kvlist_from_patches(patches: list[tuple[str, dict]]) -> KeyValueList:
    """Build a KeyValueList node from a list of (patch_name, {key: value}) pairs."""
    kv = KeyValueList()
    for name, fields in patches:
        sub = Dict_()
        for k, v in fields.items():
            if isinstance(v, dict):
                # nested dict (e.g. codedFixedValue with sub-keys)
                inner = Dict_()
                for ik, iv in v.items():
                    inner.set(ik, iv)
                sub._set_child(k, inner)
            else:
                sub.set(k, v)
        kv.entries.append((name, sub))
    return kv


def _write_field(
    case_dir: str,
    rel_path: str,
    class_name: str,
    body: Dict_,
) -> None:
    """Compose FoamFile header + body and write to disk."""
    object_name = os.path.basename(rel_path)
    location = os.path.dirname(rel_path)  # e.g. "0" or "constant"
    full_path = os.path.join(case_dir, rel_path)
    write_dict_file(
        path=full_path,
        body=body,
        class_name=class_name,
        object_name=object_name,
        location=location,
    )


# ── DictionaryService ─────────────────────────────────────────────────────────

class DictionaryService:
    """Namespace for all OpenFOAM dictionary write operations."""

    # ── system/ ──────────────────────────────────────────────────────────────

    @staticmethod
    def write_control_dict(case_dir: str, params: dict) -> None:
        """system/controlDict"""
        app        = params.get("application", "icoFoam")
        startTime  = params.get("startTime",   0.0)
        endTime    = params.get("endTime",     0.5)
        deltaT     = params.get("deltaT",      0.005)
        writeCtrl  = params.get("writeControl", "timeStep")
        writeInt   = params.get("writeInterval", 20)
        purgeWrite = params.get("purgeWrite",  0)
        runTimeMod = params.get("runTimeModifiable", "true")

        d = Dict_()
        d.set("application",        app)
        d.set("startFrom",          "startTime")
        d.set("startTime",          startTime)
        d.set("stopAt",             "endTime")
        d.set("endTime",            endTime)
        d.set("deltaT",             deltaT)
        d.set("writeControl",       writeCtrl)
        d.set("writeInterval",      writeInt)
        d.set("purgeWrite",         purgeWrite)
        d.set("writeFormat",        "ascii")
        d.set("writePrecision",     8)
        d.set("writeCompression",   "off")
        d.set("timeFormat",         "general")
        d.set("timePrecision",      6)
        d.set("runTimeModifiable",  runTimeMod)

        _write_field(case_dir, "system/controlDict", "dictionary", d)

    @staticmethod
    def write_fv_schemes(case_dir: str, params: dict) -> None:
        """system/fvSchemes"""
        app   = params.get("application", "simpleFoam")
        ddt   = params.get("ddtScheme",  "Euler")
        grad  = params.get("gradScheme", "Gauss linear")
        div_U = params.get("divScheme_U", "Gauss linearUpwind grad(U)")
        lapl  = params.get("laplacianScheme", "Gauss linear corrected")
        interp = params.get("interpolationScheme", "linear")

        # Steady-state solvers use steadyState ddt; transient solvers keep Euler
        _STEADY = ("simpleFoam", "rhoSimpleFoam", "buoyantSimpleFoam")
        if app in _STEADY:
            ddt = "steadyState"

        # Compressible solvers (rho-based)
        _COMPRESSIBLE = ("rhoSimpleFoam", "rhoPimpleFoam",
                         "buoyantSimpleFoam", "buoyantPimpleFoam",
                         "chtMultiRegionFoam")

        # ddtSchemes
        ddt_block = Dict_()
        ddt_block.set("default", ddt)

        # gradSchemes
        grad_block = Dict_()
        grad_block.set("default", grad)
        grad_block.set("grad(p)", grad)
        grad_block.set("grad(U)", grad)

        # divSchemes — use _set_child (NOT .set) for keys containing dots,
        # because .set() splits on '.' for dotted-path navigation, which
        # breaks keys like "div((nuEff*dev2(T(grad(U)))))".
        div_block = Dict_()
        div_block._set_child("default",                         Scalar(value="none"))
        div_block._set_child("div(phi,U)",                      Scalar(value=div_U))
        div_block._set_child("div(phi,k)",                      Scalar(value="Gauss upwind"))
        div_block._set_child("div(phi,epsilon)",                Scalar(value="Gauss upwind"))
        div_block._set_child("div(phi,omega)",                  Scalar(value="Gauss upwind"))
        div_block._set_child("div(phi,T)",                      Scalar(value="Gauss upwind"))

        if app in _COMPRESSIBLE:
            # OpenFOAM 2312: compressible solvers require dev2 form
            div_block._set_child("div((nuEff*dev2(T(grad(U)))))",        Scalar(value="Gauss linear"))
            div_block._set_child("div(phi,e)",                           Scalar(value="Gauss upwind"))
            div_block._set_child("div(phi,h)",                           Scalar(value="Gauss upwind"))
            div_block._set_child("div(phi,K)",                           Scalar(value="Gauss linear"))
            div_block._set_child("div(((rho*nuEff)*dev2(T(grad(U)))))",  Scalar(value="Gauss linear"))
        else:
            # Incompressible solvers (simpleFoam, pimpleFoam)
            # OpenFOAM 2312 requires dev2 here too
            div_block._set_child("div((nuEff*dev2(T(grad(U)))))", Scalar(value="Gauss linear"))
            # Legacy form kept for older OF versions / compatibility
            div_block._set_child("div((nu*dev(grad(U).T())))",    Scalar(value="Gauss linear"))

        # laplacianSchemes
        lapl_block = Dict_()
        lapl_block.set("default", lapl)

        # interpolationSchemes
        interp_block = Dict_()
        interp_block.set("default", interp)

        # snGradSchemes
        sngrad_block = Dict_()
        sngrad_block.set("default", "corrected")

        d = Dict_()
        d._set_child("ddtSchemes",          ddt_block)
        d._set_child("gradSchemes",         grad_block)
        d._set_child("divSchemes",          div_block)
        d._set_child("laplacianSchemes",    lapl_block)
        d._set_child("interpolationSchemes",interp_block)
        d._set_child("snGradSchemes",       sngrad_block)

        _write_field(case_dir, "system/fvSchemes", "dictionary", d)

    @staticmethod
    def write_fv_solution(case_dir: str, params: dict) -> None:
        """system/fvSolution — handles PISO, SIMPLE, PIMPLE."""
        p_solver  = params.get("p_solver",    "PCG")
        U_solver  = params.get("U_solver",    "PBiCGStab")
        p_tol     = params.get("p_tolerance", 1e-6)
        U_tol     = params.get("U_tolerance", 1e-5)
        p_reltol  = params.get("p_relTol",    0.01)
        U_reltol  = params.get("U_relTol",    0.0)
        nCorr     = params.get("nCorrectors", 2)
        nNonOrth  = params.get("nNonOrthogonalCorrectors", 0)
        app       = params.get("application", "icoFoam")

        _SIMPLE_SOLVERS = ("simpleFoam", "rhoSimpleFoam",
                           "buoyantSimpleFoam", "chtMultiRegionFoam")
        _PIMPLE_SOLVERS = ("pimpleFoam", "rhoPimpleFoam", "buoyantPimpleFoam")
        _COMPRESSIBLE   = ("rhoSimpleFoam", "rhoPimpleFoam",
                           "buoyantSimpleFoam", "buoyantPimpleFoam",
                           "chtMultiRegionFoam")
        _BUOYANT        = ("buoyantSimpleFoam", "buoyantPimpleFoam",
                           "chtMultiRegionFoam")
        _is_pimple = app in _PIMPLE_SOLVERS

        # ── helpers ───────────────────────────────────────────────────────
        def _p_solver_dict(reltol=None):
            d_ = Dict_()
            d_.set("solver", p_solver)
            if p_solver == "GAMG":
                d_.set("smoother", "GaussSeidel")
            else:
                d_.set("preconditioner", "DIC")
            d_.set("tolerance", p_tol)
            d_.set("relTol",    p_reltol if reltol is None else reltol)
            return d_

        def _scalar_dict(reltol=0.1):
            d_ = Dict_()
            d_.set("solver",         "PBiCGStab")
            d_.set("preconditioner", "DILU")
            d_.set("tolerance",      1e-6)
            d_.set("relTol",         reltol)
            return d_

        def _final_ref(base_key):
            """$base + relTol 0 reference block."""
            d_ = Dict_()
            d_.set(f"${base_key}", "")
            d_.set("relTol", 0)
            return d_

        # ── Build solvers sub-dict ────────────────────────────────────────
        solvers_d = Dict_()

        # --- p / p_rgh ---
        if app in _BUOYANT:
            # buoyant solvers use p_rgh as the primary pressure variable
            solvers_d._set_child("p_rgh",      _p_solver_dict())
            solvers_d._set_child("p_rghFinal", _final_ref("p_rgh") if _is_pimple else _p_solver_dict(reltol=0))
            # p is diagnostic (calculated from p_rgh)
            p_calc = Dict_()
            p_calc.set("solver",         "PCG")
            p_calc.set("preconditioner", "DIC")
            p_calc.set("tolerance",      1e-6)
            p_calc.set("relTol",         0)
            solvers_d._set_child("p", p_calc)
        else:
            solvers_d._set_child("p",      _p_solver_dict())
            solvers_d._set_child("pFinal", _final_ref("p") if _is_pimple else _p_solver_dict(reltol=0))

        # --- U / UFinal ---
        U_d = Dict_()
        U_d.set("solver",         U_solver)
        U_d.set("preconditioner", "DILU")
        U_d.set("tolerance",      U_tol)
        U_d.set("relTol",         U_reltol)
        solvers_d._set_child("U", U_d)
        if _is_pimple:
            solvers_d._set_child("UFinal", _final_ref("U"))

        # --- scalar fields (k, epsilon, omega, T, h, e) ---
        solvers_d._set_child("k",       _scalar_dict())
        solvers_d._set_child("epsilon", _scalar_dict())
        solvers_d._set_child("omega",   _scalar_dict())
        solvers_d._set_child("T",       _scalar_dict())
        if app in _COMPRESSIBLE:
            solvers_d._set_child("h",   _scalar_dict())
            solvers_d._set_child("e",   _scalar_dict())
            rho_d = Dict_()
            rho_d.set("solver",         "diagonal")
            solvers_d._set_child("rho", rho_d)
        if _is_pimple:
            solvers_d._set_child("kFinal",       _final_ref("k"))
            solvers_d._set_child("epsilonFinal", _final_ref("epsilon"))
            solvers_d._set_child("omegaFinal",   _final_ref("omega"))
            solvers_d._set_child("TFinal",       _final_ref("T"))
            if app in _COMPRESSIBLE:
                solvers_d._set_child("hFinal",   _final_ref("h"))
                solvers_d._set_child("eFinal",   _final_ref("e"))
                rho_final = Dict_()
                rho_final.set("solver", "diagonal")
                solvers_d._set_child("rhoFinal", rho_final)

        d = Dict_()
        d._set_child("solvers", solvers_d)

        # Algorithm block — reuse the classifier vars already defined above
        if app in _SIMPLE_SOLVERS:
            relax_U = params.get("relaxation_U", 0.7)
            relax_p = params.get("relaxation_p", 0.3)

            algo = Dict_()
            algo.set("nNonOrthogonalCorrectors", nNonOrth)
            algo.set("consistent",               "yes")
            if app in _BUOYANT:
                algo.set("pRefCell",  0)
                algo.set("pRefValue", 0)
            d._set_child("SIMPLE", algo)

            # relaxationFactors — only include the pressure var this solver uses
            fields_relax = Dict_()
            if app in _BUOYANT:
                fields_relax.set("p_rgh", relax_p)
                fields_relax.set("rho",   0.05)
            else:
                fields_relax.set("p",     relax_p)
                if app in _COMPRESSIBLE:
                    fields_relax.set("rho", 0.05)
            eqns_relax = Dict_()
            eqns_relax.set("U",       relax_U)
            eqns_relax.set("k",       0.7)
            eqns_relax.set("epsilon", 0.7)
            eqns_relax.set("omega",   0.7)
            eqns_relax.set("T",       0.5)
            if app in _COMPRESSIBLE:
                eqns_relax.set("h",   0.7)
                eqns_relax.set("e",   0.7)
            relax_d = Dict_()
            relax_d._set_child("fields",    fields_relax)
            relax_d._set_child("equations", eqns_relax)
            d._set_child("relaxationFactors", relax_d)

        elif app in _PIMPLE_SOLVERS:
            algo = Dict_()
            algo.set("nOuterCorrectors",         params.get("nOuterCorrectors", 2))
            algo.set("nCorrectors",              nCorr)
            algo.set("nNonOrthogonalCorrectors", nNonOrth)
            algo.set("pRefCell",                 0)
            algo.set("pRefValue",                0)
            d._set_child("PIMPLE", algo)

        else:  # unknown — generic PIMPLE fallback
            algo = Dict_()
            algo.set("nOuterCorrectors",         1)
            algo.set("nCorrectors",              nCorr)
            algo.set("nNonOrthogonalCorrectors", nNonOrth)
            algo.set("pRefCell",                 0)
            algo.set("pRefValue",                0)
            d._set_child("PIMPLE", algo)

        _write_field(case_dir, "system/fvSolution", "dictionary", d)

    # ── system/blockMeshDict ──────────────────────────────────────────────────

    @staticmethod
    def _build_block_mesh_body(params: dict, boundary_patches: list) -> Dict_:
        """Shared geometry + block builder; caller supplies boundary patches."""
        nx = params["nx"];  ny = params["ny"];  nz = params.get("nz", 1)
        Lx = params["Lx"];  Ly = params["Ly"];  Lz = params.get("Lz", 0.1)

        d = Dict_()
        d.set("scale", 1)

        # vertices — List_ of Vector nodes
        verts = List_(items=[
            Vector(components=(0,  0,  0)),
            Vector(components=(Lx, 0,  0)),
            Vector(components=(Lx, Ly, 0)),
            Vector(components=(0,  Ly, 0)),
            Vector(components=(0,  0,  Lz)),
            Vector(components=(Lx, 0,  Lz)),
            Vector(components=(Lx, Ly, Lz)),
            Vector(components=(0,  Ly, Lz)),
        ], multiline=True)
        d._set_child("vertices", verts)

        # blocks — OpenFOAM requires the hex entry as a flat keyword line:
        #   hex (0 1 2 3 4 5 6 7) (nx ny nz) simpleGrading (1 1 1)
        # The engine has no compound "hex" node, so we store it as a
        # verbatim Scalar string inside a multiline List_.
        hex_line = Scalar(value=f"hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)")
        blocks = List_(items=[hex_line], multiline=True)
        d._set_child("blocks", blocks)

        # edges — empty
        d._set_child("edges", List_(items=[], multiline=False))

        # boundary — KeyValueList
        kv = KeyValueList()
        for patch_name, patch_type, face_indices_list in boundary_patches:
            patch_d = Dict_()
            patch_d.set("type", patch_type)
            faces = List_(
                items=[
                    List_(items=[Scalar(value=i) for i in face_ids], multiline=False)
                    for face_ids in face_indices_list
                ],
                multiline=True,
            )
            patch_d._set_child("faces", faces)
            kv.entries.append((patch_name, patch_d))
        d._set_child("boundary", kv)

        return d

    @staticmethod
    def write_block_mesh_dict(case_dir: str, params: dict) -> None:
        """system/blockMeshDict — lid-driven cavity geometry."""
        patches = [
            ("movingWall",   "wall",  [[3, 7, 6, 2]]),
            ("fixedWalls",   "wall",  [[0, 4, 7, 3], [2, 6, 5, 1], [1, 5, 4, 0]]),
            ("frontAndBack", "empty", [[0, 3, 2, 1], [4, 5, 6, 7]]),
        ]
        body = DictionaryService._build_block_mesh_body(params, patches)
        _write_field(case_dir, "system/blockMeshDict", "dictionary", body)

    @staticmethod
    def write_block_mesh_dict_channel(case_dir: str, params: dict) -> None:
        """system/blockMeshDict — channel/pipe flow with inlet/outlet."""
        patches = [
            ("inlet",        "patch", [[0, 4, 7, 3]]),
            ("outlet",       "patch", [[1, 2, 6, 5]]),
            ("walls",        "wall",  [[0, 1, 5, 4], [3, 7, 6, 2]]),
            ("frontAndBack", "empty", [[0, 3, 2, 1], [4, 5, 6, 7]]),
        ]
        body = DictionaryService._build_block_mesh_body(params, patches)
        _write_field(case_dir, "system/blockMeshDict", "dictionary", body)

    # ── constant/ ─────────────────────────────────────────────────────────────

    @staticmethod
    def write_block_mesh_dict_buoyant(case_dir: str, params: dict) -> None:
        """system/blockMeshDict — buoyant cavity with hotWall/coldWall/walls/frontAndBack."""
        patches = [
            ("hotWall",     "wall",  [[3, 7, 6, 2]]),
            ("coldWall",    "wall",  [[1, 5, 4, 0]]),
            ("walls",       "wall",  [[0, 4, 7, 3], [2, 6, 5, 1]]),
            ("frontAndBack","empty", [[0, 3, 2, 1], [4, 5, 6, 7]]),
        ]
        body = DictionaryService._build_block_mesh_body(params, patches)
        _write_field(case_dir, "system/blockMeshDict", "dictionary", body)

    @staticmethod
    def write_region_properties(case_dir: str, params: dict) -> None:
        """constant/regionProperties — required by chtMultiRegionFoam.
        OF2312 regionProperties constructor calls lookup("regions") and reads
        it as a primitive ITstream of (type (name ...) type (name ...)) pairs.
        Must be written as a single flat list, NOT a sub-dictionary."""
        fluid_regions = params.get("fluid_regions", ["fluid"])
        solid_regions = params.get("solid_regions", ["solid"])

        fluid_str = " ".join(fluid_regions)
        solid_str = " ".join(solid_regions)
        # Write the file manually — the dict engine cannot represent this
        # mixed-primitive format without producing a sub-dict node.
        full_path = os.path.join(case_dir, "constant", "regionProperties")
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        content = f"""\
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "constant";
    object      regionProperties;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

regions
(
    fluid  ({fluid_str})
    solid  ({solid_str})
);

// ************************************************************************* //
"""
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def write_transport_properties(case_dir: str, params: dict) -> None:
        """constant/transportProperties — Newtonian."""
        nu  = params.get("nu",  1e-5)
        rho = params.get("rho", 1.0)
        d = Dict_()
        d.set("transportModel", "Newtonian")
        d.set("nu",  nu)
        d.set("rho", rho)
        _write_field(case_dir, "constant/transportProperties", "dictionary", d)

    @staticmethod
    def write_transport_properties_laplacian(case_dir: str, params: dict) -> None:
        """constant/transportProperties — laplacianFoam (only DT)."""
        alpha = params.get("alpha", 1e-5)
        d = Dict_()
        d.set("DT", alpha)
        _write_field(case_dir, "constant/transportProperties", "dictionary", d)

    @staticmethod
    def write_turbulence_properties(case_dir: str, params: dict) -> None:
        """constant/turbulenceProperties."""
        turb      = params.get("turbulence", "laminar")
        ras_model = params.get("ras_model",  "kEpsilon")
        d = Dict_()
        if turb == "laminar":
            d.set("simulationType", "laminar")
        else:
            d.set("simulationType", "RAS")
            ras = Dict_()
            ras.set("RASModel",   ras_model)
            ras.set("turbulence", "on")
            ras.set("printCoeffs","on")
            d._set_child("RAS", ras)
        _write_field(case_dir, "constant/turbulenceProperties", "dictionary", d)

    @staticmethod
    def write_thermophysical_properties(case_dir: str, params: dict) -> None:
        """constant/thermophysicalProperties — Boussinesq for buoyantSimpleFoam."""
        Cp    = params.get("Cp",    1005.0)
        kappa = params.get("kappa", 0.025)
        rho   = params.get("rho",   1.2)
        nu    = params.get("nu",    1e-5)
        mu    = nu * rho
        Pr    = mu * Cp / kappa if kappa > 0 else 0.7
        T0    = params.get("T_cold", 293.0)
        beta  = params.get("beta",   3e-3)

        d = Dict_()

        thermo_type = Dict_()
        thermo_type.set("type",           "heRhoThermo")
        thermo_type.set("mixture",        "pureMixture")
        thermo_type.set("transport",      "const")
        thermo_type.set("thermo",         "hConst")
        thermo_type.set("equationOfState","Boussinesq")
        thermo_type.set("specie",         "specie")
        thermo_type.set("energy",         "sensibleEnthalpy")
        d._set_child("thermoType", thermo_type)

        mixture = Dict_()

        specie_d = Dict_()
        specie_d.set("molWeight", 28.9)
        mixture._set_child("specie", specie_d)

        eos = Dict_()
        eos.set("rho0", rho)
        eos.set("T0",   T0)
        eos.set("beta", beta)
        mixture._set_child("equationOfState", eos)

        thermo_d = Dict_()
        thermo_d.set("Cp", Cp)
        thermo_d.set("Hf", 0)
        mixture._set_child("thermodynamics", thermo_d)

        transport_d = Dict_()
        transport_d.set("mu", float(f"{mu:.6e}"))
        transport_d.set("Pr", round(Pr, 4))
        mixture._set_child("transport", transport_d)

        d._set_child("mixture", mixture)
        _write_field(case_dir, "constant/thermophysicalProperties", "dictionary", d)

    @staticmethod
    def write_g_file(case_dir: str, params: dict) -> None:
        """constant/g — gravity vector."""
        g = params.get("g", 9.81)
        d = Dict_()
        d.set("dimensions", Dimensioned(dims=(0, 1, -2, 0, 0, 0, 0), value=Scalar(value="")))
        d.set("value", Vector(components=(0, -g, 0)))
        _write_field(case_dir, "constant/g", "uniformDimensionedVectorField", d)

    # ── 0/ field files ────────────────────────────────────────────────────────

    @staticmethod
    def write_U_cavity(case_dir: str, params: dict) -> None:
        """0/U — lid-driven cavity."""
        Ulid = params.get("lid_velocity", 1.0)
        Uint = params.get("internal_field_U", [0, 0, 0])
        ux, uy, uz = Uint

        d = Dict_()
        d.set("dimensions",    Dimensioned(dims=(0, 1, -1, 0, 0, 0, 0), value=Scalar(value="")))
        d.set("internalField", FieldValue(kind="uniform", value=Vector(components=(ux, uy, uz))))

        bf = Dict_()

        mw = Dict_()
        mw.set("type",  "fixedValue")
        mw.set("value", FieldValue(kind="uniform", value=Vector(components=(Ulid, 0, 0))))
        bf._set_child("movingWall", mw)

        fw = Dict_()
        fw.set("type", "noSlip")
        bf._set_child("fixedWalls", fw)

        fab = Dict_()
        fab.set("type", "empty")
        bf._set_child("frontAndBack", fab)

        d._set_child("boundaryField", bf)
        _write_field(case_dir, "0/U", "volVectorField", d)

    @staticmethod
    def write_U_channel(case_dir: str, params: dict) -> None:
        """0/U — channel flow (uniform or parabolic inlet)."""
        U_inlet = params.get("U_inlet",        1.0)
        profile = params.get("inlet_profile",  "uniform")

        d = Dict_()
        d.set("dimensions",    Dimensioned(dims=(0, 1, -1, 0, 0, 0, 0), value=Scalar(value="")))
        d.set("internalField", FieldValue(kind="uniform", value=Vector(components=(U_inlet, 0, 0))))

        bf = Dict_()

        inlet_d = Dict_()
        if profile == "parabolic":
            Ly = params["Ly"]
            # codedFixedValue — we store code as a Scalar (multi-line string)
            # The parser round-trips it; we build it as raw text nodes.
            inlet_d.set("type", "codedFixedValue")
            inlet_d.set("value", FieldValue(kind="uniform", value=Vector(components=(U_inlet, 0, 0))))
            inlet_d.set("name",  "parabolicInlet")
            # Embed the C++ code as a raw Scalar string
            code = (
                f"const fvPatch& p = this->patch();\n"
                f"        vectorField& field = *this;\n"
                f"        forAll(p.Cf(), i)\n"
                f"        {{\n"
                f"            scalar y = p.Cf()[i].y();\n"
                f"            scalar H = {Ly};\n"
                f"            field[i] = vector(4*{U_inlet}*y*(H-y)/(H*H), 0, 0);\n"
                f"        }}"
            )
            inlet_d.set("code", f"#{{ {code} #}}")
        else:
            inlet_d.set("type",  "fixedValue")
            inlet_d.set("value", FieldValue(kind="uniform", value=Vector(components=(U_inlet, 0, 0))))
        bf._set_child("inlet", inlet_d)

        outlet_d = Dict_()
        outlet_d.set("type", "zeroGradient")
        bf._set_child("outlet", outlet_d)

        walls_d = Dict_()
        walls_d.set("type", "noSlip")
        bf._set_child("walls", walls_d)

        fab = Dict_()
        fab.set("type", "empty")
        bf._set_child("frontAndBack", fab)

        d._set_child("boundaryField", bf)
        _write_field(case_dir, "0/U", "volVectorField", d)

    @staticmethod
    def write_U_buoyant(case_dir: str, params: dict) -> None:
        """0/U — buoyant case (all walls no-slip)."""
        d = Dict_()
        d.set("dimensions",    Dimensioned(dims=(0, 1, -1, 0, 0, 0, 0), value=Scalar(value="")))
        d.set("internalField", FieldValue(kind="uniform", value=Vector(components=(0, 0, 0))))

        bf = Dict_()
        for patch in ("hotWall", "coldWall", "walls"):
            p = Dict_(); p.set("type", "noSlip")
            bf._set_child(patch, p)
        fab = Dict_(); fab.set("type", "empty")
        bf._set_child("frontAndBack", fab)

        d._set_child("boundaryField", bf)
        _write_field(case_dir, "0/U", "volVectorField", d)

    @staticmethod
    def write_p_cavity(case_dir: str, params: dict) -> None:
        """0/p — cavity (zero-gradient everywhere)."""
        p0 = params.get("internal_field_p", 0.0)
        d = Dict_()
        d.set("dimensions",    Dimensioned(dims=(0, 2, -2, 0, 0, 0, 0), value=Scalar(value="")))
        d.set("internalField", FieldValue(kind="uniform", value=Scalar(value=p0)))

        bf = Dict_()
        for patch in ("movingWall", "fixedWalls"):
            p = Dict_(); p.set("type", "zeroGradient")
            bf._set_child(patch, p)
        fab = Dict_(); fab.set("type", "empty")
        bf._set_child("frontAndBack", fab)

        d._set_child("boundaryField", bf)
        _write_field(case_dir, "0/p", "volScalarField", d)

    @staticmethod
    def write_p_channel(case_dir: str, params: dict) -> None:
        """0/p — channel flow (fixed outlet, optional fixed inlet)."""
        p_outlet = params.get("p_outlet",   0.0)
        p_inlet  = params.get("p_inlet_val", None)
        app      = params.get("application", "")
        _RHO_CHANNEL = ("rhoSimpleFoam", "rhoPimpleFoam")
        # compressible rho-solvers need thermodynamic pressure [Pa] = [kg m-1 s-2]
        dims = (1, -1, -2, 0, 0, 0, 0) if app in _RHO_CHANNEL else (0, 2, -2, 0, 0, 0, 0)
        # sensible default pressure for compressible: 101325 Pa
        if app in _RHO_CHANNEL and p_outlet == 0.0:
            p_outlet = params.get("p_outlet", 101325.0)

        d = Dict_()
        d.set("dimensions",    Dimensioned(dims=dims, value=Scalar(value="")))
        d.set("internalField", FieldValue(kind="uniform", value=Scalar(value=p_outlet)))

        bf = Dict_()
        inlet_d = Dict_()
        if p_inlet is not None:
            inlet_d.set("type",  "fixedValue")
            inlet_d.set("value", FieldValue(kind="uniform", value=Scalar(value=p_inlet)))
        else:
            inlet_d.set("type", "zeroGradient")
        bf._set_child("inlet", inlet_d)

        outlet_d = Dict_()
        outlet_d.set("type",  "fixedValue")
        outlet_d.set("value", FieldValue(kind="uniform", value=Scalar(value=p_outlet)))
        bf._set_child("outlet", outlet_d)

        walls_d = Dict_(); walls_d.set("type", "zeroGradient")
        bf._set_child("walls", walls_d)

        fab = Dict_(); fab.set("type", "empty")
        bf._set_child("frontAndBack", fab)

        d._set_child("boundaryField", bf)
        _write_field(case_dir, "0/p", "volScalarField", d)

    @staticmethod
    def write_p_rgh_buoyant(case_dir: str, params: dict) -> None:
        """0/p_rgh — buoyantSimpleFoam."""
        d = Dict_()
        d.set("dimensions",    Dimensioned(dims=(1, -1, -2, 0, 0, 0, 0), value=Scalar(value="")))
        d.set("internalField", FieldValue(kind="uniform", value=Scalar(value=0)))

        bf = Dict_()
        for patch in ("hotWall", "coldWall", "walls"):
            p = Dict_()
            p.set("type",  "fixedFluxPressure")
            p.set("value", FieldValue(kind="uniform", value=Scalar(value=0)))
            bf._set_child(patch, p)
        fab = Dict_(); fab.set("type", "empty")
        bf._set_child("frontAndBack", fab)

        d._set_child("boundaryField", bf)
        _write_field(case_dir, "0/p_rgh", "volScalarField", d)

    @staticmethod
    def write_p_buoyant(case_dir: str, params: dict) -> None:
        """0/p — buoyantSimpleFoam (calculated from p_rgh)."""
        d = Dict_()
        d.set("dimensions",    Dimensioned(dims=(1, -1, -2, 0, 0, 0, 0), value=Scalar(value="")))
        d.set("internalField", FieldValue(kind="uniform", value=Scalar(value=0)))

        bf = Dict_()
        for patch in ("hotWall", "coldWall", "walls"):
            p = Dict_()
            p.set("type",  "calculated")
            p.set("value", FieldValue(kind="uniform", value=Scalar(value=0)))
            bf._set_child(patch, p)
        fab = Dict_(); fab.set("type", "empty")
        bf._set_child("frontAndBack", fab)

        d._set_child("boundaryField", bf)
        _write_field(case_dir, "0/p", "volScalarField", d)

    @staticmethod
    def write_T_buoyant(case_dir: str, params: dict) -> None:
        """0/T — buoyantSimpleFoam."""
        T_hot  = params.get("T_hot",  350.0)
        T_cold = params.get("T_cold", 293.0)
        T_init = params.get("T_init", T_cold)

        d = Dict_()
        d.set("dimensions",    Dimensioned(dims=(0, 0, 0, 1, 0, 0, 0), value=Scalar(value="")))
        d.set("internalField", FieldValue(kind="uniform", value=Scalar(value=T_init)))

        bf = Dict_()
        hw = Dict_(); hw.set("type", "fixedValue"); hw.set("value", FieldValue(kind="uniform", value=Scalar(value=T_hot)))
        bf._set_child("hotWall", hw)
        cw = Dict_(); cw.set("type", "fixedValue"); cw.set("value", FieldValue(kind="uniform", value=Scalar(value=T_cold)))
        bf._set_child("coldWall", cw)
        wl = Dict_(); wl.set("type", "zeroGradient")
        bf._set_child("walls", wl)
        fab = Dict_(); fab.set("type", "empty")
        bf._set_child("frontAndBack", fab)

        d._set_child("boundaryField", bf)
        _write_field(case_dir, "0/T", "volScalarField", d)

    @staticmethod
    def write_T_channel(case_dir: str, params: dict) -> None:
        """0/T — compressible channel (rhoSimpleFoam / rhoPimpleFoam)."""
        T_inlet = params.get("T_inlet", 300.0)
        T_init  = params.get("T_init",  T_inlet)

        d = Dict_()
        d.set("dimensions",    Dimensioned(dims=(0, 0, 0, 1, 0, 0, 0), value=Scalar(value="")))
        d.set("internalField", FieldValue(kind="uniform", value=Scalar(value=T_init)))

        bf = Dict_()
        inlet_d = Dict_()
        inlet_d.set("type",  "fixedValue")
        inlet_d.set("value", FieldValue(kind="uniform", value=Scalar(value=T_inlet)))
        bf._set_child("inlet", inlet_d)

        outlet_d = Dict_(); outlet_d.set("type", "zeroGradient")
        bf._set_child("outlet", outlet_d)

        walls_d = Dict_(); walls_d.set("type", "zeroGradient")
        bf._set_child("walls", walls_d)

        fab = Dict_(); fab.set("type", "empty")
        bf._set_child("frontAndBack", fab)

        d._set_child("boundaryField", bf)
        _write_field(case_dir, "0/T", "volScalarField", d)

    @staticmethod
    def write_T_laplacian(case_dir: str, params: dict) -> None:
        """0/T — laplacianFoam."""
        T_hot  = params.get("T_hot",  500.0)
        T_cold = params.get("T_cold", 300.0)

        d = Dict_()
        d.set("dimensions",    Dimensioned(dims=(0, 0, 0, 1, 0, 0, 0), value=Scalar(value="")))
        d.set("internalField", FieldValue(kind="uniform", value=Scalar(value=T_cold)))

        bf = Dict_()
        for name, T_val in [("left", T_hot), ("right", T_cold)]:
            p = Dict_()
            p.set("type",  "fixedValue")
            p.set("value", FieldValue(kind="uniform", value=Scalar(value=T_val)))
            bf._set_child(name, p)
        for name in ("top", "bottom"):
            p = Dict_(); p.set("type", "zeroGradient")
            bf._set_child(name, p)
        fab = Dict_(); fab.set("type", "empty")
        bf._set_child("frontAndBack", fab)

        d._set_child("boundaryField", bf)
        _write_field(case_dir, "0/T", "volScalarField", d)

    @staticmethod
    def write_turbulence_initial_fields(case_dir: str, params: dict) -> None:
        """Write 0/k and 0/epsilon or 0/omega for RAS turbulence."""
        turb = params.get("turbulence", "laminar")
        if turb == "laminar":
            return

        ras   = params.get("ras_model", "kEpsilon")
        nu    = params.get("nu", 1e-5)
        U_ref = params.get("lid_velocity", params.get("U_inlet", 1.0))
        I     = 0.05                                   # 5% turbulence intensity
        k0    = 1.5 * (U_ref * I) ** 2
        Cmu   = 0.09
        L_ref = params.get("Lx", 1.0) * 0.07
        eps0  = Cmu ** 0.75 * k0 ** 1.5 / L_ref
        omega0 = k0 / (Cmu * L_ref ** 2 * eps0 / k0) if eps0 > 0 else k0 / (nu * 6)

        # Determine wall patches based on solver type
        app = params.get("application", "")
        _BUOYANT_APPS = ("buoyantSimpleFoam", "buoyantPimpleFoam", "chtMultiRegionFoam")
        _is_buoyant = app in _BUOYANT_APPS

        if _is_buoyant:
            wall_patches = ["hotWall", "coldWall", "walls"]
            has_inlet_outlet = False
        else:
            wall_patches = ["movingWall", "fixedWalls", "walls"]
            has_inlet_outlet = True

        # ── k ──────────────────────────────────────────────────────────────
        k_d = Dict_()
        k_d.set("dimensions",    Dimensioned(dims=(0, 2, -2, 0, 0, 0, 0), value=Scalar(value="")))
        k_d.set("internalField", FieldValue(kind="uniform", value=Scalar(value=round(k0, 6))))

        k_bf = Dict_()
        for patch in wall_patches:
            p = Dict_()
            p.set("type",  "kqRWallFunction")
            p.set("value", FieldValue(kind="uniform", value=Scalar(value=round(k0, 6))))
            k_bf._set_child(patch, p)
        if has_inlet_outlet:
            inlet_k = Dict_()
            inlet_k.set("type",  "fixedValue")
            inlet_k.set("value", FieldValue(kind="uniform", value=Scalar(value=round(k0, 6))))
            k_bf._set_child("inlet", inlet_k)
            outlet_k = Dict_(); outlet_k.set("type", "zeroGradient")
            k_bf._set_child("outlet", outlet_k)
        fab_k = Dict_(); fab_k.set("type", "empty")
        k_bf._set_child("frontAndBack", fab_k)
        k_d._set_child("boundaryField", k_bf)
        _write_field(case_dir, "0/k", "volScalarField", k_d)

        # ── epsilon or omega ───────────────────────────────────────────────
        if ras in ("kEpsilon", "realizableKE", "RNGkEpsilon"):
            e_d = Dict_()
            e_d.set("dimensions",    Dimensioned(dims=(0, 2, -3, 0, 0, 0, 0), value=Scalar(value="")))
            e_d.set("internalField", FieldValue(kind="uniform", value=Scalar(value=round(eps0, 6))))

            e_bf = Dict_()
            for patch in wall_patches:
                p = Dict_()
                p.set("type",  "epsilonWallFunction")
                p.set("value", FieldValue(kind="uniform", value=Scalar(value=round(eps0, 6))))
                e_bf._set_child(patch, p)
            if has_inlet_outlet:
                inlet_e = Dict_()
                inlet_e.set("type",  "fixedValue")
                inlet_e.set("value", FieldValue(kind="uniform", value=Scalar(value=round(eps0, 6))))
                e_bf._set_child("inlet", inlet_e)
                outlet_e = Dict_(); outlet_e.set("type", "zeroGradient")
                e_bf._set_child("outlet", outlet_e)
            fab_e = Dict_(); fab_e.set("type", "empty")
            e_bf._set_child("frontAndBack", fab_e)
            e_d._set_child("boundaryField", e_bf)
            _write_field(case_dir, "0/epsilon", "volScalarField", e_d)

        else:  # kOmegaSST
            o_d = Dict_()
            o_d.set("dimensions",    Dimensioned(dims=(0, 0, -1, 0, 0, 0, 0), value=Scalar(value="")))
            o_d.set("internalField", FieldValue(kind="uniform", value=Scalar(value=round(omega0, 4))))

            o_bf = Dict_()
            for patch in wall_patches:
                p = Dict_()
                p.set("type",  "omegaWallFunction")
                p.set("value", FieldValue(kind="uniform", value=Scalar(value=round(omega0, 4))))
                o_bf._set_child(patch, p)
            if has_inlet_outlet:
                inlet_o = Dict_()
                inlet_o.set("type",  "fixedValue")
                inlet_o.set("value", FieldValue(kind="uniform", value=Scalar(value=round(omega0, 4))))
                o_bf._set_child("inlet", inlet_o)
                outlet_o = Dict_(); outlet_o.set("type", "zeroGradient")
                o_bf._set_child("outlet", outlet_o)
            fab_o = Dict_(); fab_o.set("type", "empty")
            o_bf._set_child("frontAndBack", fab_o)
            o_d._set_child("boundaryField", o_bf)
            _write_field(case_dir, "0/omega", "volScalarField", o_d)

    # ── patch_dict — load → modify → write ───────────────────────────────────

    @staticmethod
    def patch_dict(path: str, updates: dict) -> None:
        """
        Load an existing OpenFOAM dictionary from disk, apply dotted-path
        updates, and write it back.  Preserves existing entries and comments.

        Example:
            DictionaryService.patch_dict(
                "of_cases/default/system/controlDict",
                {"deltaT": 0.001, "endTime": 2.0}
            )
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"patch_dict: file not found: {path}")
        root = parse_file(path)
        for dotted_key, value in updates.items():
            root.set(dotted_key, value)
        from dict_engine import serialize
        text = serialize(root, with_banner=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)