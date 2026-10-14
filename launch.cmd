@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run setup.cmd first to create the local Python environment.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0bridge_gui.pyw"
