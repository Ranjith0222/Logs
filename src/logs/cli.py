from __future__ import annotations

import argparse
import re
import sys

import requests

from logs.extract import ExtractBuilder


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
        "--format",
        choices=sorted(ExtractBuilder.SUPPORTED_FORMATS),
        default="raw",
        help="Output format for the extract (default: raw)",
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
        builder = (
            ExtractBuilder()
            .from_source(args.source)
            .level(args.level)
            .contains(args.contains)
            .matching(args.pattern)
            .since(args.since)
            .until(args.until)
            .format(args.format)
            .to_file(args.output)
        )
        entries = builder.collect()
        text = builder.render(entries)
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
        print(f"Matched {len(entries)} log entries.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
