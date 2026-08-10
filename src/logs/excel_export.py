from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.workbook.workbook import Workbook as WorkbookType

from logs.coverages import extract_coverage_rows
from logs.ruleset import pick_field_values
from logs.sections import RATING_SECTION_NAMES, SECTION_SPECS, SectionSpec, all_alias_names

TEMPLATE_CANDIDATES = (
    Path(__file__).resolve().parent / "data" / "class_code_template.xlsx",
    Path(__file__).resolve().parents[2] / "templates" / "class_code_template.xlsx",
    Path.cwd() / "templates" / "class_code_template.xlsx",
    Path(__file__).resolve().parent / "data" / "policy_rating_template.xlsx",
    Path(__file__).resolve().parents[2] / "templates" / "policy_rating_template.xlsx",
    Path.cwd() / "templates" / "policy_rating_template.xlsx",
)

SECTION_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "Building": ("Building",),
    "Business Personal Property": (
        "Business Personal Property",
        "BusinessPersonalProperty",
        "BPP",
    ),
    "Liability": ("Liability",),
}


def resolve_template_path(template: str | Path | None = None) -> Path:
    if template:
        path = Path(template)
        if not path.exists():
            raise FileNotFoundError(f"Excel template not found: {path}")
        return path
    for path in TEMPLATE_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Excel template not found. Expected templates/class_code_template.xlsx "
        "or logs/data/class_code_template.xlsx."
    )


def _to_number(raw: str | None) -> float | int | str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    # Liability SI can be comma-separated (e.g. "1000000.00, 2000000.00"); use first.
    if "," in text:
        text = text.split(",", 1)[0].strip()
    try:
        value = float(text)
    except ValueError:
        return text
    if value.is_integer():
        return int(value)
    return value


def _lookup_aliases(values: dict[str, str | None], aliases: tuple[str, ...]) -> str | None:
    for name in aliases:
        if name in values and values[name] is not None and str(values[name]).strip() != "":
            return values[name]
    return None


def _ruleset_io_maps(log_path: str | Path, ruleset_name: str) -> tuple[dict[str, str], dict[str, str]]:
    from logs.ruleset import extract_rulesets

    extract = extract_rulesets(str(log_path), ruleset_name=ruleset_name)
    if not extract.rulesets:
        return {}, {}
    ruleset = extract.rulesets[0]
    inputs = {item.name: item.value for item in ruleset.inputs}
    outputs = {item.name: item.value for item in ruleset.outputs}
    return inputs, outputs


def collect_section_limits(log_path: str | Path) -> dict[str, str | None]:
    """Resolve Building / BPP / Liability limits from the matching rulesets."""
    from logs.coverages import resolve_liability_occurrence_limit
    from logs.ruleset import extract_rulesets

    building_in, building_out = _ruleset_io_maps(log_path, "Building")
    bpp_in, bpp_out = _ruleset_io_maps(log_path, "Business Personal Property")

    building_limit = (
        building_in.get("BuildingLimit")
        or building_out.get("BuildingCoverIncrementalSI")
        or building_in.get("BUserSI")
    )
    bpp_limit = (
        building_in.get("BusinessPersonalPropLimit")
        or bpp_in.get("BusinessPersonalPropLimit")
        or bpp_in.get("BusiPersonalPropLimit")
        or bpp_out.get("BuildingCoverIncrementalSI")
        or bpp_in.get("BUserSI")
        or bpp_in.get("IUserSI")
    )

    liability_limit = None
    liab_extract = extract_rulesets(str(log_path), ruleset_name="Liability")
    if liab_extract.rulesets:
        ruleset = liab_extract.rulesets[0]
        liab_in = {item.name: item.value for item in ruleset.inputs}
        liab_out = {item.name: item.value for item in ruleset.outputs}
        liab_eval = {item.name: item.value for item in ruleset.evaluations}
        liability_limit = resolve_liability_occurrence_limit(liab_in, liab_out, liab_eval)

    return {
        "building": building_limit,
        "bpp": bpp_limit,
        "liability": liability_limit,
    }


def collect_section_values(log_path: str | Path, spec: SectionSpec) -> dict[str, str | None]:
    """Extract one rating section and resolve logical factor keys."""
    from logs.ruleset import extract_rulesets

    extract = extract_rulesets(str(log_path), ruleset_name=spec.ruleset_name)
    if not extract.rulesets:
        return {}

    picked = pick_field_values(extract.rulesets[0], all_alias_names(spec))
    raw = {item.name: item.value for item in picked if item.found}

    resolved: dict[str, str | None] = {}
    for key, aliases in spec.field_aliases.items():
        resolved[key] = _lookup_aliases(raw, aliases)
    return resolved


def collect_all_section_values(log_path: str | Path) -> dict[str, dict[str, str | None]]:
    return {spec.ruleset_name: collect_section_values(log_path, spec) for spec in SECTION_SPECS}


def detect_section_columns(workbook: WorkbookType) -> dict[str, str]:
    """Map section name → column letter under Building / BPP / Liability headers.

    Looks immediately to the right of each ``Property Section`` label. When a
    dual-panel template has two Property Section blocks, the rightmost wins.
    """
    summary = workbook[workbook.sheetnames[0]]
    panels: list[dict[str, str]] = []

    for row in summary.iter_rows(min_row=1, max_row=8, max_col=40):
        for cell in row:
            if cell.value is None:
                continue
            if str(cell.value).strip().lower() != "property section":
                continue
            panel: dict[str, str] = {}
            for offset in range(1, 6):
                neighbor = summary.cell(cell.row, cell.column + offset)
                if neighbor.value is None:
                    continue
                text = str(neighbor.value).strip()
                for section, aliases in SECTION_HEADER_ALIASES.items():
                    if text in aliases and section not in panel:
                        panel[section] = get_column_letter(neighbor.column)
            if panel:
                panels.append(panel)

    found: dict[str, str] = panels[-1] if panels else {}
    for spec in SECTION_SPECS:
        found.setdefault(spec.ruleset_name, spec.column)
    return found


def detect_coverage_table(workbook: WorkbookType) -> dict[str, tuple[int, int]] | None:
    """Locate Coverage Code / Sum Insured / Base Rate / Final Rate / Premium headers.

    Returns mapping of field → (row, col) for the header cells, or None.
    Prefers the leftmost Coverage Code table when duplicates exist.
    """
    summary = workbook[workbook.sheetnames[0]]
    wanted = {
        "coverage": ("coverage code",),
        "sum_insured": ("sum insured",),
        "base_rate": ("base rate",),
        "final_rate": ("final rate",),
        "premium": ("premium",),
    }
    best: dict[str, tuple[int, int]] | None = None
    best_coverage_col: int | None = None

    for row in summary.iter_rows(min_row=1, max_row=10, max_col=40):
        labels: dict[str, tuple[int, int]] = {}
        for cell in row:
            if cell.value is None:
                continue
            text = str(cell.value).strip().lower()
            for key, aliases in wanted.items():
                if text in aliases and key not in labels:
                    labels[key] = (cell.row, cell.column)
        if "coverage" not in labels or "sum_insured" not in labels:
            continue
        coverage_col = labels["coverage"][1]
        if best is None or coverage_col < (best_coverage_col or 10**9):
            best = labels
            best_coverage_col = coverage_col
    return best


def fill_section_factors(
    workbook: WorkbookType,
    spec: SectionSpec,
    values: dict[str, str | None],
    *,
    column: str | None = None,
) -> None:
    summary = workbook[workbook.sheetnames[0]]
    col = column or spec.column
    for key, row in spec.cell_rows.items():
        if key not in values or values[key] is None:
            continue
        cell = f"{col}{row}"
        summary[cell] = _to_number(values[key])


def fill_coverage_table(
    workbook: WorkbookType,
    log_path: str | Path,
    *,
    coverages_path: str | Path | None = None,
) -> int:
    """Write coverage-wise rows under the Coverage Code table. Returns rows written."""
    table = detect_coverage_table(workbook)
    if table is None:
        return 0

    summary = workbook[workbook.sheetnames[0]]
    header_row = table["coverage"][0]
    start_row = header_row + 1
    rows = extract_coverage_rows(log_path, coverages_path=coverages_path)
    if not rows:
        return 0

    # Clear prior data rows until a blank gap or Total marker.
    max_clear = start_row + max(40, len(rows) + 5)
    coverage_col = table["coverage"][1]
    for r in range(start_row, max_clear):
        label = summary.cell(r, coverage_col).value
        if label is None:
            # stop once we hit a stretch of empty label cells beyond written area
            continue
        text = str(label).strip().lower()
        if text == "total":
            break
        for key in ("coverage", "sum_insured", "base_rate", "final_rate", "premium"):
            if key in table:
                summary.cell(r, table[key][1]).value = None

    premium_total = 0.0
    premium_seen = False
    for offset, cov in enumerate(rows):
        r = start_row + offset
        summary.cell(r, table["coverage"][1]).value = cov.label
        if "sum_insured" in table and cov.sum_insured is not None:
            summary.cell(r, table["sum_insured"][1]).value = _to_number(cov.sum_insured)
        if "base_rate" in table and cov.base_rate is not None:
            summary.cell(r, table["base_rate"][1]).value = _to_number(cov.base_rate)
        if "final_rate" in table and cov.final_rate is not None:
            summary.cell(r, table["final_rate"][1]).value = _to_number(cov.final_rate)
        if "premium" in table and cov.premium is not None:
            prem = _to_number(cov.premium)
            summary.cell(r, table["premium"][1]).value = prem
            if isinstance(prem, (int, float)):
                premium_total += float(prem)
                premium_seen = True

    total_row = start_row + len(rows)
    if "premium" in table and premium_seen:
        # Put Total under Final Rate column when present (Policywise layout).
        if "final_rate" in table:
            summary.cell(total_row, table["final_rate"][1]).value = "Total"
        else:
            summary.cell(total_row, table["coverage"][1]).value = "Total"
        value = int(premium_total) if premium_total.is_integer() else premium_total
        summary.cell(total_row, table["premium"][1]).value = value

    return len(rows)


def fill_policy_header(
    workbook: WorkbookType,
    *,
    policy_no: str | None,
    irpm: str | None = None,
) -> None:
    summary = workbook[workbook.sheetnames[0]]
    if policy_no:
        summary["A1"] = policy_no
        try:
            summary.title = policy_no[:31]
        except ValueError:
            pass
    if irpm is not None:
        irpm_text = f"With IRPM  {irpm}"
        written = False
        for row in summary.iter_rows(min_row=1, max_row=5, max_col=40):
            for cell in row:
                if cell.value is None:
                    continue
                if str(cell.value).strip().lower().startswith("with irpm"):
                    cell.value = irpm_text
                    written = True
                    break
            if written:
                break
        if not written:
            summary["T2"] = irpm_text
            summary["E2"] = irpm_text


def fill_limits(
    workbook: WorkbookType,
    log_path: str | Path,
) -> None:
    """Write Building / BPP / Liability limits into both Limits rows.

    Left block:  F3 / G3 / H3
    Right block: U3 / V3 / W3  (under ``With IRPM …`` / ``Limits``)
    """
    summary = workbook[workbook.sheetnames[0]]
    limits = collect_section_limits(log_path)

    building = _to_number(limits.get("building"))
    bpp = _to_number(limits.get("bpp"))
    liability = _to_number(limits.get("liability"))

    if building is not None:
        summary["F3"] = building
        summary["U3"] = building
    if bpp is not None:
        summary["G3"] = bpp
        summary["V3"] = bpp
    if liability is not None:
        summary["H3"] = liability
        summary["W3"] = liability

    # Keep Building cover rates from the Building ruleset when present,
    # but do not overwrite Excel formulas in the refined class-code template.
    _, building_out = _ruleset_io_maps(log_path, "Building")
    for cell_ref, key in (("F20", "BuildingCoverBaseRate"), ("F21", "BuildingCoverUserRate")):
        raw = building_out.get(key)
        if not raw:
            continue
        current = summary[cell_ref].value
        if isinstance(current, str) and current.startswith("="):
            continue
        summary[cell_ref] = _to_number(raw)


def fill_limits_from_building(
    workbook: WorkbookType,
    log_path: str | Path,
) -> None:
    """Backward-compatible alias for :func:`fill_limits`."""
    fill_limits(workbook, log_path)


def build_excel_from_log(
    log_path: str | Path,
    output_path: str | Path,
    *,
    ruleset: str | None = None,
    template: str | Path | None = None,
    coverages_path: str | Path | None = None,
) -> Path:
    """Build Policywise-style Excel with section factors and coverage-wise rates.

    ``ruleset`` is accepted for CLI compatibility; when omitted/Building default,
    all three rating sections are filled.
    """
    _ = ruleset  # multi-section export is the default Policywise layout
    sections = collect_all_section_values(log_path)

    from logs.ruleset import extract_rulesets

    building_extract = extract_rulesets(str(log_path), ruleset_name="Building")
    header = {
        "policy_no": building_extract.header.policy_no,
        "module_id": building_extract.header.module_id,
        "project_id": building_extract.header.project_id,
    }
    inputs = {
        item.name: item.value
        for item in (building_extract.rulesets[0].inputs if building_extract.rulesets else [])
    }
    policy_no = header.get("policy_no") or inputs.get("PolNo") or Path(log_path).stem.split("_")[0]
    irpm = (sections.get("Building") or {}).get("irpm")

    workbook = load_workbook(resolve_template_path(template))
    fill_policy_header(workbook, policy_no=str(policy_no) if policy_no else None, irpm=irpm)
    fill_limits(workbook, log_path)

    section_columns = detect_section_columns(workbook)
    for spec in SECTION_SPECS:
        fill_section_factors(
            workbook,
            spec,
            sections.get(spec.ruleset_name) or {},
            column=section_columns.get(spec.ruleset_name),
        )

    fill_coverage_table(workbook, log_path, coverages_path=coverages_path)

    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(dest)
    return dest


def build_excel_from_payload(
    payload: dict[str, Any],
    output_path: str | Path,
    *,
    full_payload: dict[str, Any] | None = None,
    template: str | Path | None = None,
    log_path: str | Path | None = None,
    coverages_path: str | Path | None = None,
) -> Path:
    """Write Excel from payloads; if log_path is given, fill all three sections."""
    if log_path:
        return build_excel_from_log(
            log_path,
            output_path,
            template=template,
            coverages_path=coverages_path,
        )

    # Building-only fallback for callers that only have Building extract data.
    fields = {
        str(k): (None if v is None else str(v))
        for k, v in ((payload.get("rulesets") or [{}])[0].get("fields") or {}).items()
    }
    source = full_payload or payload
    header = payload.get("header") or {}
    inputs = {
        str(item.get("name")): str(item.get("value") or "")
        for item in (source.get("rulesets") or [{}])[0].get("inputs") or []
    }
    policy_no = header.get("policy_no") or inputs.get("PolNo")

    building_spec = SECTION_SPECS[0]
    values: dict[str, str | None] = {}
    for key, aliases in building_spec.field_aliases.items():
        values[key] = _lookup_aliases(fields, aliases)

    workbook = load_workbook(resolve_template_path(template))
    fill_policy_header(
        workbook,
        policy_no=str(policy_no) if policy_no else None,
        irpm=values.get("irpm"),
    )
    section_columns = detect_section_columns(workbook)
    fill_section_factors(
        workbook,
        building_spec,
        values,
        column=section_columns.get(building_spec.ruleset_name),
    )

    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(dest)
    return dest


def create_blank_factor_workbook(output_path: str | Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "RatingFactors"
    ws["A1"] = "Section"
    ws["B1"] = "Factor"
    ws["C1"] = "Value"
    row = 2
    for name in RATING_SECTION_NAMES:
        ws.cell(row, 1, name)
        row += 1
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dest)
    return dest
