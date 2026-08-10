# Logs

Native **desktop** app for extracting UW Building rating factors from ItemRating
logs. Build it the same way as Policywise_Generator: `.venv` + `build` + `dist`.

## Requirements

- Windows
- Python 3.12+ from [python.org](https://www.python.org/downloads/) (Tcl/Tk included; check **Add to PATH**)

## Build EXE (Policywise-style folders)

```text
Logs\
  .venv\                 virtual environment
  build\                 PyInstaller work files
  dist\LogsExtract.exe   <-- double-click to open the app
  build.bat              one-click build
```

### Steps

1. Clone / download this repo  
2. Double-click **`build.bat`**  
3. When it finishes, open **`dist\LogsExtract.exe`**

Or from PowerShell in the repo folder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1
```

## Use the app

1. Open `dist\LogsExtract.exe`  
2. **Browse…** → select your UW `.log`  
3. Ruleset: `Building`  
4. Mode: `building-factors`  
5. **Extract**  
6. **Save JSON** / **Save CSV** if needed  

## Dev run (without building EXE)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
logs desktop
```

## CLI (optional)

```powershell
logs samples\uw_item_rating_building.log --ruleset Building --building-factors
```

## Factors extracted

`LCMFactor`, `IRPMFactor`, `PropertyRateNumbers`, `OccRelativityFactor`,
`BuiConstructionRelativitiesFactor`, `BuildingRelativityFactor`, `PPCFac`,
`BCEGFac`, `SprinkledFactor`, `400513BCvgFactor`, `FixedDedFactor`, `BaseLCfac`
