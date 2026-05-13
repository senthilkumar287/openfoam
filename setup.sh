#!/bin/bash
# ============================================================
#  OpenFOAM Clone — WSL Setup Script
#  Run once: bash setup.sh
# ============================================================
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   OpenFOAM Clone — WSL Setup         ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. Python deps ──────────────────────────────────────────
echo "► Installing Python dependencies..."
pip3 install flask flask-cors numpy --quiet
echo "  ✅ Python deps installed"

# ── 2. Detect OpenFOAM ──────────────────────────────────────
echo ""
echo "► Detecting OpenFOAM..."
cd "$(dirname "$0")/backend"
python3 detect_openfoam.py

# ── 3. Done ─────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════╗"
echo "║  Setup complete!                     ║"
echo "║  Run:  bash run.sh                   ║"
echo "╚══════════════════════════════════════╝"
