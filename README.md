# Logs

Desktop app: upload the **full UW log** + **class-code Excel template** → get a
filled Excel output (Building / BPP / Liability factors).

## Requirements

- Windows
- Python 3.12+ from [python.org](https://www.python.org/downloads/) (Tcl/Tk included; check **Add to PATH**)

## How to use (desktop)

1. Open the app (`logs desktop` or `dist\LogsExtract.exe`)
2. **Browse log…** → select the **entire** UW ruleset `.log`
3. **Browse Excel…** → select your **class-code Excel template** (e.g. `PMBP001029427Z01.xlsx`)
4. Click **Generate Excel** → choose where to save the output
5. Open the saved `.xlsx` — factors are filled into columns **U / V / W**

Optional: **Preview factors** shows extracted values before saving.

## Build EXE (Policywise-style folders)

```text
Logs\
  .venv\
  build\
  dist\LogsExtract.exe   <-- double-click to open
  build.bat
```

```powershell
git clone -b cursor/logs-excel-export-1951 https://github.com/Ranjith0222/Logs.git
cd Logs
# double-click build.bat
```

## CLI

```powershell
logs excel full_ruleset.log --template PMBP001029427Z01.xlsx -o output.xlsx
```

| Column | Ruleset |
|--------|---------|
| **U** | Building |
| **V** | Business Personal Property |
| **W** | Liability |

## Dev run

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
logs desktop
```
