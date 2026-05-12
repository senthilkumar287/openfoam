@echo off
echo Starting OpenFOAM Heat Transfer Simulator...
echo.
echo Backend starting on port 5000...
cd /d "%~dp0\backend"
start python app.py
timeout /t 2
echo.
echo Opening browser at http://localhost:5000...
start http://localhost:5000
echo.
echo Application is running!
echo Press Ctrl+C in the terminal window to stop.
pause
