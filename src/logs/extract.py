from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Self

from logs.ruleset import (
    BUILDING_RATING_FACTORS,
    RulesetLogExtract,
    extract_rulesets,
    fields_payload,
    is_ruleset_log,
    read_text_source,
)
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
    ruleset_name: str | None = None
    satisfied_only: bool = False
    fields: tuple[str, ...] | None = None
    output_format: str = "raw"
    output_path: str | None = None


class ExtractBuilder:
    """Fluent builder for composing and running log extracts.

    Supports structured line logs and UW ruleset execution logs::

        text = (
            ExtractBuilder()
            .from_source("samples/uw_item_rating_building.log")
            .ruleset("Building")
            .fields(BUILDING_RATING_FACTORS)
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
        self._ruleset_name: str | None = None
        self._satisfied_only: bool = False
        self._fields: tuple[str, ...] | None = None
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

    def ruleset(self, name: str | None) -> Self:
        self._ruleset_name = name.strip() if name else None
        return self

    def satisfied_only(self, enabled: bool = True) -> Self:
        self._satisfied_only = enabled
        return self

    def fields(self, names: list[str] | tuple[str, ...] | None) -> Self:
        if not names:
            self._fields = None
            return self
        cleaned = tuple(name.strip() for name in names if name and name.strip())
        if not cleaned:
            raise ValueError("fields must include at least one non-empty name")
        self._fields = cleaned
        return self

    def building_factors(self) -> Self:
        """Select the standard Building rating factor field set."""
        return self.fields(BUILDING_RATING_FACTORS)

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
            ruleset_name=self._ruleset_name,
            satisfied_only=self._satisfied_only,
            fields=self._fields,
            output_format=self._output_format,
            output_path=self._output_path,
        )

    def _uses_ruleset_mode(self, spec: ExtractSpec) -> bool:
        if spec.ruleset_name is not None or spec.satisfied_only or spec.fields is not None:
            return True
        return is_ruleset_log(read_text_source(spec.source))

    def collect(self) -> list[LogEntry] | RulesetLogExtract:
        """Run the extract and return matching entries or a ruleset extract."""
        spec = self.build()
        if self._uses_ruleset_mode(spec):
            return extract_rulesets(
                spec.source,
                ruleset_name=spec.ruleset_name,
                satisfied_only=spec.satisfied_only,
            )

        entries = scrape_logs(spec.source, level=spec.level)
        return [entry for entry in entries if _matches(entry, spec)]

    def render(self, payload: list[LogEntry] | RulesetLogExtract | None = None) -> str:
        """Format extract results according to the configured output format."""
        spec = self.build()
        if payload is None:
            payload = self.collect()
        if isinstance(payload, RulesetLogExtract):
            return format_ruleset_extract(
                payload,
                spec.output_format,
                fields=spec.fields,
            )
        return format_extract(payload, spec.output_format)

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
        payload = self.collect()
        text = self.render(payload)
        if self.build().output_path:
            self.write(text)
        return text

    def match_count(self, payload: list[LogEntry] | RulesetLogExtract | None = None) -> int:
        if payload is None:
            payload = self.collect()
        if isinstance(payload, RulesetLogExtract):
            return len(payload.rulesets)
        return len(payload)


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
    """Serialize structured line-log entries to raw lines, JSON, or CSV."""
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


def format_ruleset_extract(
    extract: RulesetLogExtract,
    output_format: str = "json",
    fields: tuple[str, ...] | list[str] | None = None,
) -> str:
    """Serialize a ruleset extract to JSON, CSV summary, or raw text."""
    normalized = output_format.lower().strip()
    if fields:
        return _format_ruleset_fields(extract, normalized, tuple(fields))

    data = extract.to_dict()
    if normalized == "json":
        return json.dumps(data, indent=2)
    if normalized == "raw":
        lines: list[str] = []
        header = data["header"]
        lines.append(
            " | ".join(
                f"{key}={header[key]}"
                for key in (
                    "module_id",
                    "project_id",
                    "policy_no",
                    "effective_date",
                    "param_values",
                )
                if header.get(key) is not None
            )
        )
        for ruleset in data["rulesets"]:
            lines.append(f"RULESET NAME :: {ruleset['name']}")
            precondition = ruleset["precondition"]
            if precondition.get("status"):
                lines.append(
                    f"  precondition={precondition['status']}: {precondition.get('expression')}"
                )
            for item in ruleset["inputs"]:
                lines.append(f"  INPUT {item['name']}={item['value']}")
            for item in ruleset["evaluations"]:
                lines.append(f"  EVAL[{item['kind']}] {item['name']}={item['value']}")
            for item in ruleset["outputs"]:
                lines.append(f"  OUTPUT {item['name']}={item['value']}")
        return "\n".join(lines)
    if normalized == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "ruleset",
                "precondition_status",
                "section",
                "name",
                "value",
                "type",
                "kind",
            ],
        )
        writer.writeheader()
        for ruleset in extract.rulesets:
            status = ruleset.precondition.status
            for item in ruleset.inputs:
                writer.writerow(
                    {
                        "ruleset": ruleset.name,
                        "precondition_status": status,
                        "section": "input",
                        "name": item.name,
                        "value": item.value,
                        "type": item.type or "",
                        "kind": "",
                    }
                )
            for item in ruleset.evaluations:
                writer.writerow(
                    {
                        "ruleset": ruleset.name,
                        "precondition_status": status,
                        "section": "evaluation",
                        "name": item.name,
                        "value": item.value,
                        "type": "",
                        "kind": item.kind,
                    }
                )
            for item in ruleset.outputs:
                writer.writerow(
                    {
                        "ruleset": ruleset.name,
                        "precondition_status": status,
                        "section": "output",
                        "name": item.name,
                        "value": item.value,
                        "type": "",
                        "kind": "",
                    }
                )
        return buffer.getvalue().rstrip("\n")
    supported = ", ".join(sorted(ExtractBuilder.SUPPORTED_FORMATS))
    raise ValueError(f"unsupported format {output_format!r}; choose one of: {supported}")


def _format_ruleset_fields(
    extract: RulesetLogExtract,
    output_format: str,
    fields: tuple[str, ...],
) -> str:
    payload = fields_payload(extract, fields)
    if output_format == "json":
        # Flat map when a single ruleset is selected; otherwise keep ruleset grouping.
        if len(payload["rulesets"]) == 1:
            return json.dumps(payload["rulesets"][0]["fields"], indent=2)
        return json.dumps(
            {
                ruleset["name"]: ruleset["fields"]
                for ruleset in payload["rulesets"]
            },
            indent=2,
        )
    if output_format == "raw":
        lines: list[str] = []
        for ruleset in payload["rulesets"]:
            if len(payload["rulesets"]) > 1:
                lines.append(f"RULESET NAME :: {ruleset['name']}")
            for name, value in ruleset["fields"].items():
                lines.append(f"{name}={value if value is not None else ''}")
        return "\n".join(lines)
    if output_format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["ruleset", "name", "value", "source", "found"])
        writer.writeheader()
        for ruleset in payload["rulesets"]:
            for detail in ruleset["field_details"]:
                writer.writerow(
                    {
                        "ruleset": ruleset["name"],
                        "name": detail["name"],
                        "value": detail["value"] if detail["value"] is not None else "",
                        "source": detail["source"] or "",
                        "found": detail["found"],
                    }
                )
        return buffer.getvalue().rstrip("\n")
    supported = ", ".join(sorted(ExtractBuilder.SUPPORTED_FORMATS))
    raise ValueError(f"unsupported format {output_format!r}; choose one of: {supported}")


def spec_as_dict(spec: ExtractSpec) -> dict[str, Any]:
    """Helper for debugging / serialization of an extract spec."""
    return asdict(spec)
