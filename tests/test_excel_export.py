from pathlib import Path

from openpyxl import load_workbook

from logs.excel_export import (
    build_excel_from_log,
    collect_all_section_values,
    collect_section_limits,
)

FIXTURE = Path(__file__).parent / "fixtures" / "building_ruleset_snippet.log"
FULL_SAMPLE = Path(__file__).parents[1] / "samples" / "uw_item_rating_building.log"


def test_build_excel_uses_uploaded_template(tmp_path: Path) -> None:
    template = Path("templates/policy_rating_template.xlsx")
    if not template.exists():
        template = Path("src/logs/data/policy_rating_template.xlsx")
    assert template.exists()
    out = tmp_path / "from_upload.xlsx"
    build_excel_from_log(FIXTURE, out, template=template)
    wb = load_workbook(out)
    assert "Build" in wb.sheetnames
    assert wb.active["U6"].value == 3.302
    # Building + BPP limits from Building ruleset inputs
    assert wb.active["F3"].value == 1516320
    assert wb.active["G3"].value == 5000
    assert wb.active["U3"].value == 1516320
    assert wb.active["V3"].value == 5000


def test_collect_section_limits_from_full_log() -> None:
    if not FULL_SAMPLE.exists():
        return
    limits = collect_section_limits(FULL_SAMPLE)
    assert limits["building"] == "1516320.00"
    assert limits["bpp"] == "5000.00"
    assert limits["liability"] == "1000000.00"


def test_collect_bpp_and_liability_sections() -> None:
    if not FULL_SAMPLE.exists():
        return
    sections = collect_all_section_values(FULL_SAMPLE)
    bpp = sections["Business Personal Property"]
    liab = sections["Liability"]
    assert bpp["occ_rel"] == "3.257"
    assert bpp["construction"] == "0.825"
    assert bpp["loi"] == "1.767"
    assert bpp["deductible"] == "0.886"
    assert liab["liab_class"] == "2.974"
    assert liab["increased_limits"] == "1.074"
    assert liab["prop_damage_ded"] == "1"
    assert liab["base_lc"] == "0.008"


def test_build_excel_fills_bpp_and_liability_columns(tmp_path: Path) -> None:
    if not FULL_SAMPLE.exists():
        return
    out = tmp_path / "multi.xlsx"
    build_excel_from_log(FULL_SAMPLE, out)
    wb = load_workbook(out)
    ws = wb[wb.sheetnames[0]]
    # Building U
    assert ws["U6"].value == 3.302
    # BPP V
    assert ws["V6"].value == 3.257
    assert ws["V7"].value == 0.825
    assert ws["V8"].value == 1.767
    # Liability W
    assert ws["W5"].value == 0.008
    assert ws["W17"].value == 2.974
    assert ws["W18"].value == 1.074
    assert ws["W19"].value == 1
    # Limits row: Building / BPP / Liability (left F/G/H and right U/V/W)
    assert ws["F3"].value == 1516320
    assert ws["G3"].value == 5000
    assert ws["H3"].value == 1000000
    assert ws["U3"].value == 1516320
    assert ws["V3"].value == 5000
    assert ws["W3"].value == 1000000
