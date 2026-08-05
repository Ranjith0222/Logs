from __future__ import annotations

import argparse
import re
import sys

import requests

from logs.extract import ExtractBuilder
from logs.ruleset import BUILDING_RATING_FACTORS, RulesetLogExtract


def _parse_fields(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    names = [part.strip() for part in raw.split(",") if part.strip()]
    if not names:
        raise ValueError("--fields must include at least one field name")
    return names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and run log extracts from local paths or URLs.",
    )
    parser.add_argument("source", help="Path or URL to a log file")
    parser.add_argument(
        "--level",
        help="Only include entries at this log level (e.g. ERROR, WARN, INFO)",
    )
    parser.add_argument(
        "--contains",
        help="Only include entries whose message contains this text (case-insensitive)",
    )
    parser.add_argument(
        "--regex",
        dest="pattern",
        help="Only include entries whose message matches this regular expression",
    )
    parser.add_argument(
        "--since",
        help="Only include entries at or after this timestamp (lexicographic compare)",
    )
    parser.add_argument(
        "--until",
        help="Only include entries at or before this timestamp (lexicographic compare)",
    )
    parser.add_argument(
        "--ruleset",
        help="Extract a UW ruleset execution by name (e.g. Building)",
    )
    parser.add_argument(
        "--satisfied-only",
        action="store_true",
        help="For ruleset logs, only include rulesets whose precondition was satisfied",
    )
    parser.add_argument(
        "--fields",
        help="Comma-separated ruleset field names to extract (inputs/evals/outputs)",
    )
    parser.add_argument(
        "--building-factors",
        action="store_true",
        help=(
            "Extract the standard Building rating factors "
            f"({', '.join(BUILDING_RATING_FACTORS)})"
        ),
    )
    parser.add_argument(
        "--format",
        choices=sorted(ExtractBuilder.SUPPORTED_FORMATS),
        default=None,
        help="Output format for the extract (default: json for rulesets, raw otherwise)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write the extract to this file (stdout is skipped when set)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the match count on stderr",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        field_names = _parse_fields(args.fields)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.building_factors:
        field_names = list(BUILDING_RATING_FACTORS)

    output_format = args.format
    if output_format is None:
        output_format = (
            "json"
            if args.ruleset or args.satisfied_only or field_names
            else "raw"
        )

    try:
        builder = (
            ExtractBuilder()
            .from_source(args.source)
            .level(args.level)
            .contains(args.contains)
            .matching(args.pattern)
            .since(args.since)
            .until(args.until)
            .ruleset(args.ruleset)
            .satisfied_only(args.satisfied_only)
            .fields(field_names)
            .format(output_format)
            .to_file(args.output)
        )
        payload = builder.collect()
        text = builder.render(payload)
        if args.output:
            builder.write(text)
        elif text:
            print(text)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except re.error as exc:
        print(f"Invalid regular expression: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"Failed to fetch remote logs: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        count = (
            len(payload.rulesets)
            if isinstance(payload, RulesetLogExtract)
            else len(payload)
        )
        label = "rulesets" if isinstance(payload, RulesetLogExtract) else "log entries"
        print(f"Matched {count} {label}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
