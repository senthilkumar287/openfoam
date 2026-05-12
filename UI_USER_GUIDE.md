# OpenFOAM Heat Transfer Simulator - User Guide

## Quick Start

### 1. Start the Application

**Option A: Using Batch File (Windows)**
```
Double-click: start_app.bat
```

**Option B: Manual Start**
```bash
cd backend
python app.py
```

Then open browser at: `http://localhost:5000`

---

## Complete Workflow

The UI is organized in 5 steps from left to right:

### Step 1: Create Mesh
**Purpose**: Define the computational domain and grid resolution

| Field | Value | Description |
|-------|-------|-------------|
| **Dimension Type** | 3D | Select 2D or 3D |
| **Grid Size X (nx)** | 50 | Number of cells in X direction |
| **Grid Size Y (ny)** | 50 | Number of cells in Y direction |
| **Grid Size Z (nz)** | 10 | Number of cells in Z direction (3D only) |
| **Domain Length X** | 1.0 | Physical length in X (meters) |
| **Domain Length Y** | 1.0 | Physical length in Y (meters) |
| **Domain Length Z** | 0.2 | Physical length in Z (meters) |

**Expected Output**:
```
[MESH] Creating mesh: 50x50x10 on domain [1.0, 1.0, 0.2]
✓ 3D Mesh created: 50x50x10 = 25000 cells
  Total cells: 25000
```

---

### Step 2: Create Solver
**Purpose**: Initialize the heat transfer solver

| Field | Value | Description |
|-------|-------|-------------|
| **Solver Type** | laplacianFoam | Heat transfer solver (only option for this guide) |
| **Thermal Diffusivity (alpha)** | 0.01 | Heat diffusion coefficient (m²/s) |

**Supported Solvers**:
- **laplacianFoam**: Heat diffusion (dT/dt = α ∇²T)
- **simpleFoam**: CFD (requires nu, rho)

**Expected Output**:
```
[SOLVER] Creating laplacianFoam with config:
✓ laplacianFoam created
  Solver: laplacianFoam
```

---

### Step 3: Set Boundary Conditions
**Purpose**: Define temperature boundary conditions on domain surfaces

| Field | Value | Description |
|-------|-------|-------------|
| **BC Name** | hot_wall | User-defined boundary name |
| **Location** | x_min | Domain surface location |
| **Type** | dirichlet | Fixed value (temperature) |
| **Value** | 100.0 | Temperature in Kelvin |

**Available Locations**:
- `x_min` - Left surface (minimum X)
- `x_max` - Right surface (maximum X)
- `y_min` - Front surface (minimum Y)
- `y_max` - Back surface (maximum Y)
- `z_min` - Bottom surface (minimum Z)
- `z_max` - Top surface (maximum Z)

**BC Types**:
- `dirichlet` - Fixed value (ideal for temperature)
- `neumann` - Fixed gradient (zero = insulated)

**Example Configuration**:
```
Row 1:
  Name: hot_wall
  Location: x_min
  Type: dirichlet
  Value: 100.0
  Action: [Set Button]

Row 2:
  Name: cold_wall
  Location: x_max
  Type: dirichlet
  Value: 0.0
  Action: [Set Button]
```

**Expected Output**:
```
[BC] Setting: hot_wall at x_min (dirichlet) = 100
✓ BC set: BC set on hot_wall at x_min (500 cells)

[BC] Setting: cold_wall at x_max (dirichlet) = 0
✓ BC set: BC set on cold_wall at x_max (500 cells)
```

---

### Step 4: Run Simulation
**Purpose**: Execute the heat transfer solver

| Field | Value | Description |
|-------|-------|-------------|
| **Maximum Iterations** | 100 | Max solver iterations |
| **Convergence Tolerance** | 1e-6 | Residual convergence criterion |
| **Time Step (dt)** | 0.01 | Not used (auto-calculated) |
| **Sample Interval** | 10 | Print output every N iterations |

**Expected Output**:
```
[SIM] Starting simulation...
  Max iterations: 100
  Tolerance: 1e-6
  Time step: 0.01

LaplacianFoam: alpha=0.01, dt=0.005553, iters=100, cells=25000
  iter 0: res=1.067e+01, Tmin=0.0, Tmax=100.0
  iter 10: res=1.690e+00, Tmin=0.0, Tmax=100.0
  iter 20: res=8.971e-01, Tmin=0.0, Tmax=100.0
  ...
✓ Simulation completed
  Converged: true
  Iterations: 99
  Final residual: 1.93e-01
```

---

### Step 5: Results & Visualization
**Purpose**: View and export simulation results

**Available Actions**:
1. **Get 2D Heatmap** - Retrieve 2D temperature field
2. **Get 3D Heatmap** - Retrieve full 3D temperature field
3. **Export CSV** - Save results to CSV file

**Expected Output**:
```
[RESULTS] Fetching 2D heatmap...
✓ 2D Heatmap retrieved
  Min: 0.00 K
  Max: 100.00 K
  Mean: 50.00 K

[EXPORT] Exporting results to CSV...
✓ Data exported to CSV
  File: exports/export.csv
```

---

## Complete Example Simulation

### Initial Setup (All Fields Pre-filled)
```
STEP 1: Mesh
  nx=50, ny=50, nz=10
  domain=[1.0, 1.0, 0.2]
  
STEP 2: Solver
  type=laplacianFoam
  alpha=0.01
  
STEP 3: Boundary Conditions
  hot_wall: x_min, dirichlet, 100.0 K
  cold_wall: x_max, dirichlet, 0.0 K
  
STEP 4: Simulation
  max_iters=100
  tolerance=1e-6
  
STEP 5: Results
  Export to CSV
```

### Expected Results
```
Temperature Gradient: 0K (cold) to 100K (hot)
Convergence: 99 iterations
Residual Decay: 10.67 → 0.19

Visualization:
  LEFT (x=0):    100K (RED)
  MIDDLE (x=0.5): 50K (YELLOW)
  RIGHT (x=1.0):   0K (BLUE)
```

---

## Output Panel

All operations log output to the **Output Panel** at the bottom. This includes:
- Mesh creation details
- Solver initialization
- Boundary condition setup
- Simulation progress
- Results statistics

**Controls**:
- `Clear Output` - Clear all logged text

---

## Status Indicators

Color-coded status messages appear below each section:

| Color | Status | Meaning |
|-------|--------|---------|
| Green | SUCCESS | Operation completed successfully |
| Red | ERROR | Operation failed - check output panel |
| Gray | INFO | Informational messages |

---

## Troubleshooting

### "Connection error" Message
- **Cause**: Flask backend not running
- **Solution**: Start Flask with `python app.py` in the `backend/` folder

### "No mesh created" Error
- **Cause**: Skipped Step 1
- **Solution**: Create mesh first before solver

### "Create solver first" Error
- **Cause**: Solver not initialized
- **Solution**: Complete Steps 1 and 2 in order

### Temperature Shows as Uniform (All 20K)
- **Cause**: Boundary conditions not set
- **Solution**: Set BCs in Step 3 with different values

### Simulation Never Converges
- **Cause**: Tolerance too strict or mesh too coarse
- **Solution**: 
  - Increase `max_iters` to 200+
  - Reduce `tolerance` to 1e-5 or 1e-4
  - Coarser mesh converges faster (try nx=30, ny=30)

---

## API Reference

The UI communicates with these endpoints:

```
POST /api/mesh/create3d
  Input: {nx, ny, nz, domain}
  Output: {status, mesh}

POST /api/solver/create
  Input: {type, config}
  Output: {status, solver}

POST /api/bc/set
  Input: {patch, location, type, value}
  Output: {status, message}

POST /api/simulate/run
  Input: {max_iters, dt, tolerance, sample_interval}
  Output: {status, converged, iterations, residuals}

GET /api/results/heatmap
  Output: {status, data, statistics}

GET /api/results/heatmap3d
  Output: {status, data, statistics}

POST /api/results/export
  Input: {format}
  Output: {status, file}
```

---

## Files Generated

- `exports/export.csv` - Temperature field exported as CSV
- `exports/export.json` - Temperature field as JSON
- `exports/export.vtk` - Temperature field as VTK format
- `backend/test_heat_gradient.py` - Automated test case

---

## System Requirements

- Python 3.8+
- Flask
- Flask-CORS
- NumPy
- Modern web browser (Chrome, Firefox, Edge)

---

## Next Steps

After successful simulation:

1. **Analyze Results**: Open CSV file in Excel/Calc
2. **Visualize**: Use VTK files in ParaView
3. **Experiment**: Try different:
   - Temperature values (higher gradients = faster diffusion)
   - Mesh resolutions (coarser = faster convergence)
   - Alpha values (diffusivity)
   - Domain sizes

---

## Support

For issues or questions:
1. Check **Output Panel** for error messages
2. Verify all 5 steps completed in order
3. Check Flask backend is running
4. Review API_GUIDE_HEAT_TRANSFER.md for technical details
