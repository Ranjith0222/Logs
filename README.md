# Logs

A small Python CLI for scraping, filtering, and building extracts from structured log files
(local paths or URLs).

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

# Run the CLI against the sample log file
logs samples/app.log --level ERROR
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
| `--format {raw,json,csv}` | Output format (default: `raw`) |
| `-o` / `--output PATH` | Write the extract to a file |
| `--quiet` | Suppress the match-count line on stderr |

### Examples

```bash
# Errors only
logs samples/app.log --level ERROR

# JSON extract for disk-related errors
logs samples/app.log --level ERROR --contains Disk --format json

# CSV extract for a time window
logs samples/app.log --since "2026-08-05 10:00:02" --until "2026-08-05 10:00:04" \
  --format csv -o /tmp/slice.csv
```

## Extract builder (library)

Compose extracts programmatically with the fluent builder:

```python
from logs import ExtractBuilder

text = (
    ExtractBuilder()
    .from_source("samples/app.log")
    .level("ERROR")
    .contains("Disk")
    .as_json()
    .to_file("/tmp/errors.json")
    .extract()
)
```
