# OpenFOAM Clone — Web CFD App

A ParaView-style browser interface for OpenFOAM running on WSL (Windows).

---

## Quick Start (WSL on Windows)

### Step 1 — Open WSL terminal
Press `Win + R` → type `wsl` → Enter

### Step 2 — Navigate to the app
```bash
cd /mnt/c/Users/YOUR_USERNAME/Desktop/openfoam_final
# Adjust the path to wherever you unzipped the folder
```

### Step 3 — Setup (run once)
```bash
bash setup.sh
```
This installs Python packages and auto-detects your OpenFOAM installation.

### Step 4 — Run
```bash
bash run.sh
```

### Step 5 — Open browser (on Windows)
```
http://localhost:5000
```

---

## If OpenFOAM is not detected automatically

Find your OpenFOAM bashrc:
```bash
find /opt /usr -name "bashrc" -path "*/openfoam*/etc/*" 2>/dev/null
```

Then edit `backend/of_config.json` manually:
```json
{
  "OF_ROOT":   "/opt/openfoam11",
  "OF_BASHRC": "/opt/openfoam11/etc/bashrc"
}
```

Or source OpenFOAM first, then run:
```bash
source /opt/openfoam11/etc/bashrc
cd backend
python3 detect_openfoam.py
python3 app.py
```

---

## App Workflow

| Step | What to do |
|------|-----------|
| **1. Mesh** | Set nx, ny, domain size → Generate Mesh |
| **2. Solver** | Pick solver (icoFoam/simpleFoam/etc), set ν, endTime, deltaT |
| **3. BC** | Add boundary conditions (lid velocity, inlet, temperatures) |
| **4. Run** | Click ▶ Run — OpenFOAM executes in background |
| **5. Post** | Click 🌡 Visualize — 3D heatmap, slices, vectors appear |

---

## Supported Solvers

| Solver | Type | Use case |
|--------|------|----------|
| `icoFoam` | Transient laminar | Lid-driven cavity |
| `simpleFoam` | Steady SIMPLE | Channel / pipe flow |
| `pisoFoam` | Transient PISO | Pulsating flows |
| `pimpleFoam` | Transient PIMPLE | Complex transient |
| `buoyantSimpleFoam` | Natural convection | Hot/cold wall cavity |
| `laplacianFoam` | Heat diffusion | Conduction only |

---

## File Structure

```
openfoam_final/
├── setup.sh              ← Run once to set up
├── run.sh                ← Start the server
├── README.md
├── backend/
│   ├── app.py            ← Flask REST API
│   ├── openfoam_backend.py ← Writes OF files, runs OF, parses results
│   ├── detect_openfoam.py  ← Auto-finds OF installation
│   ├── of_config.json    ← Created by detect_openfoam.py
│   └── of_cases/         ← OpenFOAM case directories (auto-created)
│       └── default/
│           ├── 0/        ← Field files (U, p, T, k, epsilon)
│           ├── constant/ ← transportProperties, turbulenceProperties
│           ├── system/   ← blockMeshDict, controlDict, fvSchemes, fvSolution
│           └── foam.log  ← OpenFOAM run log
└── frontend/
    ├── index.html
    ├── css/style.css
    └── js/
        ├── ui.js
        ├── visualization3d.js
        ├── visualization.js
        └── api.js
```

---

## Troubleshooting

**"OpenFOAM not found"**
→ Run `bash setup.sh` first, or edit `backend/of_config.json`

**"blockMesh failed"**
→ Check `backend/of_cases/default/foam.log` for errors
→ Common cause: invalid mesh parameters (nx too large, Lz=0)

**"Port 5000 in use"**
```bash
# Kill existing process:
fuser -k 5000/tcp
```

**Browser can't connect**
→ Make sure you opened `http://localhost:5000` in Windows browser (Edge/Chrome)
→ WSL2 exposes ports to Windows automatically

**Results look wrong**
→ Check `backend/of_cases/default/foam.log` — search for "FOAM FATAL ERROR"
→ Try reducing endTime or increasing deltaT first
