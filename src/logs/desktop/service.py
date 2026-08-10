from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from logs.ruleset import (
    BUILDING_RATING_FACTORS,
    extract_rulesets,
    fields_payload,
    is_ruleset_log,
)

MODES = ("building-factors", "fields", "full")


def run_desktop_extract(
    path: str | Path,
    *,
    ruleset: str = "Building",
    mode: str = "building-factors",
    fields: str = "",
) -> dict[str, Any]:
    """Run a ruleset extract and return a JSON-serializable payload for the desktop UI."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Log file not found: {source}")

    text = source.read_text(encoding="utf-8", errors="replace")
    if not is_ruleset_log(text):
        raise ValueError("File does not look like a UW ruleset execution log.")

    ruleset_name = ruleset.strip() or None
    extract = extract_rulesets(str(source), ruleset_name=ruleset_name)
    if not extract.rulesets:
        raise ValueError(f"No ruleset named {ruleset!r} found in the log.")

    normalized = mode.strip().lower()
    if normalized in {"building-factors", "factors"}:
        payload = fields_payload(extract, BUILDING_RATING_FACTORS)
        return {
            "mode": "building-factors",
            "filename": source.name,
            "header": payload["header"],
            "requested_fields": payload["requested_fields"],
            "rulesets": payload["rulesets"],
        }

    if normalized == "fields":
        field_names = [part.strip() for part in fields.split(",") if part.strip()]
        if not field_names:
            raise ValueError("Provide at least one field name for Custom fields mode.")
        payload = fields_payload(extract, field_names)
        return {
            "mode": "fields",
            "filename": source.name,
            "header": payload["header"],
            "requested_fields": payload["requested_fields"],
            "rulesets": payload["rulesets"],
        }

    if normalized == "full":
        return {
            "mode": "full",
            "filename": source.name,
            "header": asdict(extract.header),
            "rulesets": [asdict(item) for item in extract.rulesets],
        }

    raise ValueError(f"Unsupported mode {mode!r}. Use one of: {', '.join(MODES)}")


def rows_from_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Flatten an extract payload into table rows."""
    ruleset = (payload.get("rulesets") or [None])[0]
    if not ruleset:
        return []

    if payload.get("mode") == "full":
        rows: list[dict[str, str]] = []
        for item in ruleset.get("inputs") or []:
            rows.append(
                {
                    "name": str(item.get("name", "")),
                    "value": str(item.get("value", "")),
                    "source": "input",
                }
            )
        for item in ruleset.get("evaluations") or []:
            kind = item.get("kind") or "evaluation"
            rows.append(
                {
                    "name": str(item.get("name", "")),
                    "value": str(item.get("value", "")),
                    "source": f"evaluation/{kind}",
                }
            )
        for item in ruleset.get("outputs") or []:
            rows.append(
                {
                    "name": str(item.get("name", "")),
                    "value": str(item.get("value", "")),
                    "source": "output",
                }
            )
        return rows

    details = ruleset.get("field_details") or []
    if details:
        return [
            {
                "name": str(item.get("name", "")),
                "value": "" if item.get("value") is None else str(item.get("value")),
                "source": str(item.get("source") or ""),
            }
            for item in details
        ]

    fields = ruleset.get("fields") or {}
    return [
        {"name": str(name), "value": "" if value is None else str(value), "source": ""}
        for name, value in fields.items()
    ]


def export_json_text(payload: dict[str, Any]) -> str:
    ruleset = (payload.get("rulesets") or [None])[0]
    if not ruleset:
        return "{}\n"
    data = ruleset if payload.get("mode") == "full" else ruleset.get("fields") or {}
    return json.dumps(data, indent=2) + "\n"


def export_csv_text(payload: dict[str, Any]) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["name", "value", "source"])
    writer.writeheader()
    for row in rows_from_payload(payload):
        writer.writerow(row)
    return buffer.getvalue()


def default_export_stem(payload: dict[str, Any]) -> str:
    filename = str(payload.get("filename") or "extract")
    stem = Path(filename).stem
    ruleset = ((payload.get("rulesets") or [{}])[0].get("name") or "ruleset").replace(" ", "_")
    return f"{stem}_{ruleset}"
