# Logs

A small Python CLI and GUI for scraping structured logs and extracting UW ruleset
execution data from local paths or URLs.

## Requirements

- Python 3.12+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## GUI

Launch the extract builder UI:

```bash
logs gui
# or
logs-gui --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000, drop a UW ItemRating `.log` file, keep ruleset
`Building`, and extract the rating factors.

## CLI

```bash
# Line-log extract
logs samples/app.log --level ERROR

# Building rating factors from the UW sample
logs samples/uw_item_rating_building.log --ruleset Building --building-factors
```

## Development

```bash
ruff check .
pytest
```

## Options

| Flag | Description |
|------|-------------|
| `--level LEVEL` | Keep only this log level (`ERROR`, `WARN`, `INFO`, …) |
| `--contains TEXT` | Keep messages containing this text (case-insensitive) |
| `--regex PATTERN` | Keep messages matching this regular expression |
| `--since TIMESTAMP` | Keep entries at or after this timestamp |
| `--until TIMESTAMP` | Keep entries at or before this timestamp |
| `--ruleset NAME` | Extract a UW ruleset execution by name (e.g. `Building`) |
| `--satisfied-only` | Keep only rulesets whose precondition was satisfied |
| `--fields A,B,C` | Extract only these ruleset field names |
| `--building-factors` | Shortcut for the standard Building rating factor set |
| `--format {raw,json,csv}` | Output format (default: `json` with `--ruleset`, else `raw`) |
| `-o` / `--output PATH` | Write the extract to a file |
| `--quiet` | Suppress the match-count line on stderr |

`--building-factors` selects:

`LCMFactor`, `IRPMFactor`, `PropertyRateNumbers`, `OccRelativityFactor`,
`BuiConstructionRelativitiesFactor`, `BuildingRelativityFactor`, `PPCFac`,
`BCEGFac`, `SprinkledFactor`, `400513BCvgFactor`, `FixedDedFactor`, `BaseLCfac`
