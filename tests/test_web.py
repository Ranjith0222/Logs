from pathlib import Path

from fastapi.testclient import TestClient

from logs.web.app import app

FIXTURE = Path(__file__).parent / "fixtures" / "building_ruleset_snippet.log"


def test_gui_index_serves_brand() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "LOGS" in response.text
    assert "Extract Building rating factors" in response.text


def test_gui_extract_building_factors() -> None:
    client = TestClient(app)
    with FIXTURE.open("rb") as handle:
        response = client.post(
            "/api/extract",
            files={"file": ("building.log", handle, "text/plain")},
            data={"ruleset": "Building", "mode": "building-factors"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "building-factors"
    fields = payload["rulesets"][0]["fields"]
    assert fields["LCMFactor"] == "1.890"
    assert fields["IRPMFactor"] == "-0.1800000"
    assert fields["BaseLCfac"] == "0.186"
    assert fields["FixedDedFactor"] == "0.886"


def test_gui_extract_missing_ruleset() -> None:
    client = TestClient(app)
    with FIXTURE.open("rb") as handle:
        response = client.post(
            "/api/extract",
            files={"file": ("building.log", handle, "text/plain")},
            data={"ruleset": "DoesNotExist", "mode": "building-factors"},
        )
    assert response.status_code == 404
