#!/bin/bash
# ============================================================
#  OpenFOAM Clone — Start Server (WSL)
#  Run: bash run.sh
#  Then open browser: http://localhost:5000
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$SCRIPT_DIR/backend"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   OpenFOAM Clone — Starting...       ║"
echo "╚══════════════════════════════════════╝"

# Source OpenFOAM if of_config.json exists
CONFIG="$BACKEND/of_config.json"
if [ -f "$CONFIG" ]; then
    BASHRC=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('OF_BASHRC',''))" 2>/dev/null)
    if [ -f "$BASHRC" ]; then
        echo "► Sourcing OpenFOAM: $BASHRC"
        source "$BASHRC"
        echo "  ✅ OpenFOAM environment loaded: $WM_PROJECT_VERSION"
    fi
fi

echo "► Starting Flask server..."
echo "► Open browser at: http://localhost:5000"
echo ""
cd "$BACKEND"
python3 app.py
