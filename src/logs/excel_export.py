from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.workbook.workbook import Workbook as WorkbookType

from logs.desktop.service import run_desktop_extract
from logs.ruleset import BUILDING_RATING_FACTORS

# Template cells on the policy summary sheet (Building column = U).
# Labels live in column T; Building values in U; BPP in V; Liability in W.
BUILDING_FACTOR_CELLS: dict[str, str] = {
    "BaseLCfac": "U5",  # Base Loss Costs
    "OccRelativityFactor": "U6",  # Prop Rate Group Number RF
    "BuiConstructionRelativitiesFactor": "U7",  # Construction Class RF
    "BuildingRelativityFactor": "U8",  # Limit of Insurance(LOI) RF
    "PPCFac": "U9",  # Fire PPC Factor RF
    "BCEGFac": "U10",  # BCEG Factor RF
    "SprinkledFactor": "U11",  # Sprinkler RF
    "FixedDedFactor": "U12",  # Deductible RF
    "LCMFactor": "U13",  # LCM factor (Tier Based)
    "IRPMFactor": "U14",  # IRPM Factor
    "400513BCvgFactor": "U15",  # BI / Extra Expense period factor
}

FACTOR_WRITE_ORDER: tuple[str, ...] = (
    "BaseLCfac",
    "OccRelativityFactor",
    "BuiConstructionRelativitiesFactor",
    "BuildingRelativityFactor",
    "PPCFac",
    "BCEGFac",
    "SprinkledFactor",
    "FixedDedFactor",
    "LCMFactor",
    "IRPMFactor",
    "400513BCvgFactor",
)

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
    try:
        value = float(text)
    except ValueError:
        return text
    if value.is_integer():
        return int(value)
    return value


def _fields_from_payload(payload: dict[str, Any]) -> dict[str, str | None]:
    ruleset = (payload.get("rulesets") or [{}])[0]
    fields = dict(ruleset.get("fields") or {})
    if not fields:
        for item in ruleset.get("field_details") or []:
            fields[str(item.get("name"))] = item.get("value")
    return fields


def _inputs_from_full_ruleset(payload: dict[str, Any]) -> dict[str, str]:
    ruleset = (payload.get("rulesets") or [{}])[0]
    return {
        str(item.get("name")): str(item.get("value") or "")
        for item in ruleset.get("inputs") or []
    }


def _outputs_from_full_ruleset(payload: dict[str, Any]) -> dict[str, str]:
    ruleset = (payload.get("rulesets") or [{}])[0]
    return {
        str(item.get("name")): str(item.get("value") or "")
        for item in ruleset.get("outputs") or []
    }


def fill_building_factors(
    workbook: WorkbookType,
    fields: dict[str, str | None],
    *,
    policy_no: str | None = None,
) -> None:
    """Write Building rating factors into the summary sheet Building column (U)."""
    summary = workbook[workbook.sheetnames[0]]
    if policy_no:
        summary["A1"] = policy_no
        # Rename first sheet to policy number when possible.
        try:
            summary.title = policy_no[:31]
        except ValueError:
            pass

    for name in FACTOR_WRITE_ORDER:
        cell = BUILDING_FACTOR_CELLS.get(name)
        if not cell or name not in fields:
            continue
        summary[cell] = _to_number(fields.get(name))

    irpm = fields.get("IRPMFactor")
    if irpm is not None:
        summary["T2"] = f"With IRPM  {irpm}"


def fill_limits_and_rates(
    workbook: WorkbookType,
    *,
    inputs: dict[str, str] | None = None,
    outputs: dict[str, str] | None = None,
) -> None:
    """Fill common Building/BPP limits and rates when available from the ruleset."""
    summary = workbook[workbook.sheetnames[0]]
    inputs = inputs or {}
    outputs = outputs or {}

    building_limit = inputs.get("BuildingLimit") or outputs.get("BuildingCoverIncrementalSI")
    bpp_limit = inputs.get("BusinessPersonalPropLimit")
    if building_limit:
        summary["F3"] = _to_number(building_limit)
    if bpp_limit:
        summary["G3"] = _to_number(bpp_limit)

    base_rate = outputs.get("BuildingCoverBaseRate") or outputs.get("BCBasePremium")
    user_rate = outputs.get("BuildingCoverUserRate")
    # Left-side premium helpers when present.
    if outputs.get("BuildingCoverBaseRate"):
        summary["F20"] = _to_number(outputs.get("BuildingCoverBaseRate"))
    if outputs.get("BuildingCoverUserRate"):
        summary["F21"] = _to_number(user_rate)
    elif outputs.get("BuildingCoverAnnPrem") and building_limit:
        # leave formulas intact on right side; optional left-side seed
        pass
    _ = base_rate


def build_excel_from_log(
    log_path: str | Path,
    output_path: str | Path,
    *,
    ruleset: str = "Building",
    template: str | Path | None = None,
) -> Path:
    """Extract Building factors from a UW log and write a Policywise-style Excel workbook."""
    factors_payload = run_desktop_extract(
        log_path,
        ruleset=ruleset,
        mode="building-factors",
    )
    full_payload = run_desktop_extract(
        log_path,
        ruleset=ruleset,
        mode="full",
    )
    fields = _fields_from_payload(factors_payload)
    inputs = _inputs_from_full_ruleset(full_payload)
    outputs = _outputs_from_full_ruleset(full_payload)

    header = factors_payload.get("header") or {}
    policy_no = (
        header.get("policy_no")
        or inputs.get("PolNo")
        or Path(log_path).stem.split("_")[0]
    )

    workbook = load_workbook(resolve_template_path(template))
    fill_building_factors(workbook, fields, policy_no=str(policy_no) if policy_no else None)
    fill_limits_and_rates(workbook, inputs=inputs, outputs=outputs)

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
) -> Path:
    """Write Excel from an already-extracted desktop payload."""
    fields = _fields_from_payload(payload)
    source = full_payload or payload
    inputs = _inputs_from_full_ruleset(source)
    outputs = _outputs_from_full_ruleset(source)
    header = payload.get("header") or {}
    policy_no = header.get("policy_no") or inputs.get("PolNo")

    workbook = load_workbook(resolve_template_path(template))
    fill_building_factors(workbook, fields, policy_no=str(policy_no) if policy_no else None)
    fill_limits_and_rates(workbook, inputs=inputs, outputs=outputs)

    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(dest)
    return dest


def create_blank_factor_workbook(output_path: str | Path) -> Path:
    """Fallback minimal workbook if template is unavailable."""
    wb = Workbook()
    ws = wb.active
    ws.title = "BuildingFactors"
    ws["A1"] = "Factor"
    ws["B1"] = "Value"
    for index, name in enumerate(BUILDING_RATING_FACTORS, start=2):
        ws.cell(index, 1, name)
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dest)
    return dest
