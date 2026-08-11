@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
)

call ".venv\Scripts\activate.bat"

REM No Streamlit, no local server, and no runtime pip install is required.
python -m automation_repository_explorer.local_app

endlocal
