from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Self

from logs.scraper import LogEntry, scrape_logs


@dataclass(frozen=True)
class ExtractSpec:
    """Immutable configuration produced by :class:`ExtractBuilder`."""

    source: str
    level: str | None = None
    contains: str | None = None
    pattern: str | None = None
    since: str | None = None
    until: str | None = None
    output_format: str = "raw"
    output_path: str | None = None


class ExtractBuilder:
    """Fluent builder for composing and running log extracts.

    Example::

        text = (
            ExtractBuilder()
            .from_source("samples/app.log")
            .level("ERROR")
            .contains("Disk")
            .as_json()
            .extract()
        )
    """

    SUPPORTED_FORMATS = frozenset({"raw", "json", "csv"})

    def __init__(self) -> None:
        self._source: str | None = None
        self._level: str | None = None
        self._contains: str | None = None
        self._pattern: str | None = None
        self._since: str | None = None
        self._until: str | None = None
        self._output_format: str = "raw"
        self._output_path: str | None = None

    def from_source(self, source: str) -> Self:
        if not source or not source.strip():
            raise ValueError("source must be a non-empty path or URL")
        self._source = source.strip()
        return self

    def level(self, level: str | None) -> Self:
        self._level = level.upper() if level else None
        return self

    def contains(self, text: str | None) -> Self:
        self._contains = text if text else None
        return self

    def matching(self, pattern: str | None) -> Self:
        if pattern:
            re.compile(pattern)  # validate early
        self._pattern = pattern if pattern else None
        return self

    def since(self, timestamp: str | None) -> Self:
        self._since = timestamp if timestamp else None
        return self

    def until(self, timestamp: str | None) -> Self:
        self._until = timestamp if timestamp else None
        return self

    def format(self, output_format: str) -> Self:
        normalized = output_format.lower().strip()
        if normalized not in self.SUPPORTED_FORMATS:
            supported = ", ".join(sorted(self.SUPPORTED_FORMATS))
            raise ValueError(f"unsupported format {output_format!r}; choose one of: {supported}")
        self._output_format = normalized
        return self

    def as_raw(self) -> Self:
        return self.format("raw")

    def as_json(self) -> Self:
        return self.format("json")

    def as_csv(self) -> Self:
        return self.format("csv")

    def to_file(self, path: str | None) -> Self:
        self._output_path = path if path else None
        return self

    def build(self) -> ExtractSpec:
        if self._source is None:
            raise ValueError("source is required; call from_source(...) before build()")
        if self._since and self._until and self._since > self._until:
            raise ValueError("since must be less than or equal to until")
        return ExtractSpec(
            source=self._source,
            level=self._level,
            contains=self._contains,
            pattern=self._pattern,
            since=self._since,
            until=self._until,
            output_format=self._output_format,
            output_path=self._output_path,
        )

    def collect(self) -> list[LogEntry]:
        """Run the extract and return matching :class:`LogEntry` objects."""
        spec = self.build()
        entries = scrape_logs(spec.source, level=spec.level)
        return [entry for entry in entries if _matches(entry, spec)]

    def render(self, entries: list[LogEntry] | None = None) -> str:
        """Format matching entries according to the configured output format."""
        spec = self.build()
        if entries is None:
            entries = self.collect()
        return format_extract(entries, spec.output_format)

    def write(self, text: str) -> None:
        """Write formatted extract text to the configured output path."""
        spec = self.build()
        if not spec.output_path:
            raise ValueError("output path is required; call to_file(...) before write()")
        path = Path(spec.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + ("\n" if text else ""), encoding="utf-8")

    def extract(self) -> str:
        """Collect, format, and optionally write the extract; return the text."""
        entries = self.collect()
        text = self.render(entries)
        if self.build().output_path:
            self.write(text)
        return text

def _matches(entry: LogEntry, spec: ExtractSpec) -> bool:
    if spec.contains and spec.contains.lower() not in entry.message.lower():
        return False
    if spec.pattern and re.search(spec.pattern, entry.message) is None:
        return False
    if spec.since and entry.timestamp < spec.since:
        return False
    if spec.until and entry.timestamp > spec.until:
        return False
    return True


def format_extract(entries: list[LogEntry], output_format: str = "raw") -> str:
    """Serialize log entries to raw lines, JSON, or CSV."""
    normalized = output_format.lower().strip()
    if normalized == "raw":
        return "\n".join(entry.raw for entry in entries)
    if normalized == "json":
        payload = [
            {"timestamp": e.timestamp, "level": e.level, "message": e.message} for e in entries
        ]
        return json.dumps(payload, indent=2)
    if normalized == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["timestamp", "level", "message"])
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {"timestamp": entry.timestamp, "level": entry.level, "message": entry.message}
            )
        return buffer.getvalue().rstrip("\n")
    supported = ", ".join(sorted(ExtractBuilder.SUPPORTED_FORMATS))
    raise ValueError(f"unsupported format {output_format!r}; choose one of: {supported}")


def spec_as_dict(spec: ExtractSpec) -> dict[str, str | None]:
    """Helper for debugging / serialization of an extract spec."""
    return asdict(spec)
