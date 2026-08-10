import json
from pathlib import Path

from logs.desktop.service import (
    export_csv_text,
    export_json_text,
    rows_from_payload,
    run_desktop_extract,
)

FIXTURE = Path(__file__).parent / "fixtures" / "building_ruleset_snippet.log"


def test_desktop_extract_building_factors() -> None:
    payload = run_desktop_extract(FIXTURE, ruleset="Building", mode="building-factors")
    fields = payload["rulesets"][0]["fields"]
    assert fields["LCMFactor"] == "1.890"
    assert fields["IRPMFactor"] == "-0.1800000"
    assert fields["BaseLCfac"] == "0.186"
    assert fields["FixedDedFactor"] == "0.886"


def test_desktop_rows_and_exports() -> None:
    payload = run_desktop_extract(FIXTURE, ruleset="Building", mode="building-factors")
    rows = rows_from_payload(payload)
    assert any(row["name"] == "PPCFac" and row["value"] == "1.0" for row in rows)

    data = json.loads(export_json_text(payload))
    assert data["OccRelativityFactor"] == "3.302"

    csv_text = export_csv_text(payload)
    assert csv_text.splitlines()[0] == "name,value,source"
    assert "LCMFactor,1.890,input" in csv_text


def test_desktop_extract_missing_ruleset() -> None:
    try:
        run_desktop_extract(FIXTURE, ruleset="DoesNotExist", mode="building-factors")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "DoesNotExist" in str(exc)
