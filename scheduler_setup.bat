@echo off
REM ============================================================
REM Redfin Listing Finder - Windows Task Scheduler Setup
REM Creates one scheduled task: 8:00 AM daily
REM Run this script as Administrator
REM ============================================================

SET PYTHON_PATH=C:\Users\Zara\anaconda3\python.exe
SET SCRIPT_PATH=%~dp0run.py
SET WORKING_DIR=%~dp0

echo.
echo ============================================================
echo  Redfin Listing Finder - Task Scheduler Setup
echo ============================================================
echo.
echo Python: %PYTHON_PATH%
echo Script: %SCRIPT_PATH%
echo Working Dir: %WORKING_DIR%
echo.

REM Delete any existing tasks (cleans up old names too)
schtasks /delete /tn "ZillowFinder_Morning" /f >nul 2>&1
schtasks /delete /tn "ZillowFinder_Evening" /f >nul 2>&1
schtasks /delete /tn "ZillowFinder_Daily" /f >nul 2>&1
schtasks /delete /tn "RedfinFinder_Daily" /f >nul 2>&1

REM Create daily task (8:00 AM)
schtasks /create ^
    /tn "RedfinFinder_Daily" ^
    /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\"" ^
    /sc daily ^
    /st 08:00 ^
    /rl HIGHEST ^
    /f

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to create task. Run as Administrator.
    goto :error
)
echo [OK] Created RedfinFinder_Daily (8:00 AM daily)

echo.
echo ============================================================
echo  Setup complete!
echo    - RedfinFinder_Daily: Every day at 8:00 AM
echo.
echo  To verify:  schtasks /query /tn "RedfinFinder_Daily"
echo  To run now: schtasks /run /tn "RedfinFinder_Daily"
echo  To remove:  schtasks /delete /tn "RedfinFinder_Daily" /f
echo ============================================================
echo.

goto :end

:error
echo.
echo Setup failed. Please run this script as Administrator.
echo Right-click the .bat file and select "Run as administrator"
echo.

:end
pause
