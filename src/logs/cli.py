from __future__ import annotations

import argparse
import sys

import requests

from logs.scraper import format_entries, scrape_logs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape and filter structured log files.")
    parser.add_argument("source", help="Path or URL to a log file")
    parser.add_argument(
        "--level",
        help="Only include entries at this log level (e.g. ERROR, WARN, INFO)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        entries = scrape_logs(args.source, level=args.level)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"Failed to fetch remote logs: {exc}", file=sys.stderr)
        return 1

    output = format_entries(entries)
    if output:
        print(output)
    print(f"Matched {len(entries)} log entries.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
