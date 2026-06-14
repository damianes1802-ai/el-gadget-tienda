@echo off
REM Panel El Gadget - app de escritorio
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python scripts\admin_desktop.py

if errorlevel 1 (
    echo.
    echo Ocurrio un error al iniciar el panel. Revisa el mensaje anterior.
    pause
)
