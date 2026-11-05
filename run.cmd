@echo off
setlocal
cd /d "%~dp0"
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 14) else 1)" >nul 2>&1
if not errorlevel 1 (
    python -X utf8 "%~dp0start.py" %*
    goto finished
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 14) else 1)" >nul 2>&1
if not errorlevel 1 (
    py -3 -X utf8 "%~dp0start.py" %*
    goto finished
)
echo Install Python 3.14+ with Tcl/Tk, then run run.cmd again.
pause
exit /b 1
:finished
set "XY_EXIT=%ERRORLEVEL%"
if not "%XY_EXIT%"=="0" pause
exit /b %XY_EXIT%
