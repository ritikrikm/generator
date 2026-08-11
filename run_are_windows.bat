@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -c "import gherkin, cucumber_expressions, javaproperties, ruamel.yaml, lxml" >nul 2>&1
if errorlevel 1 (
    echo Installing ARE parser dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 exit /b 1
)

REM Local Tkinter UI only. Eclipse JDT bridge builds locally with Maven on first Java scan.
python -m automation_repository_explorer.local_app

endlocal
