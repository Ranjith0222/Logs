from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.workbook.workbook import Workbook as WorkbookType

from logs.ruleset import pick_field_values
from logs.sections import RATING_SECTION_NAMES, SECTION_SPECS, SectionSpec, all_alias_names

TEMPLATE_CANDIDATES = (
    Path(__file__).resolve().parent / "data" / "policy_rating_template.xlsx",
    Path(__file__).resolve().parents[2] / "templates" / "policy_rating_template.xlsx",
    Path.cwd() / "templates" / "policy_rating_template.xlsx",
)


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
        "Excel template not found. Expected templates/policy_rating_template.xlsx "
        "or logs/data/policy_rating_template.xlsx."
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
    building_in, building_out = _ruleset_io_maps(log_path, "Building")
    bpp_in, bpp_out = _ruleset_io_maps(log_path, "Business Personal Property")
    liab_in, liab_out = _ruleset_io_maps(log_path, "Liability")

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
    liability_limit = (
        liab_in.get("BUserSI")
        or liab_in.get("400127BUserSI")
        or liab_out.get("BuildingCoverIncrementalSI")
        or liab_out.get("CoverageIncrementalSI")
    )
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


def fill_section_factors(
    workbook: WorkbookType,
    spec: SectionSpec,
    values: dict[str, str | None],
) -> None:
    summary = workbook[workbook.sheetnames[0]]
    for key, row in spec.cell_rows.items():
        if key not in values or values[key] is None:
            continue
        cell = f"{spec.column}{row}"
        summary[cell] = _to_number(values[key])


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
        summary["T2"] = f"With IRPM  {irpm}"


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

    # Keep Building cover rates from the Building ruleset when present.
    _, building_out = _ruleset_io_maps(log_path, "Building")
    if building_out.get("BuildingCoverBaseRate"):
        summary["F20"] = _to_number(building_out.get("BuildingCoverBaseRate"))
    if building_out.get("BuildingCoverUserRate"):
        summary["F21"] = _to_number(building_out.get("BuildingCoverUserRate"))


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
) -> Path:
    """Build Policywise-style Excel with Building (U), BPP (V), Liability (W) factors.

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

    for spec in SECTION_SPECS:
        fill_section_factors(workbook, spec, sections.get(spec.ruleset_name) or {})

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
) -> Path:
    """Write Excel from payloads; if log_path is given, fill all three sections."""
    if log_path:
        return build_excel_from_log(log_path, output_path, template=template)

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
    fill_section_factors(workbook, building_spec, values)

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
