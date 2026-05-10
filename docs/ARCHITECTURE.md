# OpenFOAM Clone - System Architecture

## Overview

A three-tier web application: **Frontend (HTML/CSS/JS) → Backend (Flask/Python) → Compute (NumPy/SciPy)**

```
Browser (UI)
    ↓ HTTP/JSON
Flask API Server (Route Handler)
    ↓
Python Solver Engine (NumPy/SciPy)
    ↓
Results Cache/Export
    ↓ HTTP/JSON
Browser Visualization
```

## Backend Architecture

### Core Modules (9 files)

1. **01_mesh.py** - Mesh generation, import/export
   - `Mesh`: Grid structure (cells, faces, volumes)
   - `BlockMeshGenerator`: Structured mesh creation
   - `MeshConverter`: STL/Gmsh/OpenFOAM formats

2. **02_field.py** - Field data management
   - `Field`: Generic scalar/vector field
   - `VectorField`: Velocity, gradients
   - `ScalarField`: Pressure, temperature
   - `FieldOperations`: Gradient, divergence, Laplacian
   - `FieldIO`: Save/load fields

3. **03_schemes.py** - Numerical discretization
   - `GradientScheme`: Gauss, least-squares
   - `DivergenceScheme`: Linear, upwind, MUSCL, QUICK
   - `LaplacianScheme`: Gauss, corrected
   - `TimeScheme`: Euler, RK4, Crank-Nicolson
   - `FluxLimiter`: van Leer, minmod

4. **04_boundary_conditions.py** - BC handling
   - `BoundaryCondition`: Base class
   - `DirichletBC`, `NeumannBC`, `RobinBC`: Basic BCs
   - `WallBC`, `InletBC`, `OutletBC`: Flow BCs
   - `PeriodicBC`, `SymmetryBC`: Spatial BCs
   - `BoundaryManager`: Apply all BCs

5. **05_turbulence.py** - Turbulence modeling
   - `TurbulenceModel`: Base class
   - `KEpsilonModel`: k-epsilon (Standard, RNG, Realizable)
   - `KOmegaModel`: k-omega, SST
   - `SpalartAllmarasModel`: One-equation
   - `LESModel`: Large Eddy Simulation
   - `WallFunctions`: Log-law treatment

6. **06_linear_solvers.py** - Linear algebra
   - `LinearSystem`: Sparse matrix system
   - `IterativeSolver`: Jacobi, Gauss-Seidel, SOR, GMRES
   - `Preconditioner`: ILU, DILU, Diagonal

7. **07_solvers.py** - CFD solvers
   - `BaseSolver`: Common interface
   - `SimpleFoam`: SIMPLE (steady)
   - `IcoFoam`: ICO (transient laminar)
   - `LaplacianFoam`: Heat diffusion
   - `PisoFoam`: PISO (transient)

8. **08_postprocessing.py** - Results processing
   - `FieldOperations`: Gradient, vorticity, Q-criterion
   - `Sampling`: Lines, planes, points
   - `Averaging`: Time/ensemble averaging
   - `DataExport`: VTK, CSV, JSON, HDF5
   - `Visualization`: Heatmap, vectors, contours
   - `MonitoringProbes`: Track point values

9. **09_chemistry.py** - Chemistry models
   - `ChemistryModel`: Base class
   - `SimpleChemistry`: One-step reactions
   - `FlameletModel`: Flamelet-based
   - `ReactionMechanism`: Multi-step
   - `CombustionSolver`: Operator splitting
   - `NoxyGenerator`, `SootModel`: Pollutants
   - `ThermodynamicProperties`, `EquationOfState`: Properties

10. **app.py** (10_api_routes.py) - Flask server
    - 25+ REST endpoints
    - Case management
    - Simulation control
    - Result export

## Data Flow

### Simulation Workflow

```
1. Mesh Creation
   └─ Mesh(nx, ny, nz) → cells, faces, volumes

2. Solver Init
   └─ SimpleFoam(mesh) → U, p, k, ε fields

3. Field Setup
   └─ initialize_fields(U, p, k, ε)

4. Boundary Conditions
   └─ BoundaryManager.apply_all(fields)

5. Iteration Loop
   ├─ momentum_predictor()
   ├─ pressure_correction()
   ├─ velocity_update()
   ├─ turbulence_update()
   └─ check_convergence()

6. Post-Processing
   ├─ Extract fields
   ├─ Create visualization
   └─ Export results
```

### API Request Flow

```
HTTP Request (JSON)
    ↓
Flask Route Handler
    ↓
Global State (current_mesh, current_solver, current_case)
    ↓
Core Module Functions
    ↓
NumPy/SciPy Computation
    ↓
Result Assembly
    ↓
JSON Response
    ↓
Browser Rendering
```

## Frontend Architecture

### Page Structure

```
Header (Logo, Case Name, Save/Load Buttons)
├─ Left Sidebar (Navigation Menu)
├─ Center (Main Editor Panels)
│   ├─ Mesh Setup
│   ├─ Solver Config
│   ├─ Fields
│   ├─ Boundary Conditions
│   ├─ Run Control
│   ├─ Post-Processing
│   └─ Utilities
├─ Canvas (Visualization)
└─ Right Panel (Properties, Logs, Help)
```

### JavaScript Architecture

- **api.js**: HTTPClient class for backend calls
- **ui.js**: UIManager class for DOM manipulation
- **visualization.js**: VisualizationEngine for canvas rendering
- **app.js**: (Implicit) Event listeners & handlers

## Key Classes & Methods

### Mesh
```python
mesh = Mesh(nx=50, ny=50, nz=1, domain=(1,1,1))
mesh.create_cells()           # Cell centers
mesh.create_faces()           # Face connectivity
mesh.add_boundary_patch(...)  # Add BC region
mesh.compute_volumes()        # Cell volumes
```

### Solver
```python
solver = SimpleFoam(mesh, config)
solver.initialize_fields()     # U, p, k, ε
solver.solve(max_iters=100)    # Main loop
solver.check_convergence()     # Tolerance check
solver.get_residuals()         # History
```

### Field Operations
```python
grad_p = GradientScheme.gauss(p, mesh)
div_U = DivergenceScheme.upwind(U, velocity, mesh)
lap_T = LaplacianScheme.gauss_linear(T, mesh)
```

### Boundary Manager
```python
bc_manager = BoundaryManager(mesh)
bc_manager.add_bc('inlet', InletBC('inlet', 1.0))
bc_manager.add_bc('wall', WallBC('wall'))
bc_manager.apply_all(U)
```

## Performance Considerations

### Computational Complexity

| Operation | Complexity | O(n) where |
|-----------|-----------|-----------|
| Create mesh | O(n) | n = cells |
| Time step | O(n) | n = cells |
| Linear solve | O(n²) | CG, GMRES |
| Field I/O | O(n) | n = cells |

### Memory

- Cell data: ~50 bytes/cell × 2500 cells = 125 KB (small grid)
- Solver workspace: ~1 MB (residuals, intermediate fields)
- Visualization cache: ~100 KB (heatmap data)

### Bottlenecks

1. **Linear solver** - CG/GMRES iterations dominant
2. **Field operations** - NumPy vectorization helps
3. **I/O** - JSON serialization for large fields

## Scalability

**Current Limits:**
- Max mesh: ~250K cells (desktop RAM)
- Max iterations: Limited by convergence, not memory
- Parallel: Single-threaded (future: MPI)

**Optimizations:**
- NumPy vectorization (avoid Python loops)
- Sparse matrix storage (SciPy)
- Iterator patterns (avoid storing full history)

## Extension Points

1. **Add Solver**: Inherit `BaseSolver`
2. **Add Turbulence**: Inherit `TurbulenceModel`
3. **Add BC**: Inherit `BoundaryCondition`
4. **Add Scheme**: Add method to discretization classes
5. **Add Export**: Add format handler to `DataExport`

---

**Total Code: ~2000 lines Python + 800 lines HTML/CSS/JS**
