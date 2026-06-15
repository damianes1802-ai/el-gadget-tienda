@echo off
REM Panel El Gadget - app de escritorio (lanza sin consola via AdminElGadget.vbs)
cd /d "%~dp0"
start "" wscript.exe "%~dp0AdminElGadget.vbs"
