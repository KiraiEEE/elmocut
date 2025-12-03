@echo off
echo ========================================
echo   elmoCut Launcher
echo ========================================
echo.
echo Checking administrator privileges...

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Running as Administrator
    echo.
    echo Starting elmoCut...
    python start.py --quick
) else (
    echo [WARNING] Not running as Administrator!
    echo.
    echo Some features may not work properly.
    echo Right-click this file and select "Run as administrator"
    echo.
    pause
    echo.
    echo Starting anyway...
    python start.py --quick
)

pause
