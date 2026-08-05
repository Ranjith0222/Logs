from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>[A-Z]+)\s+"
    r"(?P<message>.+)$"
)


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    level: str
    message: str
    raw: str


def parse_log_line(line: str) -> LogEntry | None:
    match = LOG_LINE_PATTERN.match(line.strip())
    if not match:
        return None
    return LogEntry(
        timestamp=match.group("timestamp"),
        level=match.group("level"),
        message=match.group("message"),
        raw=line.strip(),
    )


def read_log_lines(source: str) -> list[str]:
    if source.startswith(("http://", "https://")):
        response = requests.get(source, timeout=30)
        response.raise_for_status()
        return response.text.splitlines()

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Log source not found: {source}")
    return path.read_text(encoding="utf-8").splitlines()


def scrape_logs(source: str, level: str | None = None) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for line in read_log_lines(source):
        if not line.strip():
            continue
        entry = parse_log_line(line)
        if entry is None:
            continue
        if level is not None and entry.level != level.upper():
            continue
        entries.append(entry)
    return entries


def format_entries(entries: Iterable[LogEntry]) -> str:
    return "\n".join(entry.raw for entry in entries)
