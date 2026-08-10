from pathlib import Path

from openpyxl import load_workbook

from logs.excel_export import build_excel_from_log

FIXTURE = Path(__file__).parent / "fixtures" / "building_ruleset_snippet.log"


def test_build_excel_fills_building_factor_column(tmp_path: Path) -> None:
    out = tmp_path / "PMBP001030043Z02000.xlsx"
    result = build_excel_from_log(FIXTURE, out, ruleset="Building")
    assert result.exists()

    wb = load_workbook(result)
    ws = wb[wb.sheetnames[0]]
    assert ws["A1"].value == "PMBP001030043Z02000"
    assert ws["U6"].value == 3.302  # OccRelativityFactor
    assert ws["U7"].value == 0.759  # BuiConstructionRelativitiesFactor
    assert ws["U9"].value == 1.0  # PPCFac
    assert ws["U13"].value == 1.89  # LCMFactor
    assert ws["U14"].value == -0.18  # IRPMFactor
    assert "Build" in wb.sheetnames
    assert any(name.strip() == "Item" for name in wb.sheetnames)
