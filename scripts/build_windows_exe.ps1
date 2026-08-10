# Build LogsExtract.exe on a Windows machine.
#
# Prerequisites: Python 3.12+ from python.org (includes Tcl/Tk)
#
#   python -m venv .venv
#   .venv\Scripts\activate
#   pip install -e .
#   pip install "pyinstaller>=6.11.0,<7"
#   powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "Building LogsExtract.exe with PyInstaller..."
pyinstaller packaging\LogsExtract.spec --noconfirm --clean

$exe = Join-Path (Get-Location) "dist\LogsExtract.exe"
if (-not (Test-Path $exe)) {
    throw "Build failed: $exe not found"
}

Write-Host "Done: $exe"
Get-Item $exe | Format-List FullName, Length, LastWriteTime
