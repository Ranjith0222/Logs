# Logs

A small Python CLI for scraping structured logs and extracting UW ruleset execution
data from local paths or URLs.

## Requirements

- Python 3.12+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Development

```bash
# Lint
ruff check .

# Test
pytest

# Line-log extract
logs samples/app.log --level ERROR

# Building ruleset extract from the UW sample
logs samples/uw_item_rating_building.log --ruleset Building -o /tmp/building.json
```

## Usage

```bash
logs <path-or-url> [options]
```

### Options

| Flag | Description |
|------|-------------|
| `--level LEVEL` | Keep only this log level (`ERROR`, `WARN`, `INFO`, …) |
| `--contains TEXT` | Keep messages containing this text (case-insensitive) |
| `--regex PATTERN` | Keep messages matching this regular expression |
| `--since TIMESTAMP` | Keep entries at or after this timestamp |
| `--until TIMESTAMP` | Keep entries at or before this timestamp |
| `--ruleset NAME` | Extract a UW ruleset execution by name (e.g. `Building`) |
| `--satisfied-only` | Keep only rulesets whose precondition was satisfied |
| `--format {raw,json,csv}` | Output format (default: `json` with `--ruleset`, else `raw`) |
| `-o` / `--output PATH` | Write the extract to a file |
| `--quiet` | Suppress the match-count line on stderr |

### Examples

```bash
# Errors only
logs samples/app.log --level ERROR

# JSON extract for disk-related errors
logs samples/app.log --level ERROR --contains Disk --format json

# Extract the Building ruleset (inputs, evaluations, outputs)
logs samples/uw_item_rating_building.log --ruleset Building

# CSV summary of Building ruleset fields
logs samples/uw_item_rating_building.log --ruleset Building --format csv \
  -o /tmp/building.csv
```

## Extract builder (library)

```python
from logs import ExtractBuilder

text = (
    ExtractBuilder()
    .from_source("samples/uw_item_rating_building.log")
    .ruleset("Building")
    .as_json()
    .to_file("/tmp/building.json")
    .extract()
)
```

Ruleset extracts include:

- run header (`module_id`, `project_id`, `policy_no`, `effective_date`, …)
- precondition status / expression
- input variables (name, path, type, value)
- formula / decision-table evaluations
- output variables
