"""
Auto-detects OpenFOAM in WSL environment.
Run this first to find your OF path.
Usage: python3 detect_openfoam.py
"""
import subprocess, os, sys

def detect():
    # Try sourcing common OF bashrc locations
    candidates = [
        "/opt/openfoam11/etc/bashrc",
        "/opt/openfoam10/etc/bashrc",
        "/opt/openfoam9/etc/bashrc",
        "/opt/openfoam8/etc/bashrc",
        "/opt/openfoam7/etc/bashrc",
        "/opt/openfoam6/etc/bashrc",
        "/opt/openfoam2312/etc/bashrc",
        "/opt/openfoam2306/etc/bashrc",
        "/opt/openfoam2212/etc/bashrc",
        "/opt/openfoam2112/etc/bashrc",
        "/usr/lib/openfoam/openfoam2312/etc/bashrc",
        "/usr/lib/openfoam/openfoam2212/etc/bashrc",
        "/usr/lib/openfoam/openfoam11/etc/bashrc",
    ]

    print("Searching for OpenFOAM...")

    # Also search dynamically
    result = subprocess.run(
        ["bash","-c","find /opt /usr/lib -name 'bashrc' -path '*/openfoam*/etc/bashrc' 2>/dev/null"],
        capture_output=True, text=True, timeout=10
    )
    for line in result.stdout.strip().splitlines():
        if line not in candidates:
            candidates.append(line)

    # Check WM_PROJECT_DIR env (set if OF already sourced in shell)
    wm = os.environ.get("WM_PROJECT_DIR","")
    if wm:
        bashrc = os.path.join(wm,"etc","bashrc")
        if bashrc not in candidates:
            candidates.insert(0, bashrc)

    for bashrc in candidates:
        if not os.path.exists(bashrc):
            continue
        # Try running blockMesh after sourcing
        test = subprocess.run(
            ["bash","-c",f'source "{bashrc}" && blockMesh -help 2>&1 | head -1'],
            capture_output=True, text=True, timeout=15
        )
        if test.returncode == 0 or len(test.stdout.strip()) > 0:
            root = os.path.dirname(os.path.dirname(bashrc))
            print(f"\n✅ OpenFOAM FOUND!")
            print(f"   Root:   {root}")
            print(f"   bashrc: {bashrc}")

            # Write config file for app to read
            with open("of_config.json","w") as f:
                import json
                json.dump({"OF_ROOT": root, "OF_BASHRC": bashrc}, f, indent=2)
            print(f"\n✅ Config saved to backend/of_config.json")
            print(f"\nNow run: python3 app.py")
            return root, bashrc
        else:
            print(f"   ✗ {bashrc} — not working")

    print("\n❌ OpenFOAM not found automatically.")
    print("   Please run: source /path/to/openfoam/etc/bashrc && python3 detect_openfoam.py")
    print("   OR edit of_config.json manually with your path.")

    # Write empty config for manual edit
    with open("of_config.json","w") as f:
        import json
        json.dump({"OF_ROOT": "/opt/openfoamXX", "OF_BASHRC": "/opt/openfoamXX/etc/bashrc"}, f, indent=2)
    return None, None

if __name__ == "__main__":
    detect()
