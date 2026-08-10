# Build LogsExtract.exe on Windows — same folder layout as Policywise_Generator:
#   .venv\   build\   dist\LogsExtract.exe
#
# Prefer double-clicking build.bat in the repo root.
# Or run:
#   powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "Building LogsExtract.exe (Policywise-style dist/build/.venv layout)..."

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating .venv ..."
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .
& .\.venv\Scripts\python.exe -m pip install "pyinstaller>=6.11.0,<7"

if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

& .\.venv\Scripts\pyinstaller.exe packaging\LogsExtract.spec --noconfirm --clean --distpath dist --workpath build

$exe = Join-Path (Get-Location) "dist\LogsExtract.exe"
if (-not (Test-Path $exe)) {
    throw "Build failed: $exe not found"
}

Write-Host ""
Write-Host "SUCCESS"
Write-Host "  .venv\"
Write-Host "  build\"
Write-Host "  dist\LogsExtract.exe   <-- open this"
Write-Host ""
Get-Item $exe | Format-List FullName, Length, LastWriteTime
