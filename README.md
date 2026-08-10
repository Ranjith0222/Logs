# Logs

Native **desktop** app (and CLI) for extracting UW ruleset / Building rating factors
from ItemRating execution logs. Package it as a Windows `.exe` — no browser required.

## Requirements

- Python 3.12+ (Windows: install from [python.org](https://www.python.org/downloads/) so Tcl/Tk is included)

## Run the desktop app (local)

```bash
git clone https://github.com/Ranjith0222/Logs.git
cd Logs

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"
logs desktop
# or:
logs-desktop
```

1. Click **Browse…** and select your UW `.log`  
2. Keep ruleset `Building` and mode `building-factors`  
3. Click **Extract**  
4. Use **Save JSON** / **Save CSV**

## Build Windows EXE

### On a Windows PC

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
pip install "pyinstaller>=6.11.0,<7"
powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1
```

Output: `dist\LogsExtract.exe` — double-click to open the desktop app.

### Via GitHub Actions

Push to `main` (or run **Build Windows EXE** manually). Download the
`LogsExtract-windows` artifact from the workflow run.

## CLI (optional)

```bash
logs samples/uw_item_rating_building.log --ruleset Building --building-factors
```

## Building factors extracted

`LCMFactor`, `IRPMFactor`, `PropertyRateNumbers`, `OccRelativityFactor`,
`BuiConstructionRelativitiesFactor`, `BuildingRelativityFactor`, `PPCFac`,
`BCEGFac`, `SprinkledFactor`, `400513BCvgFactor`, `FixedDedFactor`, `BaseLCfac`

## Optional web UI

The older browser UI is still available if you want it:

```bash
pip install -e ".[web]"
logs gui --host 127.0.0.1 --port 8000
```
