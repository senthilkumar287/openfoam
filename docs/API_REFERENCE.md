# OpenFOAM Clone - REST API Reference

## Overview

All endpoints return JSON. Base URL: `http://localhost:5000/api`

## Mesh API (`/mesh`)

### POST `/mesh/create`
Create structured mesh
```json
{
  "nx": 50,
  "ny": 50,
  "nz": 1,
  "domain": [1.0, 1.0, 1.0]
}
```
Response: Mesh info with cell count

### GET `/mesh/info`
Get current mesh properties
Response: Grid size, domain, volumes

### POST `/mesh/refine`
Refine mesh in region
```json
{
  "x_range": [0, 0.5],
  "y_range": [0, 1.0],
  "level": 2
}
```

## Solver API (`/solver`)

### GET `/solver/list`
List all available solvers
Response: Grouped by category (Incompressible, Compressible, etc.)

### POST `/solver/create`
Initialize solver
```json
{
  "type": "simpleFoam",
  "config": {
    "nu": 1e-5,
    "rho": 1.0,
    "dt": 0.01
  }
}
```

### POST `/solver/configure`
Set solver parameters during runtime

## Boundary Condition API (`/bc`)

### POST `/bc/set`
Set BC on patch
```json
{
  "patch": "inlet",
  "type": "inlet",
  "value": 1.0
}
```

Types: dirichlet, neumann, inlet, outlet, wall, symmetry, periodic

### GET `/bc/list`
List all BCs on patches

## Field API (`/fields`)

### POST `/fields/initialize`
Initialize flow fields
```json
{
  "U": [1.0, 0.0, 0.0],
  "p": 0.0,
  "k": 0.1,
  "epsilon": 0.01
}
```

### GET `/results/field/<name>`
Extract field (p, U, k, epsilon, T)

## Simulation API (`/simulate`)

### POST `/simulate/run`
Run simulation
```json
{
  "max_iters": 100,
  "dt": 0.01
}
```

Response:
```json
{
  "status": "success",
  "converged": true,
  "iterations": 78,
  "residuals": {
    "U": [0.1, 0.05, 0.02],
    "p": [0.2, 0.1, 0.05]
  }
}
```

### GET `/simulate/status`
Get current simulation status

## Results API (`/results`)

### GET `/results/heatmap`
Get field for visualization (heatmap data)

Response:
```json
{
  "heatmap": {
    "data": [[...], [...], ...],
    "min": 20.5,
    "max": 99.8
  }
}
```

### POST `/results/export`
Export results
```json
{
  "format": "json"
}
```

Formats: json, csv, vtk

## Case API (`/case`)

### POST `/case/save`
Save case to file
```json
{
  "name": "cavity_flow"
}
```

### POST `/case/load`
Load saved case
```json
{
  "name": "cavity_flow"
}
```

---

**Total Implemented Endpoints: 25+**
More endpoints being added continuously.
