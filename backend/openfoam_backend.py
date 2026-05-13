"""
OpenFOAM Backend — Pure OpenFOAM execution engine.

Architecture:
  1. User submits case params via REST API (frontend form)
  2. We write valid OpenFOAM case files (0/, constant/, system/)
  3. Run blockMesh then the solver via subprocess
  4. Parse postProcessing/ and time directories for results
  5. Return field data to frontend for visualization

Supports: icoFoam, simpleFoam, pisoFoam, buoyantSimpleFoam, laplacianFoam
"""

import os, sys, subprocess, shutil, json, re, time, threading, glob
import numpy as np
from pathlib import Path

# ── OpenFOAM environment ──────────────────────────────────────────
def find_openfoam():
    """Locate OpenFOAM — checks of_config.json first (written by detect_openfoam.py),
    then falls back to scanning common paths."""
    here = os.path.dirname(os.path.abspath(__file__))
    cfg  = os.path.join(here, "of_config.json")

    # 1. Config file (most reliable — written by detect_openfoam.py)
    if os.path.exists(cfg):
        import json
        try:
            d = json.load(open(cfg))
            bashrc = d.get("OF_BASHRC","")
            root   = d.get("OF_ROOT","")
            if bashrc and os.path.exists(bashrc):
                return root, bashrc
        except Exception:
            pass

    # 2. Already sourced in shell (WSL with OF in .bashrc)
    wm = os.environ.get("WM_PROJECT_DIR","")
    if wm:
        bashrc = os.path.join(wm, "etc", "bashrc")
        if os.path.exists(bashrc):
            return wm, bashrc

    # 3. Scan common install paths
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
    """Return environment dict with OpenFOAM sourced."""
    if OF_BASHRC is None:
        raise RuntimeError("OpenFOAM not found. Install OpenFOAM and ensure /opt/openfoamXX exists.")
    cmd = f'source "{OF_BASHRC}" && env'
    result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=30)
    env = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            env[k] = v
    return env

# Cache env (source bashrc is slow)
_of_env_cache = None
def get_of_env():
    global _of_env_cache
    if _of_env_cache is None:
        _of_env_cache = of_env()
    return _of_env_cache

def run_of_cmd(cmd, cwd, timeout=600, log_file=None):
    """Run an OpenFOAM command (blockMesh, icoFoam, etc.) with proper env."""
    env = get_of_env()
    full_cmd = f'source "{OF_BASHRC}" && cd "{cwd}" && {cmd}'
    proc = subprocess.Popen(
        ["bash", "-c", full_cmd],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, env=os.environ.copy()
    )
    output_lines = []
    for line in proc.stdout:
        output_lines.append(line)
        if log_file:
            with open(log_file, "a") as f:
                f.write(line)
    proc.wait(timeout=timeout)
    return proc.returncode, "".join(output_lines)


# ══════════════════════════════════════════════════════════════════
#  OpenFOAM File Writers  (one function per file)
# ══════════════════════════════════════════════════════════════════

OF_HEADER = '''\
FoamFile
{{
    version     2.0;
    format      ascii;
    class       {cls};
    object      {obj};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
'''

def _header(cls, obj):
    return OF_HEADER.format(cls=cls, obj=obj)


def write_blockMeshDict(case_dir, params):
    """
    Write system/blockMeshDict from user params.
    params keys: nx, ny, nz, Lx, Ly, Lz
    """
    nx = params["nx"]; ny = params["ny"]; nz = params.get("nz", 1)
    Lx = params["Lx"]; Ly = params["Ly"]; Lz = params.get("Lz", 0.1)

    content = _header("dictionary", "blockMeshDict") + f"""
scale   1;

vertices
(
    (0   0   0  )   // 0
    ({Lx} 0   0  )   // 1
    ({Lx} {Ly}  0  )   // 2
    (0   {Ly}  0  )   // 3
    (0   0   {Lz} )   // 4
    ({Lx} 0   {Lz} )   // 5
    ({Lx} {Ly}  {Lz} )   // 6
    (0   {Ly}  {Lz} )   // 7
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
);

edges
();

boundary
(
    movingWall
    {{
        type wall;
        faces ((3 7 6 2));
    }}
    fixedWalls
    {{
        type wall;
        faces ((0 4 7 3) (2 6 5 1) (1 5 4 0));
    }}
    frontAndBack
    {{
        type empty;
        faces ((0 3 2 1) (4 5 6 7));
    }}
);
"""
    _write(case_dir, "system/blockMeshDict", content)


def write_blockMeshDict_channel(case_dir, params):
    """blockMeshDict for channel/pipe flow with inlet/outlet."""
    nx=params["nx"]; ny=params["ny"]; nz=params.get("nz",1)
    Lx=params["Lx"]; Ly=params["Ly"]; Lz=params.get("Lz",0.1)

    content = _header("dictionary","blockMeshDict") + f"""
scale   1;
vertices
(
    (0   0   0  )
    ({Lx} 0   0  )
    ({Lx} {Ly}  0  )
    (0   {Ly}  0  )
    (0   0   {Lz} )
    ({Lx} 0   {Lz} )
    ({Lx} {Ly}  {Lz} )
    (0   {Ly}  {Lz} )
);
blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
);
edges ();
boundary
(
    inlet
    {{
        type patch;
        faces ((0 4 7 3));
    }}
    outlet
    {{
        type patch;
        faces ((1 2 6 5));
    }}
    walls
    {{
        type wall;
        faces ((0 1 5 4) (3 7 6 2));
    }}
    frontAndBack
    {{
        type empty;
        faces ((0 3 2 1) (4 5 6 7));
    }}
);
"""
    _write(case_dir, "system/blockMeshDict", content)


def write_U_cavity(case_dir, params):
    """
    0/U for lid-driven cavity.
    params: lid_velocity (float), internal_field=[0,0,0]
    """
    Ulid = params.get("lid_velocity", 1.0)
    Uint = params.get("internal_field_U", [0, 0, 0])
    ux, uy, uz = Uint

    content = _header("volVectorField","U") + f"""
dimensions  [0 1 -1 0 0 0 0];

internalField   uniform ({ux} {uy} {uz});

boundaryField
{{
    movingWall
    {{
        type            fixedValue;
        value           uniform ({Ulid} 0 0);
    }}
    fixedWalls
    {{
        type            noSlip;
    }}
    frontAndBack
    {{
        type            empty;
    }}
}}
"""
    _write(case_dir, "0/U", content)


def write_U_channel(case_dir, params):
    """0/U for channel flow — parabolic or uniform inlet."""
    U_inlet   = params.get("U_inlet", 1.0)
    profile   = params.get("inlet_profile", "uniform")  # uniform|parabolic

    if profile == "parabolic":
        # OpenFOAM codedFixedValue for parabolic profile
        Ly = params["Ly"]
        inlet_bc = f"""
        type            codedFixedValue;
        value           uniform ({U_inlet} 0 0);
        name            parabolicInlet;
        code
        #{{
            const fvPatch& p = this->patch();
            vectorField& field = *this;
            forAll(p.Cf(), i)
            {{
                scalar y = p.Cf()[i].y();
                scalar H = {Ly};
                field[i] = vector(4*{U_inlet}*y*(H-y)/(H*H), 0, 0);
            }}
        #}};"""
    else:
        inlet_bc = f"""
        type            fixedValue;
        value           uniform ({U_inlet} 0 0);"""

    content = _header("volVectorField","U") + f"""
dimensions  [0 1 -1 0 0 0 0];

internalField   uniform ({U_inlet} 0 0);

boundaryField
{{
    inlet
    {{{inlet_bc}
    }}
    outlet
    {{
        type            zeroGradient;
    }}
    walls
    {{
        type            noSlip;
    }}
    frontAndBack
    {{
        type            empty;
    }}
}}
"""
    _write(case_dir, "0/U", content)


def write_p_cavity(case_dir, params):
    """0/p for cavity — one reference pressure at corner."""
    p0 = params.get("internal_field_p", 0.0)
    content = _header("volScalarField","p") + f"""
dimensions  [0 2 -2 0 0 0 0];

internalField   uniform {p0};

boundaryField
{{
    movingWall
    {{
        type            zeroGradient;
    }}
    fixedWalls
    {{
        type            zeroGradient;
    }}
    frontAndBack
    {{
        type            empty;
    }}
}}
"""
    _write(case_dir, "0/p", content)


def write_p_channel(case_dir, params):
    """0/p for channel — fixed outlet pressure."""
    p_outlet = params.get("p_outlet", 0.0)
    p_inlet  = params.get("p_inlet_val", None)

    inlet_bc = f"""
        type            fixedValue;
        value           uniform {p_inlet};""" if p_inlet is not None else """
        type            zeroGradient;"""

    content = _header("volScalarField","p") + f"""
dimensions  [0 2 -2 0 0 0 0];

internalField   uniform {p_outlet};

boundaryField
{{
    inlet
    {{{inlet_bc}
    }}
    outlet
    {{
        type            fixedValue;
        value           uniform {p_outlet};
    }}
    walls
    {{
        type            zeroGradient;
    }}
    frontAndBack
    {{
        type            empty;
    }}
}}
"""
    _write(case_dir, "0/p", content)


def write_T_buoyant(case_dir, params):
    """0/T for buoyantSimpleFoam — hot/cold walls."""
    T_hot  = params.get("T_hot",  350.0)
    T_cold = params.get("T_cold", 293.0)
    T_init = params.get("T_init", T_cold)
    content = _header("volScalarField","T") + f"""
dimensions  [0 0 0 1 0 0 0];

internalField   uniform {T_init};

boundaryField
{{
    hotWall
    {{
        type            fixedValue;
        value           uniform {T_hot};
    }}
    coldWall
    {{
        type            fixedValue;
        value           uniform {T_cold};
    }}
    walls
    {{
        type            zeroGradient;
    }}
    frontAndBack
    {{
        type            empty;
    }}
}}
"""
    _write(case_dir, "0/T", content)


def write_transportProperties(case_dir, params):
    """constant/transportProperties."""
    nu  = params.get("nu", 1e-5)
    rho = params.get("rho", 1.0)
    # For buoyant cases also write thermophysical properties
    content = _header("dictionary","transportProperties") + f"""
transportModel  Newtonian;

nu              {nu};

rho             {rho};
"""
    _write(case_dir, "constant/transportProperties", content)


def write_turbulenceProperties(case_dir, params):
    """constant/turbulenceProperties — handles laminar, RAS (k-eps, k-omega SST)."""
    turb = params.get("turbulence", "laminar")
    ras_model = params.get("ras_model", "kEpsilon")

    if turb == "laminar":
        sim_type = "laminar"
        ras_block = ""
    else:
        sim_type = "RAS"
        ras_block = f"""
RAS
{{
    RASModel        {ras_model};
    turbulence      on;
    printCoeffs     on;
}}"""

    content = _header("dictionary","turbulenceProperties") + f"""
simulationType  {sim_type};
{ras_block}
"""
    _write(case_dir, "constant/turbulenceProperties", content)


def write_turbulence_initial_fields(case_dir, params):
    """Write 0/k, 0/epsilon, 0/omega for RAS turbulence."""
    turb = params.get("turbulence","laminar")
    if turb == "laminar":
        return
    ras = params.get("ras_model","kEpsilon")
    nu = params.get("nu",1e-5)
    U_ref = params.get("lid_velocity", params.get("U_inlet", 1.0))
    # Turbulence intensity 5%
    I = 0.05
    k0    = 1.5 * (U_ref * I)**2
    Cmu   = 0.09
    L_ref = params.get("Lx",1.0) * 0.07
    eps0  = Cmu**0.75 * k0**1.5 / L_ref
    omega0= k0 / (Cmu * L_ref**2 * eps0 / k0) if eps0>0 else k0 / (nu*6)

    wall_bc_k = """
        type            kqRWallFunction;
        value           $internalField;"""
    wall_bc_e = """
        type            epsilonWallFunction;
        value           $internalField;"""
    wall_bc_o = """
        type            omegaWallFunction;
        value           $internalField;"""

    # k
    k_content = _header("volScalarField","k") + f"""
dimensions  [0 2 -2 0 0 0 0];
internalField   uniform {k0:.6f};
boundaryField
{{
    movingWall   {{ type kqRWallFunction; value uniform {k0:.6f}; }}
    fixedWalls   {{ type kqRWallFunction; value uniform {k0:.6f}; }}
    inlet        {{ type fixedValue;       value uniform {k0:.6f}; }}
    outlet       {{ type zeroGradient; }}
    walls        {{ type kqRWallFunction; value uniform {k0:.6f}; }}
    frontAndBack {{ type empty; }}
}}
"""
    _write(case_dir, "0/k", k_content)

    if ras in ("kEpsilon","realizableKE","RNGkEpsilon"):
        eps_content = _header("volScalarField","epsilon") + f"""
dimensions  [0 2 -3 0 0 0 0];
internalField   uniform {eps0:.6f};
boundaryField
{{
    movingWall   {{ type epsilonWallFunction; value uniform {eps0:.6f}; }}
    fixedWalls   {{ type epsilonWallFunction; value uniform {eps0:.6f}; }}
    inlet        {{ type fixedValue;          value uniform {eps0:.6f}; }}
    outlet       {{ type zeroGradient; }}
    walls        {{ type epsilonWallFunction; value uniform {eps0:.6f}; }}
    frontAndBack {{ type empty; }}
}}
"""
        _write(case_dir, "0/epsilon", eps_content)
    else:  # kOmegaSST
        om_content = _header("volScalarField","omega") + f"""
dimensions  [0 0 -1 0 0 0 0];
internalField   uniform {omega0:.4f};
boundaryField
{{
    movingWall   {{ type omegaWallFunction; value uniform {omega0:.4f}; }}
    fixedWalls   {{ type omegaWallFunction; value uniform {omega0:.4f}; }}
    inlet        {{ type fixedValue;        value uniform {omega0:.4f}; }}
    outlet       {{ type zeroGradient; }}
    walls        {{ type omegaWallFunction; value uniform {omega0:.4f}; }}
    frontAndBack {{ type empty; }}
}}
"""
        _write(case_dir, "0/omega", om_content)


def write_controlDict(case_dir, params):
    """system/controlDict from user params."""
    app         = params.get("application", "icoFoam")
    startTime   = params.get("startTime",   0.0)
    endTime     = params.get("endTime",     0.5)
    deltaT      = params.get("deltaT",      0.005)
    writeCtrl   = params.get("writeControl","timeStep")
    writeInt    = params.get("writeInterval",20)
    purgeWrite  = params.get("purgeWrite",  0)
    runTimeMod  = params.get("runTimeModifiable","true")

    content = _header("dictionary","controlDict") + f"""
application     {app};

startFrom       startTime;

startTime       {startTime};

stopAt          endTime;

endTime         {endTime};

deltaT          {deltaT};

writeControl    {writeCtrl};

writeInterval   {writeInt};

purgeWrite      {purgeWrite};

writeFormat     ascii;

writePrecision  8;

writeCompression off;

timeFormat      general;

timePrecision   6;

runTimeModifiable {runTimeMod};
"""
    _write(case_dir, "system/controlDict", content)


def write_fvSchemes(case_dir, params):
    """system/fvSchemes."""
    ddt   = params.get("ddtScheme",     "Euler")
    grad  = params.get("gradScheme",    "Gauss linear")
    div_U = params.get("divScheme_U",   "Gauss linearUpwind grad(U)")
    lapl  = params.get("laplacianScheme","Gauss linear corrected")
    interp= params.get("interpolationScheme","linear")

    # simpleFoam/buoyantSimpleFoam need steady ddt
    app = params.get("application","icoFoam")
    if app in ("simpleFoam","buoyantSimpleFoam","buoyantPimpleFoam"):
        ddt = "steadyState"

    content = _header("dictionary","fvSchemes") + f"""
ddtSchemes
{{
    default         {ddt};
}}

gradSchemes
{{
    default         {grad};
    grad(p)         {grad};
    grad(U)         {grad};
}}

divSchemes
{{
    default         none;
    div(phi,U)      {div_U};
    div(phi,k)      Gauss upwind;
    div(phi,epsilon) Gauss upwind;
    div(phi,omega)  Gauss upwind;
    div(phi,T)      Gauss upwind;
    div((nuEff*dev(T(grad(U))))) Gauss linear;
    div((nu*dev(grad(U).T()))) Gauss linear;
}}

laplacianSchemes
{{
    default         {lapl};
}}

interpolationSchemes
{{
    default         {interp};
}}

snGradSchemes
{{
    default         corrected;
}}
"""
    _write(case_dir, "system/fvSchemes", content)


def write_fvSolution(case_dir, params):
    """system/fvSolution — handles PISO, SIMPLE, PIMPLE."""
    p_solver   = params.get("p_solver",    "PCG")
    U_solver   = params.get("U_solver",    "PBiCGStab")
    p_tol      = params.get("p_tolerance", 1e-6)
    U_tol      = params.get("U_tolerance", 1e-5)
    p_reltol   = params.get("p_relTol",    0.01)
    U_reltol   = params.get("U_relTol",    0.0)
    nCorr      = params.get("nCorrectors", 2)
    nNonOrth   = params.get("nNonOrthogonalCorrectors", 0)
    app        = params.get("application", "icoFoam")

    if p_solver == "PCG":
        p_precond = "DIC"
    elif p_solver == "GAMG":
        p_precond = "GAMG"
    else:
        p_precond = "DIC"

    if p_solver == "GAMG":
        p_block = f"""
    p
    {{
        solver          GAMG;
        tolerance       {p_tol};
        relTol          {p_reltol};
        smoother        GaussSeidel;
    }}
    pFinal
    {{
        $p;
        relTol          0;
    }}"""
    else:
        p_block = f"""
    p
    {{
        solver          {p_solver};
        preconditioner  {p_precond};
        tolerance       {p_tol};
        relTol          {p_reltol};
    }}
    pFinal
    {{
        $p;
        relTol          0;
    }}"""

    algo_block = ""
    if app in ("icoFoam","pisoFoam"):
        algo_block = f"""
PISO
{{
    nCorrectors                 {nCorr};
    nNonOrthogonalCorrectors    {nNonOrth};
    pRefCell                    0;
    pRefValue                   0;
}}"""
    elif app in ("simpleFoam","buoyantSimpleFoam"):
        relax_U = params.get("relaxation_U", 0.7)
        relax_p = params.get("relaxation_p", 0.3)
        algo_block = f"""
SIMPLE
{{
    nNonOrthogonalCorrectors    {nNonOrth};
    pRefCell                    0;
    pRefValue                   0;
    consistent                  yes;
}}

relaxationFactors
{{
    fields
    {{
        p               {relax_p};
    }}
    equations
    {{
        U               {relax_U};
        k               0.7;
        epsilon         0.7;
        omega           0.7;
        T               0.5;
    }}
}}"""
    else:  # pimpleFoam
        algo_block = f"""
PIMPLE
{{
    nOuterCorrectors            2;
    nCorrectors                 {nCorr};
    nNonOrthogonalCorrectors    {nNonOrth};
    pRefCell                    0;
    pRefValue                   0;
}}"""

    content = _header("dictionary","fvSolution") + f"""
solvers
{{{p_block}

    U
    {{
        solver          {U_solver};
        preconditioner  DILU;
        tolerance       {U_tol};
        relTol          {U_reltol};
    }}

    k
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-6;
        relTol          0.1;
    }}
    epsilon {{ $k; }}
    omega   {{ $k; }}
    T
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-6;
        relTol          0.1;
    }}
}}
{algo_block}
"""
    _write(case_dir, "system/fvSolution", content)


def _write(case_dir, rel_path, content):
    """Write a file, creating dirs as needed."""
    full = os.path.join(case_dir, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)


# ══════════════════════════════════════════════════════════════════
#  Case Builder — assembles all files for a given solver type
# ══════════════════════════════════════════════════════════════════

SOLVER_APPS = {
    "icoFoam":            "icoFoam",
    "simpleFoam":         "simpleFoam",
    "pisoFoam":           "pisoFoam",
    "pimpleFoam":         "pimpleFoam",
    "buoyantSimpleFoam":  "buoyantSimpleFoam",
    "laplacianFoam":      "laplacianFoam",
}

def build_case(case_dir, solver_type, params):
    """
    Write a complete OpenFOAM case directory from user params.
    Returns list of files written.
    """
    os.makedirs(os.path.join(case_dir, "0"),        exist_ok=True)
    os.makedirs(os.path.join(case_dir, "constant"), exist_ok=True)
    os.makedirs(os.path.join(case_dir, "system"),   exist_ok=True)

    app = SOLVER_APPS.get(solver_type, solver_type)
    params["application"] = app
    written = []

    is_channel = solver_type in ("simpleFoam","pisoFoam","pimpleFoam")
    is_buoyant  = solver_type == "buoyantSimpleFoam"
    is_laplacian= solver_type == "laplacianFoam"

    # ── Mesh ──
    if is_channel:
        write_blockMeshDict_channel(case_dir, params)
    else:
        write_blockMeshDict(case_dir, params)
    written.append("system/blockMeshDict")

    # ── 0/ fields ──
    if is_buoyant:
        _write_buoyant_U(case_dir, params)
        _write_buoyant_p(case_dir, params)
        write_T_buoyant(case_dir, params)
        written += ["0/U","0/p","0/T"]
    elif is_laplacian:
        write_T_laplacian(case_dir, params)
        written.append("0/T")
    elif is_channel:
        write_U_channel(case_dir, params)
        write_p_channel(case_dir, params)
        written += ["0/U","0/p"]
    else:  # cavity (icoFoam default)
        write_U_cavity(case_dir, params)
        write_p_cavity(case_dir, params)
        written += ["0/U","0/p"]

    write_turbulence_initial_fields(case_dir, params)

    # ── constant/ ──
    write_transportProperties(case_dir, params)
    write_turbulenceProperties(case_dir, params)
    written += ["constant/transportProperties","constant/turbulenceProperties"]

    if is_buoyant:
        write_thermophysicalProperties(case_dir, params)
        write_g_file(case_dir, params)
        written += ["constant/thermophysicalProperties","constant/g"]

    if is_laplacian:
        write_transportProperties_laplacian(case_dir, params)

    # ── system/ ──
    write_controlDict(case_dir, params)
    write_fvSchemes(case_dir, params)
    write_fvSolution(case_dir, params)
    written += ["system/controlDict","system/fvSchemes","system/fvSolution"]

    return written


def _write_buoyant_U(case_dir, params):
    T_hot  = params.get("T_hot",350); T_cold=params.get("T_cold",293)
    content = _header("volVectorField","U") + """
dimensions  [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{
    hotWall    { type noSlip; }
    coldWall   { type noSlip; }
    walls      { type noSlip; }
    frontAndBack { type empty; }
}
"""
    _write(case_dir, "0/U", content)


def _write_buoyant_p(case_dir, params):
    content = _header("volScalarField","p_rgh") + """
dimensions  [1 -1 -2 0 0 0 0];
internalField   uniform 0;
boundaryField
{
    hotWall    { type fixedFluxPressure; value uniform 0; }
    coldWall   { type fixedFluxPressure; value uniform 0; }
    walls      { type fixedFluxPressure; value uniform 0; }
    frontAndBack { type empty; }
}
"""
    _write(case_dir, "0/p_rgh", content)
    content2 = _header("volScalarField","p") + """
dimensions  [1 -1 -2 0 0 0 0];
internalField   uniform 0;
boundaryField
{
    hotWall    { type calculated; value uniform 0; }
    coldWall   { type calculated; value uniform 0; }
    walls      { type calculated; value uniform 0; }
    frontAndBack { type empty; }
}
"""
    _write(case_dir, "0/p", content2)


def write_T_laplacian(case_dir, params):
    T_hot  = params.get("T_hot", 500.0)
    T_cold = params.get("T_cold", 300.0)
    alpha  = params.get("alpha",  1e-5)
    content = _header("volScalarField","T") + f"""
dimensions  [0 0 0 1 0 0 0];
internalField   uniform {T_cold};
boundaryField
{{
    left   {{ type fixedValue; value uniform {T_hot};  }}
    right  {{ type fixedValue; value uniform {T_cold}; }}
    top    {{ type zeroGradient; }}
    bottom {{ type zeroGradient; }}
    frontAndBack {{ type empty; }}
}}
"""
    _write(case_dir, "0/T", content)


def write_transportProperties_laplacian(case_dir, params):
    alpha = params.get("alpha", 1e-5)
    content = _header("dictionary","transportProperties") + f"""
DT              {alpha};
"""
    _write(case_dir, "constant/transportProperties", content)


def write_thermophysicalProperties(case_dir, params):
    """constant/thermophysicalProperties for buoyantSimpleFoam."""
    Cp    = params.get("Cp", 1005.0)
    kappa = params.get("kappa", 0.025)
    mu    = params.get("nu", 1e-5) * params.get("rho", 1.2)
    Pr    = mu * Cp / kappa if kappa > 0 else 0.7
    content = _header("dictionary","thermophysicalProperties") + f"""
thermoType
{{
    type            heRhoThermo;
    mixture         pureMixture;
    transport       const;
    thermo          hConst;
    equationOfState Boussinesq;
    specie          specie;
    energy          sensibleEnthalpy;
}}

mixture
{{
    specie
    {{
        molWeight       28.9;
    }}
    equationOfState
    {{
        rho0            {params.get("rho",1.2)};
        T0              {params.get("T_cold",293.0)};
        beta            {params.get("beta",3e-3)};
    }}
    thermodynamics
    {{
        Cp              {Cp};
        Hf              0;
    }}
    transport
    {{
        mu              {mu:.6e};
        Pr              {Pr:.4f};
    }}
}}
"""
    _write(case_dir, "constant/thermophysicalProperties", content)


def write_g_file(case_dir, params):
    """constant/g — gravity vector."""
    g = params.get("g", 9.81)
    content = _header("uniformDimensionedVectorField","g") + f"""
dimensions  [0 1 -2 0 0 0 0];
value       (0 -{g} 0);
"""
    _write(case_dir, "constant/g", content)


# ══════════════════════════════════════════════════════════════════
#  Result Parser — reads OpenFOAM output back into numpy arrays
# ══════════════════════════════════════════════════════════════════

def parse_of_scalar_field(filepath):
    """Parse an OpenFOAM ASCII scalar field file into numpy array."""
    with open(filepath) as f:
        text = f.read()

    # Find internalField
    m = re.search(r'internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([^)]+)\)', text, re.DOTALL)
    if m:
        n = int(m.group(1))
        vals = np.array([float(x) for x in m.group(2).split()], dtype=float)
        return vals

    # uniform
    m = re.search(r'internalField\s+uniform\s+([\d.eE+\-]+)', text)
    if m:
        return np.array([float(m.group(1))])

    return None


def parse_of_vector_field(filepath, component=0):
    """Parse an OpenFOAM ASCII vector field, return one component (0=x,1=y,2=z)."""
    with open(filepath) as f:
        text = f.read()

    m = re.search(r'internalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\(([^;]+)\)', text, re.DOTALL)
    if m:
        raw = m.group(2).strip()
        tuples = re.findall(r'\(\s*([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s*\)', raw)
        arr = np.array([[float(x),float(y),float(z)] for x,y,z in tuples], dtype=float)
        if component == 'mag':
            return np.linalg.norm(arr, axis=1)
        return arr[:, component]

    m = re.search(r'internalField\s+uniform\s+\(\s*([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s*\)', text)
    if m:
        vals = [float(m.group(i+1)) for i in range(3)]
        if component == 'mag':
            return np.array([np.linalg.norm(vals)])
        return np.array([vals[component]])

    return None


def get_latest_time_dir(case_dir):
    """Return path to the latest time directory (excluding 0)."""
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
    """Return list of field names available in the latest time directory."""
    latest = get_latest_time_dir(case_dir)
    if latest is None:
        # Fall back to 0/ directory
        zero = os.path.join(case_dir, "0")
        if os.path.exists(zero):
            return [f for f in os.listdir(zero)
                    if os.path.isfile(os.path.join(zero, f))
                    and not f.startswith('.')]
        return []
    skip = {'uniform', 'polyMesh', 'sets', 'surfaces'}
    fields = []
    for f in os.listdir(latest):
        if f in skip or f.startswith('.'):
            continue
        if os.path.isfile(os.path.join(latest, f)):
            fields.append(f)
    return sorted(fields)


def _best_field(case_dir, requested):
    """
    Return the best available field name for a requested field.
    Handles aliases: T→p (icoFoam has no T), Umag→U, etc.
    """
    available = list_available_fields(case_dir)
    if not available:
        return None
    # Direct match
    if requested in available:
        return requested
    # Aliases
    aliases = {
        'T':           ['T', 'p', 'U'],
        'temperature': ['T', 'p'],
        'p':           ['p', 'p_rgh'],
        'pressure':    ['p', 'p_rgh'],
        'U':           ['U'],
        'Umag':        ['U'],
        'velocity':    ['U'],
        'k':           ['k'],
        'epsilon':     ['epsilon'],
        'omega':       ['omega'],
    }
    for candidate in aliases.get(requested, [requested]):
        if candidate in available:
            return candidate
    # Return first available scalar-like field
    for f in available:
        if f not in ('polyMesh',):
            return f
    return None


def read_field_as_heatmap(case_dir, field_name, nx, ny, nz=1):
    """
    Read the latest time step of a field and return as heatmap dict
    with shape [nz][ny][nx], min, max, is_3d.
    Auto-detects best available field if requested field missing.
    """
    latest = get_latest_time_dir(case_dir)
    if latest is None:
        return None

    # Resolve to best available field
    resolved = _best_field(case_dir, field_name)
    if resolved is None:
        return None

    fpath = os.path.join(latest, resolved)
    if not os.path.exists(fpath):
        return None

    # Try scalar first, then vector magnitude
    arr = parse_of_scalar_field(fpath)
    is_vector = False
    if arr is None:
        arr = parse_of_vector_field(fpath, component='mag')
        is_vector = True
    if arr is None:
        return None

    # Handle uniform (single value) case
    if arr.size == 1:
        arr = np.full(nx*ny*nz, arr[0])

    # Sanitize
    arr = arr.astype(float)
    bad = ~np.isfinite(arr)
    if bad.any() and not bad.all():
        good = np.flatnonzero(~bad)
        arr[np.flatnonzero(bad)] = np.interp(np.flatnonzero(bad), good, arr[good])
    elif bad.all():
        arr[:] = 0.0

    # Reshape to [nz][ny][nx]
    total = nx * ny * nz
    if arr.size < total:
        arr = np.resize(arr, total)
    elif arr.size > total:
        arr = arr[:total]
    arr = arr.reshape(nz, ny, nx)
    data = arr.tolist()

    return {
        "data":      data,
        "min":       float(arr.min()),
        "max":       float(arr.max()),
        "shape":     [nz, ny, nx],
        "is_3d":     nz > 1,
        "field":     resolved,
        "requested": field_name,
        "field": field_name,
        "time_dir": os.path.basename(latest)
    }


def parse_residuals_log(log_path):
    """Parse OpenFOAM log file for residuals. Returns dict of lists."""
    residuals = {}
    if not os.path.exists(log_path):
        return residuals
    pattern = re.compile(r'Solving for (\w+).*?Initial residual = ([\d.eE+\-]+)', re.IGNORECASE)
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
    """Parse final ExecutionTime from log."""
    if not os.path.exists(log_path):
        return None
    with open(log_path) as f:
        text = f.read()
    m = re.findall(r'ExecutionTime\s*=\s*([\d.]+)\s*s', text)
    return float(m[-1]) if m else None


# ══════════════════════════════════════════════════════════════════
#  CaseRunner — manages the full lifecycle
# ══════════════════════════════════════════════════════════════════

class CaseRunner:
    """
    Manages one OpenFOAM case: build → mesh → solve → parse.
    Thread-safe: run() can be called in a background thread.
    """

    def __init__(self, case_dir):
        self.case_dir   = case_dir
        self.status     = "idle"   # idle|meshing|running|done|error
        self.log_path   = os.path.join(case_dir, "foam.log")
        self.progress   = 0.0     # 0–100
        self.error_msg  = ""
        self.residuals  = {}
        self.exec_time  = None
        self._params    = {}
        self._thread    = None

    def build(self, solver_type, params):
        """Write case files. Returns list of written files."""
        self._params = params.copy()
        self._params["solver_type"] = solver_type
        return build_case(self.case_dir, solver_type, params)

    def run_async(self, solver_type, params):
        """Build and run in background thread."""
        def _go():
            try:
                self.build(solver_type, params)
                self._run_blockmesh()
                self._run_solver(solver_type, params)
            except Exception as e:
                self.status    = "error"
                self.error_msg = str(e)

        self._thread = threading.Thread(target=_go, daemon=True)
        self._thread.start()

    def run_sync(self, solver_type, params, timeout=600):
        """Build and run synchronously. Raises on error."""
        self.build(solver_type, params)
        self._run_blockmesh(timeout=60)
        self._run_solver(solver_type, params, timeout=timeout)

    def _run_blockmesh(self, timeout=60):
        self.status   = "meshing"
        self.progress = 5.0
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

        rc, out = run_of_cmd("blockMesh", self.case_dir, timeout=timeout, log_file=self.log_path)
        if rc != 0:
            self.status    = "error"
            self.error_msg = f"blockMesh failed (rc={rc}). Check {self.log_path}"
            raise RuntimeError(self.error_msg)
        self.progress = 15.0

    def _run_solver(self, solver_type, params, timeout=600):
        self.status   = "running"
        app = SOLVER_APPS.get(solver_type, solver_type)
        rc, out = run_of_cmd(app, self.case_dir, timeout=timeout, log_file=self.log_path)

        self.residuals = parse_residuals_log(self.log_path)
        self.exec_time = parse_execution_time(self.log_path)
        self.progress  = 100.0

        if rc != 0:
            self.status    = "error"
            self.error_msg = f"{app} failed (rc={rc}). Check {self.log_path}"
            raise RuntimeError(self.error_msg)

        self.status = "done"

    def get_heatmap(self, field_name, nx, ny, nz=1):
        return read_field_as_heatmap(self.case_dir, field_name, nx, ny, nz)

    def tail_log(self, n=40):
        """Return last n lines of foam.log."""
        if not os.path.exists(self.log_path):
            return ""
        with open(self.log_path) as f:
            lines = f.readlines()
        return "".join(lines[-n:])

    def is_running(self):
        return self._thread and self._thread.is_alive()


# ══════════════════════════════════════════════════════════════════
#  Global registry of active cases
# ══════════════════════════════════════════════════════════════════
CASES_ROOT = os.path.join(os.path.dirname(__file__), "of_cases")
os.makedirs(CASES_ROOT, exist_ok=True)

_runners = {}   # case_name -> CaseRunner

def get_runner(name, create=True):
    if name not in _runners and create:
        case_dir = os.path.join(CASES_ROOT, name)
        os.makedirs(case_dir, exist_ok=True)
        _runners[name] = CaseRunner(case_dir)
    return _runners.get(name)
