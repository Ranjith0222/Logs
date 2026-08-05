# Logs

A small Python CLI for scraping and filtering structured log files from local paths or URLs.

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
logs <path-or-url> [--level LEVEL]
```

Example:

```bash
logs samples/app.log --level ERROR
```
