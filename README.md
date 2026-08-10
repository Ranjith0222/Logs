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

## Save Excel (Policywise format)

After extracting a Building ruleset log, save a workbook like
`PMBP001029427Z01.xlsx` (summary + Build + Item sheets):

```powershell
logs excel samples\uw_item_rating_building.log -o dist\PMBP001030043Z02000.xlsx
```

Or in the desktop app: **Save Excel**.

Building / BPP / Liability factors are written into columns **U / V / W**:

| Row | Label | Building (U) | BPP (V) | Liability (W) |
|-----|-------|--------------|---------|---------------|
| 5 | Base Loss Costs | BaseLCfac | BaseLCFactor | BaseLCFactor |
| 6 | Prop Rate Group RF | OccRelativityFactor | OccRelativityFactor | |
| 7 | Construction Class RF | BuiConstruction… | BPPConstruction… | |
| 8 | LOI RF | BuildingRelativityFactor | BusinessRelativityFactor | |
| 9–12 | PPC / BCEG / Sprinkler / Deductible | Building fields | BPP fields | |
| 13–14 | LCM / IRPM | LCMFactor / IRPMFactor | same | same |
| 15 | BI period factor | 400513BCvgFactor | 400513BCvgFactor | |
| 17–19 | Liability class / limits / PD ded | | | LiabilityClassGrpFactor / IncreasedLimitsFactor / PropDamageDedFactor |

## CLI (optional)

```powershell
logs samples\uw_item_rating_building.log --ruleset Building --building-factors
```

## Factors extracted

`LCMFactor`, `IRPMFactor`, `PropertyRateNumbers`, `OccRelativityFactor`,
`BuiConstructionRelativitiesFactor`, `BuildingRelativityFactor`, `PPCFac`,
`BCEGFac`, `SprinkledFactor`, `400513BCvgFactor`, `FixedDedFactor`, `BaseLCfac`
