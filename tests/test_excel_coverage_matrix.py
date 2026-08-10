"""Comprehensive Excel export / coverage-wise test matrix.

Covers:
1. LiabilityPremiumNB1 limit branches (all formula paths)
2. Coverage-wise row filter (valued vs zero)
3. Section limits (Building / BPP / Liability)
4. Coverage-wise Excel columns (K–O)
5. Section factor columns (refined F/G/H vs legacy U/V/W)
6. Policy header / IRPM
7. BOP coverage label mapping
8. Edge cases (missing ruleset, empty template cells, Total row)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from logs.coverages import (
    CoverageRow,
    coverage_row_has_value,
    extract_coverage_rows,
    is_nonzero_amount,
    load_coverage_descriptions,
    resolve_liability_occurrence_limit,
    resolve_liability_rating_limit,
)
from logs.excel_export import (
    build_excel_from_log,
    collect_section_limits,
    detect_coverage_table,
    detect_section_columns,
    fill_coverage_table,
    fill_limits,
    fill_policy_header,
)

COVERAGE_FIXTURE = Path(__file__).parent / "fixtures" / "coverage_rating_snippet.log"
BUILDING_FIXTURE = Path(__file__).parent / "fixtures" / "building_ruleset_snippet.log"
FULL_SAMPLE = Path(__file__).parents[1] / "samples" / "uw_item_rating_building.log"
CLASS_CODE_TEMPLATE = Path("templates/class_code_template.xlsx")
LEGACY_TEMPLATE = Path("templates/policy_rating_template.xlsx")
BOP_COVERAGES = Path("templates/BOP_coverages.xlsx")

BUILDING = "3141815.00"
BPP = "10000.00"
TURNOVER = "390000"
PAYROLL = "800000.00"


def _limit(
    *,
    exp_base: str,
    category: str,
    status: str = "L",
    building: str = BUILDING,
    bpp: str = BPP,
    turnover: str = TURNOVER,
    payroll: str = PAYROLL,
) -> str | None:
    inputs = {
        "BuildingLimit": building,
        "BusiPersonalPropLimit": bpp,
        "BusinessCatgeory": category,
    }
    evaluations = {
        "LiabilityExpBase": exp_base,
        "AnnualTurnover": turnover,
        "Payroll": payroll,
        "18InsuredStatus": status if category == "18" else "L",
        "N18InsuredStatus": status if category != "18" else "O",
    }
    return resolve_liability_rating_limit(inputs, {}, evaluations)


# ---------------------------------------------------------------------------
# 1. LiabilityPremiumNB1 — all formula branches
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("exp_base", "category", "status", "expected"),
    [
        # SALES
        ("SALES", "18", "L", BUILDING),
        ("SALES", "18", "COL", BUILDING),
        ("SALES", "14", "O", TURNOVER),
        ("SALES", "16", "O", TURNOVER),
        # PAY
        ("PAY", "18", "L", BUILDING),
        ("PAY", "14", "O", PAYROLL),
        # LOI + Lessors (18)
        ("LOI", "18", "L", BUILDING),
        ("LOI", "18", "COL", BUILDING),
        # LOI + Occupant with BPP
        ("LOI", "14", "O", BPP),
        # LOI + Occupant with zero BPP → BuildingLimit
        # (handled in dedicated test below)
        # LOI + Lessor-like non-18
        ("LOI", "14", "L", BUILDING),
        ("LOI", "14", "COL", BUILDING),
        # Unknown / empty exp base → BuildingLimit (else branch)
        ("", "18", "L", BUILDING),
        ("OTHER", "14", "O", BUILDING),
    ],
)
def test_liability_premium_nb1_limit_matrix(
    exp_base: str,
    category: str,
    status: str,
    expected: str,
) -> None:
    assert _limit(exp_base=exp_base, category=category, status=status) == expected


def test_liability_loi_occupant_zero_bpp_uses_building_limit() -> None:
    assert (
        _limit(exp_base="LOI", category="14", status="O", bpp="0.00") == BUILDING
    )


def test_liability_sales_missing_turnover_falls_back_to_building() -> None:
    inputs = {"BuildingLimit": BUILDING, "BusinessCatgeory": "14"}
    evaluations = {"LiabilityExpBase": "SALES"}  # no AnnualTurnover
    assert resolve_liability_rating_limit(inputs, {}, evaluations) == BUILDING


def test_liability_occurrence_limit_uses_final_building_400127() -> None:
    assert (
        resolve_liability_occurrence_limit(
            {"BUserSI": "1000000.00", "400127BUserSI": "1000000.00"},
            {"BuildingCoverIncrementalSI": "1000000.00, 2000000.00, 2000000.00"},
            {"FinalBuilding400127SI": "1000000.00", "FinalBuilding400129SI": "2000000.00"},
        )
        == "1000000.00"
    )


def test_liability_occurrence_limit_prefers_final_over_list() -> None:
    # First list value happens to match occurrence; prefer named final field.
    assert (
        resolve_liability_occurrence_limit(
            {},
            {"BuildingCoverIncrementalSI": "999.00, 2000000.00, 2000000.00"},
            {"FinalBuilding400127SI": "1000000.00"},
        )
        == "1000000.00"
    )


# ---------------------------------------------------------------------------
# 2. Coverage-wise value filter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("row", "keep"),
    [
        (
            CoverageRow("400101", "Building", "100", "0.2", "0.1", "50"),
            True,
        ),
        (
            CoverageRow("400102", "BPP", "10000", "1.3", "1.1", "115"),
            True,
        ),
        (
            CoverageRow("400127", "Liability", "3141815", "0.042", "0.035", "1100"),
            True,
        ),
        # Non-core with premium only
        (
            CoverageRow("400136", "Hired Auto", "0", None, None, "28"),
            True,
        ),
        # Non-core all zeros → drop
        (
            CoverageRow("400114", "Outdoor Signs", "0", "0", "0", "0"),
            False,
        ),
        # Non-core SI + rates but $0 premium → drop
        (
            CoverageRow("400103", "AR", "10000", "1.4", "1.2", "0"),
            False,
        ),
        # Core Building with SI only still kept
        (
            CoverageRow("400101", "Building", "3141815", None, None, None),
            True,
        ),
        # Empty row → drop
        (
            CoverageRow("400999", "Other", None, None, None, None),
            False,
        ),
    ],
)
def test_coverage_row_has_value_matrix(row: CoverageRow, keep: bool) -> None:
    assert coverage_row_has_value(row) is keep


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", False),
        ("0.0", False),
        ("0.00", False),
        ("0.0000000", False),
        (None, False),
        ("", False),
        ("1", True),
        ("1000000.00", True),
        ("0.0350000", True),
        ("1000000.00, 2000000.00", True),
    ],
)
def test_is_nonzero_amount_matrix(raw: str | None, expected: bool) -> None:
    assert is_nonzero_amount(raw) is expected


# ---------------------------------------------------------------------------
# 3. Fixture / log extraction
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not COVERAGE_FIXTURE.exists(), reason="coverage fixture missing")
def test_extract_building_bpp_liability_from_fixture() -> None:
    rows = {r.code: r for r in extract_coverage_rows(COVERAGE_FIXTURE, coverages_path=BOP_COVERAGES)}
    assert rows["400101"].sum_insured == "3141815.00"
    assert rows["400101"].base_rate == "0.2110000"
    assert rows["400101"].final_rate == "0.1780000"
    assert rows["400101"].premium == "5593.0000000"
    assert rows["400102"].sum_insured == "10000.00"
    assert rows["400102"].premium == "115.0000000"
    assert rows["400127"].label == "Liability"
    assert rows["400127"].sum_insured == "3141815.00"  # SALES+18 → BuildingLimit
    assert rows["400127"].base_rate == "0.0420000"
    assert rows["400127"].final_rate == "0.0350000"
    assert rows["400127"].premium == "1100.0000000"


@pytest.mark.skipif(not COVERAGE_FIXTURE.exists(), reason="coverage fixture missing")
def test_extract_drops_zero_premium_non_core_coverages() -> None:
    rows = extract_coverage_rows(COVERAGE_FIXTURE, coverages_path=BOP_COVERAGES)
    codes = {r.code for r in rows}
    assert "400101" in codes
    assert "400102" in codes
    assert "400127" in codes
    # Zero-premium defaults should not appear
    assert "400105" not in codes  # Automatic Increase
    assert "400513" not in codes  # BI revised period
    assert "400114" not in codes  # Outdoor Signs (rates, $0 prem)


@pytest.mark.skipif(not COVERAGE_FIXTURE.exists(), reason="coverage fixture missing")
def test_extract_keeps_premium_only_endorsements() -> None:
    rows = {r.code: r for r in extract_coverage_rows(COVERAGE_FIXTURE, coverages_path=BOP_COVERAGES)}
    # RCFlagN=N coverages must be excluded even with residual premium
    assert "400136" not in rows  # Hired Auto unselected
    assert "400440" not in rows  # Non-owned Auto unselected
    # Selected endorsement bundle must appear
    assert "400503" in rows
    assert float(rows["400503"].premium) == 542


@pytest.mark.skipif(not COVERAGE_FIXTURE.exists(), reason="coverage fixture missing")
def test_section_limits_match_liability_premium_nb1() -> None:
    limits = collect_section_limits(COVERAGE_FIXTURE)
    assert limits["building"] == "3141815.00"
    assert limits["bpp"] == "10000.00"
    assert limits["liability"] == "3141815.00"


# ---------------------------------------------------------------------------
# 4. Template detection
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not CLASS_CODE_TEMPLATE.exists(), reason="class-code template missing")
def test_detect_refined_template_columns() -> None:
    wb = load_workbook(CLASS_CODE_TEMPLATE)
    cols = detect_section_columns(wb)
    assert cols["Building"] == "F"
    assert cols["Business Personal Property"] == "G"
    assert cols["Liability"] == "H"
    table = detect_coverage_table(wb)
    assert table is not None
    assert table["coverage"] == (3, 11)  # K3
    assert table["sum_insured"] == (3, 12)  # L3
    assert table["base_rate"] == (3, 13)  # M3
    assert table["final_rate"] == (3, 14)  # N3
    assert table["premium"] == (3, 15)  # O3


@pytest.mark.skipif(not LEGACY_TEMPLATE.exists(), reason="legacy template missing")
def test_detect_legacy_template_columns() -> None:
    wb = load_workbook(LEGACY_TEMPLATE)
    cols = detect_section_columns(wb)
    assert cols["Building"] == "U"
    assert cols["Business Personal Property"] == "V"
    assert cols["Liability"] == "W"
    table = detect_coverage_table(wb)
    assert table is not None
    # Leftmost Coverage Code block
    assert table["coverage"][1] == 10  # column J


# ---------------------------------------------------------------------------
# 5. End-to-end Excel fill — refined class-code template
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (COVERAGE_FIXTURE.exists() and CLASS_CODE_TEMPLATE.exists()),
    reason="fixture/template missing",
)
def test_excel_coverage_wise_headers_and_core_rows(tmp_path: Path) -> None:
    out = tmp_path / "out.xlsx"
    build_excel_from_log(
        COVERAGE_FIXTURE,
        out,
        template=CLASS_CODE_TEMPLATE,
        coverages_path=BOP_COVERAGES,
    )
    ws = load_workbook(out).active
    assert ws["K3"].value == "Coverage Code"
    assert ws["L3"].value == "Sum Insured"
    assert ws["M3"].value == "Base Rate"
    assert ws["N3"].value == "Final Rate"
    assert ws["O3"].value == "Premium"

    assert ws["K4"].value == "Building"
    assert ws["L4"].value == 3141815
    assert ws["M4"].value == 0.211
    assert ws["N4"].value == 0.178
    assert ws["O4"].value == 5593


@pytest.mark.skipif(
    not (COVERAGE_FIXTURE.exists() and CLASS_CODE_TEMPLATE.exists()),
    reason="fixture/template missing",
)
def test_excel_limits_row_building_bpp_liability(tmp_path: Path) -> None:
    out = tmp_path / "out.xlsx"
    build_excel_from_log(COVERAGE_FIXTURE, out, template=CLASS_CODE_TEMPLATE)
    ws = load_workbook(out).active
    assert ws["F3"].value == 3141815
    assert ws["G3"].value == 10000
    assert ws["H3"].value == 3141815  # LiabilityPremiumNB1 BuildingLimit


@pytest.mark.skipif(
    not (COVERAGE_FIXTURE.exists() and CLASS_CODE_TEMPLATE.exists()),
    reason="fixture/template missing",
)
def test_excel_liability_coverage_row_uses_building_limit(tmp_path: Path) -> None:
    out = tmp_path / "out.xlsx"
    build_excel_from_log(COVERAGE_FIXTURE, out, template=CLASS_CODE_TEMPLATE)
    ws = load_workbook(out).active
    liab_row = next(r for r in range(4, 40) if ws.cell(r, 11).value == "Liability")
    assert ws.cell(liab_row, 12).value == 3141815
    assert ws.cell(liab_row, 13).value == 0.042
    assert ws.cell(liab_row, 14).value == 0.035
    assert ws.cell(liab_row, 15).value == 1100


@pytest.mark.skipif(
    not (COVERAGE_FIXTURE.exists() and CLASS_CODE_TEMPLATE.exists()),
    reason="fixture/template missing",
)
def test_excel_total_premium_equals_sum_of_row_premiums(tmp_path: Path) -> None:
    out = tmp_path / "out.xlsx"
    build_excel_from_log(COVERAGE_FIXTURE, out, template=CLASS_CODE_TEMPLATE)
    ws = load_workbook(out).active
    premiums: list[float] = []
    total = None
    for r in range(4, 40):
        label = ws.cell(r, 14).value
        prem = ws.cell(r, 15).value
        if label == "Total":
            total = prem
            break
        if isinstance(prem, (int, float)):
            premiums.append(float(prem))
    assert total is not None
    assert total == int(sum(premiums)) if float(sum(premiums)).is_integer() else sum(premiums)
    assert total == 7350  # 5593+115+1100+542 (selected bundle; Hired/Non-owned excluded)


@pytest.mark.skipif(
    not (COVERAGE_FIXTURE.exists() and CLASS_CODE_TEMPLATE.exists()),
    reason="fixture/template missing",
)
def test_excel_no_zero_only_coverage_rows(tmp_path: Path) -> None:
    out = tmp_path / "out.xlsx"
    build_excel_from_log(COVERAGE_FIXTURE, out, template=CLASS_CODE_TEMPLATE)
    ws = load_workbook(out).active
    for r in range(4, 40):
        name = ws.cell(r, 11).value
        if name is None or ws.cell(r, 14).value == "Total":
            continue
        si, base, final, prem = (ws.cell(r, c).value for c in range(12, 16))
        nums = [v for v in (si, base, final, prem) if isinstance(v, (int, float))]
        assert any(v != 0 for v in nums), f"{name} is all-zero"


@pytest.mark.skipif(
    not (COVERAGE_FIXTURE.exists() and CLASS_CODE_TEMPLATE.exists()),
    reason="fixture/template missing",
)
def test_excel_irpm_header_updated(tmp_path: Path) -> None:
    out = tmp_path / "out.xlsx"
    build_excel_from_log(COVERAGE_FIXTURE, out, template=CLASS_CODE_TEMPLATE)
    ws = load_workbook(out).active
    assert str(ws["E2"].value).startswith("With IRPM")
    assert "-0.23" in str(ws["E2"].value).replace(" ", "") or "-0.2300000" in str(
        ws["E2"].value
    )


@pytest.mark.skipif(
    not (COVERAGE_FIXTURE.exists() and CLASS_CODE_TEMPLATE.exists()),
    reason="fixture/template missing",
)
def test_excel_policy_number_in_a1(tmp_path: Path) -> None:
    out = tmp_path / "out.xlsx"
    build_excel_from_log(COVERAGE_FIXTURE, out, template=CLASS_CODE_TEMPLATE)
    ws = load_workbook(out).active
    assert ws["A1"].value
    assert "PMBP" in str(ws["A1"].value).upper()


# ---------------------------------------------------------------------------
# 6. End-to-end — legacy dual-panel template
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (FULL_SAMPLE.exists() and LEGACY_TEMPLATE.exists()),
    reason="full sample/legacy template missing",
)
def test_excel_legacy_fills_uvw_factors_and_limits(tmp_path: Path) -> None:
    out = tmp_path / "legacy.xlsx"
    build_excel_from_log(FULL_SAMPLE, out, template=LEGACY_TEMPLATE)
    ws = load_workbook(out).active
    assert ws["U6"].value == 3.302
    assert ws["V6"].value == 3.257
    assert ws["W5"].value == 0.008
    assert ws["F3"].value == 1516320
    assert ws["G3"].value == 5000
    assert ws["H3"].value == 1516320
    assert ws["U3"].value == 1516320
    assert ws["W3"].value == 1516320


# ---------------------------------------------------------------------------
# 7. BOP coverages mapping
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not BOP_COVERAGES.exists(), reason="BOP coverages missing")
def test_bop_coverages_maps_core_codes() -> None:
    mapping = load_coverage_descriptions(BOP_COVERAGES)
    assert mapping["400101"] == "Building"
    assert mapping["400102"] == "Business Personal Property"
    assert "Liability" in mapping["400127"]
    assert mapping["400136"]  # Hired Auto


# ---------------------------------------------------------------------------
# 8. Unit helpers / edge cases on blank workbook
# ---------------------------------------------------------------------------


def test_fill_policy_header_writes_irpm_on_existing_label() -> None:
    wb = Workbook()
    ws = wb.active
    ws["E2"] = "With IRPM  0.25"
    fill_policy_header(wb, policy_no="PMBPTEST001", irpm="-0.2300000")
    assert ws["A1"].value == "PMBPTEST001"
    assert ws["E2"].value == "With IRPM  -0.2300000"


def test_fill_coverage_table_noop_without_headers(tmp_path: Path) -> None:
    wb = Workbook()
    assert fill_coverage_table(wb, BUILDING_FIXTURE) == 0


def test_fill_limits_writes_fgh_when_building_present() -> None:
    if not BUILDING_FIXTURE.exists():
        pytest.skip("building fixture missing")
    wb = Workbook()
    fill_limits(wb, BUILDING_FIXTURE)
    ws = wb.active
    assert ws["F3"].value == 1516320
    assert ws["G3"].value == 5000
