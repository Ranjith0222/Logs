from pathlib import Path

import pytest

from logs.cli import main
from logs.extract import ExtractBuilder, format_extract
from logs.ruleset import extract_rulesets
from logs.scraper import parse_log_line, scrape_logs

SAMPLE_LINES = "\n".join(
    [
        "2026-08-05 10:00:00 INFO Server started",
        "2026-08-05 10:00:01 ERROR Disk full",
        "2026-08-05 10:00:02 WARN Retrying connection",
        "2026-08-05 10:00:03 ERROR Failed to rotate logs",
    ]
)

FIXTURE = Path(__file__).parent / "fixtures" / "building_ruleset_snippet.log"


@pytest.fixture
def sample_log(tmp_path: Path) -> Path:
    path = tmp_path / "app.log"
    path.write_text(SAMPLE_LINES, encoding="utf-8")
    return path


def test_parse_log_line_valid() -> None:
    entry = parse_log_line("2026-08-05 10:00:00 INFO Server started")
    assert entry is not None
    assert entry.level == "INFO"
    assert entry.message == "Server started"


def test_parse_log_line_invalid() -> None:
    assert parse_log_line("not a log line") is None


def test_scrape_logs_filters_by_level(sample_log: Path) -> None:
    errors = scrape_logs(str(sample_log), level="ERROR")
    assert len(errors) == 2
    assert errors[0].message == "Disk full"


def test_extract_builder_filters_and_json(sample_log: Path) -> None:
    builder = (
        ExtractBuilder()
        .from_source(str(sample_log))
        .level("ERROR")
        .contains("Disk")
        .as_json()
    )
    entries = builder.collect()
    assert len(entries) == 1
    assert entries[0].message == "Disk full"

    payload = builder.render(entries)
    assert '"level": "ERROR"' in payload
    assert "Disk full" in payload


def test_extract_builder_regex_and_time_window(sample_log: Path) -> None:
    entries = (
        ExtractBuilder()
        .from_source(str(sample_log))
        .matching(r"rotate|connection")
        .since("2026-08-05 10:00:02")
        .until("2026-08-05 10:00:03")
        .collect()
    )
    assert [e.message for e in entries] == [
        "Retrying connection",
        "Failed to rotate logs",
    ]


def test_extract_builder_csv_and_write(sample_log: Path, tmp_path: Path) -> None:
    out = tmp_path / "out" / "errors.csv"
    text = (
        ExtractBuilder()
        .from_source(str(sample_log))
        .level("ERROR")
        .as_csv()
        .to_file(str(out))
        .extract()
    )
    assert out.exists()
    assert "timestamp,level,message" in text
    assert "Disk full" in text
    assert out.read_text(encoding="utf-8").startswith("timestamp,level,message")


def test_extract_builder_requires_source() -> None:
    with pytest.raises(ValueError, match="source is required"):
        ExtractBuilder().build()


def test_extract_builder_rejects_bad_format(sample_log: Path) -> None:
    with pytest.raises(ValueError, match="unsupported format"):
        ExtractBuilder().from_source(str(sample_log)).format("xml")


def test_extract_builder_rejects_inverted_window(sample_log: Path) -> None:
    with pytest.raises(ValueError, match="since must be less than or equal to until"):
        (
            ExtractBuilder()
            .from_source(str(sample_log))
            .since("2026-08-05 11:00:00")
            .until("2026-08-05 10:00:00")
            .build()
        )


def test_format_extract_raw(sample_log: Path) -> None:
    entries = scrape_logs(str(sample_log), level="WARN")
    assert format_extract(entries, "raw") == "2026-08-05 10:00:02 WARN Retrying connection"


def test_cli_extract_json(sample_log: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main([str(sample_log), "--level", "ERROR", "--format", "json", "--quiet"])
    assert code == 0
    captured = capsys.readouterr()
    assert '"Disk full"' in captured.out
    assert captured.err == ""


def test_extract_building_ruleset_from_fixture() -> None:
    extract = extract_rulesets(str(FIXTURE), ruleset_name="Building")
    assert extract.header.module_id == "UW"
    assert extract.header.project_id == "FICUW_ItemRating"
    assert extract.header.policy_no == "PMBP001030043Z02000"
    assert len(extract.rulesets) == 1

    building = extract.rulesets[0]
    assert building.name == "Building"
    assert building.precondition.status == "satisfied"
    assert "IUWP1_MGA_ID IN MGA1" in (building.precondition.expression or "")

    inputs = {item.name: item for item in building.inputs}
    assert inputs["BuildingLimit"].value == "1516320.00"
    assert inputs["BuildingLimit"].type == "NUMBER"
    assert inputs["State"].value == "MI"
    assert inputs["BuildingID"].value == "0001"
    assert inputs["Source"].value == "B2B"

    outputs = {item.name: item.value for item in building.outputs}
    assert outputs["BuildingCoverBaseRate"] == "0.1650000"
    assert outputs["BuildingCoverIncrementalPrem"] == "3882.0000000"
    assert outputs["BuildingCoverIncrementalSI"] == "1516320.00"
    assert outputs["CoverageNewPremium"] == "3882.0000000"

    evaluations = {item.name: item for item in building.evaluations}
    assert evaluations["ClassCode"].value == "09031_5812_722211"
    assert evaluations["ClassCode"].kind == "formula"
    assert evaluations["PropertyRateNumbers"].kind == "decision_table"
    assert evaluations["FinICvgPrem"].value == "3882.0000000"


def test_extract_builder_ruleset_json() -> None:
    text = (
        ExtractBuilder()
        .from_source(str(FIXTURE))
        .ruleset("Building")
        .as_json()
        .extract()
    )
    assert '"name": "Building"' in text
    assert "BuildingCoverAnnPrem" in text


def test_cli_building_ruleset(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([str(FIXTURE), "--ruleset", "Building", "--quiet"])
    assert code == 0
    captured = capsys.readouterr()
    assert '"BuildingCoverIncrementalSI"' in captured.out
    assert "Matched" not in captured.err


def test_satisfied_only_filters_failed_rulesets() -> None:
    extract = extract_rulesets(str(FIXTURE), satisfied_only=True)
    names = [ruleset.name for ruleset in extract.rulesets]
    assert "Building" in names
    assert "BuildBPPSICvgDefaultB2C48" not in names
