@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
)

call ".venv\Scripts\activate.bat"

REM ARE runtime has no required third-party packages.
REM requirements.txt is intentionally kept for compatibility and future additions.
python -m pip install -r requirements.txt

python -m automation_repository_explorer.local_app

endlocal
