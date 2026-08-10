from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from logs.ruleset import extract_rulesets

BOP_COVERAGES_CANDIDATES = (
    Path(__file__).resolve().parent / "data" / "BOP_coverages.xlsx",
    Path(__file__).resolve().parents[2] / "templates" / "BOP_coverages.xlsx",
    Path.cwd() / "templates" / "BOP_coverages.xlsx",
)

# Canonical section rulesets that may omit a single BuildingCvgCode.
SECTION_COVERAGE_CODES: dict[str, str] = {
    "Building": "400101",
    "Business Personal Property": "400102",
    "Liability": "400127",
}


@dataclass(frozen=True)
class CoverageRow:
    code: str
    label: str
    sum_insured: str | None = None
    base_rate: str | None = None
    final_rate: str | None = None
    premium: str | None = None


def resolve_coverages_path(path: str | Path | None = None) -> Path | None:
    if path:
        candidate = Path(path)
        if not candidate.exists():
            raise FileNotFoundError(f"BOP coverages workbook not found: {candidate}")
        return candidate
    for candidate in BOP_COVERAGES_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def load_coverage_descriptions(path: str | Path | None = None) -> dict[str, str]:
    """Map coverage code (e.g. 400101) → description from BOP_coverages.xlsx."""
    workbook_path = resolve_coverages_path(path)
    if workbook_path is None:
        return {}
    wb = load_workbook(workbook_path, data_only=True)
    ws = wb.active
    mapping: dict[str, str] = {}
    for row in ws.iter_rows(min_row=1, values_only=True):
        if not row or row[0] is None:
            continue
        code = str(row[0]).strip()
        if not code.isdigit():
            continue
        desc = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        if desc:
            mapping[code] = desc
    return mapping


def _parse_list_values(raw: str | None) -> list[str]:
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return [part.strip() for part in text.split(",") if part.strip()]


def _single_coverage_code(*candidates: str | None) -> str | None:
    for raw in candidates:
        parts = _parse_list_values(raw)
        if len(parts) == 1 and parts[0].isdigit():
            return parts[0]
        if raw is not None:
            text = str(raw).strip()
            if text.isdigit():
                return text
    return None


def _first_scalar(raw: str | None) -> str | None:
    if raw is None:
        return None
    parts = _parse_list_values(raw)
    if not parts:
        text = str(raw).strip()
        return text or None
    return parts[0]


def _io_maps(ruleset) -> tuple[dict[str, str], dict[str, str]]:
    inputs = {item.name: item.value for item in ruleset.inputs}
    outputs = {item.name: item.value for item in ruleset.outputs}
    return inputs, outputs


def _merge_si_from_arrays(log_path: str | Path) -> dict[str, str]:
    """Zip parallel BuildingCvgCode / BuildingCoverIncrementalSI arrays when present."""
    extract = extract_rulesets(str(log_path))
    best: dict[str, str] = {}
    for ruleset in extract.rulesets:
        inputs, outputs = _io_maps(ruleset)
        for source in (outputs, inputs):
            codes = _parse_list_values(
                source.get("BuildingCvgCode")
                or source.get("BCvgCode")
                or source.get("CvgCode")
            )
            sis = _parse_list_values(
                source.get("BuildingCoverIncrementalSI")
                or source.get("CoverageIncrementalSI")
            )
            if len(codes) < 2 or len(codes) != len(sis):
                continue
            if not all(code.isdigit() for code in codes):
                continue
            if len(codes) >= len(best):
                best = dict(zip(codes, sis))
    return best


def extract_coverage_rows(
    log_path: str | Path,
    *,
    coverages_path: str | Path | None = None,
    include_zero: bool = False,
) -> list[CoverageRow]:
    """Extract coverage-wise Sum Insured / Base Rate / Final Rate / Premium from a log."""
    descriptions = load_coverage_descriptions(coverages_path)
    extract = extract_rulesets(str(log_path))
    by_code: dict[str, CoverageRow] = {}

    for ruleset in extract.rulesets:
        inputs, outputs = _io_maps(ruleset)
        code = _single_coverage_code(
            inputs.get("BuildingCvgCode"),
            outputs.get("BuildingCvgCode"),
            inputs.get("CvgCode"),
            outputs.get("CvgCode"),
            inputs.get("BCvgCode"),
            outputs.get("BCvgCode"),
        )
        if code is None:
            code = SECTION_COVERAGE_CODES.get(ruleset.name)
        if code is None:
            continue

        sum_insured = _first_scalar(
            outputs.get("BuildingCoverIncrementalSI")
            or outputs.get("CoverageIncrementalSI")
            or inputs.get("BUserSI")
        )
        base_rate = _first_scalar(outputs.get("BuildingCoverBaseRate"))
        final_rate = _first_scalar(outputs.get("BuildingCoverUserRate"))
        premium = _first_scalar(
            outputs.get("BuildingCoverIncrementalPrem")
            or outputs.get("CoverageIncrementalPremium")
        )

        # Skip rulesets that only mention the code with no rating payloads.
        if not any([sum_insured, base_rate, final_rate, premium]):
            continue

        label = descriptions.get(code) or ruleset.name or code
        existing = by_code.get(code)
        # Prefer later executions that carry rates/premium (rating rulesets).
        score = sum(1 for v in (base_rate, final_rate, premium) if v is not None)
        prev_score = 0
        if existing:
            prev_score = sum(
                1
                for v in (existing.base_rate, existing.final_rate, existing.premium)
                if v is not None
            )
        if existing is None or score >= prev_score:
            by_code[code] = CoverageRow(
                code=code,
                label=label,
                sum_insured=sum_insured or (existing.sum_insured if existing else None),
                base_rate=base_rate or (existing.base_rate if existing else None),
                final_rate=final_rate or (existing.final_rate if existing else None),
                premium=premium or (existing.premium if existing else None),
            )

    # Fill any missing SI from parallel coverage arrays.
    for code, si in _merge_si_from_arrays(log_path).items():
        if code in by_code:
            if by_code[code].sum_insured is None:
                row = by_code[code]
                by_code[code] = CoverageRow(
                    code=row.code,
                    label=row.label,
                    sum_insured=si,
                    base_rate=row.base_rate,
                    final_rate=row.final_rate,
                    premium=row.premium,
                )
        elif include_zero:
            by_code[code] = CoverageRow(
                code=code,
                label=descriptions.get(code, code),
                sum_insured=si,
            )

    rows = list(by_code.values())
    if not include_zero:
        filtered: list[CoverageRow] = []
        for row in rows:
            values = (row.sum_insured, row.base_rate, row.final_rate, row.premium)
            if any(v is not None and str(v).strip() not in ("", "0", "0.0", "0.00", "0.0000000") for v in values):
                filtered.append(row)
            elif row.code in SECTION_COVERAGE_CODES.values():
                filtered.append(row)
        rows = filtered

    # Stable order: section coverages first, then numeric code order.
    priority = {code: idx for idx, code in enumerate(SECTION_COVERAGE_CODES.values())}

    def sort_key(row: CoverageRow) -> tuple[int, str]:
        return (priority.get(row.code, 100), row.code)

    return sorted(rows, key=sort_key)
