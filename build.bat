@echo off
REM Build LogsExtract like Policywise_Generator:
REM   .venv\   virtual environment
REM   build\   PyInstaller work files
REM   dist\    LogsExtract.exe  (double-click this)
REM
REM Usage: double-click build.bat  OR  run from cmd in the repo root

setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo === LOGS Extract Windows build ===
echo Working directory: %CD%
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python not found on PATH.
  echo Install Python 3.12+ from https://www.python.org/downloads/
  echo Make sure "Add python.exe to PATH" is checked.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv ...
  python -m venv .venv
  if errorlevel 1 (
    echo ERROR: failed to create .venv
    exit /b 1
  )
)

echo Activating .venv ...
call ".venv\Scripts\activate.bat"

echo Installing package + PyInstaller ...
python -m pip install --upgrade pip
pip install -e .
if errorlevel 1 exit /b 1
pip install "pyinstaller>=6.11.0,<7"
if errorlevel 1 exit /b 1

echo.
echo Building dist\LogsExtract.exe ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

pyinstaller packaging\LogsExtract.spec --noconfirm --clean --distpath dist --workpath build
if errorlevel 1 (
  echo ERROR: PyInstaller build failed
  exit /b 1
)

if not exist "dist\LogsExtract.exe" (
  echo ERROR: dist\LogsExtract.exe was not created
  exit /b 1
)

echo.
echo ============================================
echo  SUCCESS
echo  .venv\              Python environment
echo  build\              PyInstaller temp files
echo  dist\LogsExtract.exe   ^<-- open this
echo ============================================
echo.
explorer "dist"
exit /b 0
