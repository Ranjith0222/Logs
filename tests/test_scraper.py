from pathlib import Path

from logs.scraper import parse_log_line, scrape_logs


def test_parse_log_line_valid() -> None:
    entry = parse_log_line("2026-08-05 10:00:00 INFO Server started")
    assert entry is not None
    assert entry.level == "INFO"
    assert entry.message == "Server started"


def test_parse_log_line_invalid() -> None:
    assert parse_log_line("not a log line") is None


def test_scrape_logs_filters_by_level(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text(
        "\n".join(
            [
                "2026-08-05 10:00:00 INFO Server started",
                "2026-08-05 10:00:01 ERROR Disk full",
                "2026-08-05 10:00:02 WARN Retrying connection",
            ]
        ),
        encoding="utf-8",
    )

    errors = scrape_logs(str(log_file), level="ERROR")
    assert len(errors) == 1
    assert errors[0].message == "Disk full"
