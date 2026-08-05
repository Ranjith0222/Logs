from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HEADER_PATTERNS = {
    "module_id": re.compile(r"Module Id\s*::\s*(.+)$", re.M),
    "project_id": re.compile(r"Project Id\s*::\s*(.+)$", re.M),
    "param_values": re.compile(r"Param Values\s*::\s*(.+)$", re.M),
    "effective_date": re.compile(r"Effective Date\s*::\s*(.+)$", re.M),
    "policy_no": re.compile(r"Policy No \+ Endt No\s*::\s*(.+)$", re.M),
    "ruleset_count": re.compile(r"NUMBER OF RULE SETS\s*::\s*(\d+)", re.M),
}

RULESET_NAME_RE = re.compile(r"^RULESET NAME\s*::\s*(.+?)\s*$", re.M)
PRECONDITION_COUNT_RE = re.compile(r"PRE-CONDITION OCCURRENCE COUNT\s*::\s*(\d+)")
PRECONDITION_RE = re.compile(
    r"Pre-Condition (Satisfied|Failed) for\s*::\s*(.+?)(?:\n|$)",
    re.M,
)
INPUT_PATH_RE = re.compile(
    r"^\t\t([A-Za-z0-9_]+) = (.+),(STRING|NUMBER|BOOLEAN|DATE)\s*$",
    re.M,
)
INPUT_VALUE_RE = re.compile(r"^\t\t([A-Za-z0-9_]+) = (.*?)\s*$", re.M)
OUTPUT_RE = re.compile(r"^\t\t([A-Za-z0-9_]+) =  ?(.*?),\s*$", re.M)
DECISION_TABLE_RE = re.compile(
    r"^\t\tDecision Table Evaluation\s*::\s*([A-Za-z0-9_]+) = (.*?)\s*$",
    re.M,
)
EVALUATED_VALUE_RE = re.compile(r"^\t\t\t([A-Za-z0-9_]+) = (.*?)\s*$", re.M)
SECTION_MARKERS = (
    "RULESET - INPUT VARIABLE AND VALUES ARE",
    "RuleSet - Formulae/Decistion Table VALUES ARE",
    "RULESET - OUTPUT VARIABLE AND VALUES ARE",
)


@dataclass
class RulesetHeader:
    module_id: str | None = None
    project_id: str | None = None
    param_values: str | None = None
    effective_date: str | None = None
    policy_no: str | None = None
    ruleset_count: int | None = None


@dataclass
class RulesetVariable:
    name: str
    value: str
    path: str | None = None
    type: str | None = None


@dataclass
class RulesetEvaluation:
    name: str
    value: str
    kind: str  # "formula" | "decision_table"


@dataclass
class RulesetPrecondition:
    occurrence_count: int | None = None
    status: str | None = None  # satisfied | failed
    expression: str | None = None


@dataclass
class RulesetExecution:
    name: str
    precondition: RulesetPrecondition = field(default_factory=RulesetPrecondition)
    inputs: list[RulesetVariable] = field(default_factory=list)
    evaluations: list[RulesetEvaluation] = field(default_factory=list)
    outputs: list[RulesetVariable] = field(default_factory=list)


@dataclass
class RulesetLogExtract:
    header: RulesetHeader
    rulesets: list[RulesetExecution]

    def to_dict(self) -> dict[str, Any]:
        return {
            "header": asdict(self.header),
            "rulesets": [asdict(ruleset) for ruleset in self.rulesets],
        }


def is_ruleset_log(text: str) -> bool:
    return "RULESET NAME ::" in text or "DETAIL OF RULE SET EXECUTION" in text


def read_text_source(source: str) -> str:
    if source.startswith(("http://", "https://")):
        import requests

        response = requests.get(source, timeout=60)
        response.raise_for_status()
        return response.text

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Log source not found: {source}")
    return path.read_text(encoding="utf-8", errors="replace")


def parse_ruleset_header(text: str) -> RulesetHeader:
    values: dict[str, Any] = {}
    for key, pattern in HEADER_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            continue
        raw = match.group(1).strip()
        values[key] = int(raw) if key == "ruleset_count" else raw
    return RulesetHeader(**values)


def _section_slices(block: str) -> dict[str, str]:
    positions: list[tuple[int, str]] = []
    for marker in SECTION_MARKERS:
        idx = block.find(marker)
        if idx >= 0:
            positions.append((idx, marker))
    positions.sort()
    slices: dict[str, str] = {}
    for i, (start, marker) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(block)
        slices[marker] = block[start:end]
    return slices


def _unwrap_value(raw: str) -> str:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]") and len(value) >= 2:
        value = value[1:-1].strip()
    return value.rstrip(",")


def _parse_inputs(section: str) -> list[RulesetVariable]:
    """Parse paired path/type declaration + value assignment lines."""
    pending: dict[str, RulesetVariable] = {}
    order: list[str] = []

    for line in section.splitlines():
        path_match = INPUT_PATH_RE.match(line)
        if path_match:
            name, path, var_type = path_match.groups()
            pending[name] = RulesetVariable(
                name=name,
                value="",
                path=path.strip(),
                type=var_type,
            )
            if name not in order:
                order.append(name)
            continue

        value_match = INPUT_VALUE_RE.match(line)
        if not value_match:
            continue
        name, raw_value = value_match.groups()
        if name in pending:
            pending[name].value = _unwrap_value(raw_value)
            continue
        pending[name] = RulesetVariable(name=name, value=_unwrap_value(raw_value))
        order.append(name)

    return [pending[name] for name in order]


def _parse_evaluations(section: str) -> list[RulesetEvaluation]:
    evaluations: list[RulesetEvaluation] = []
    after_eval = False
    for line in section.splitlines():
        stripped = line.strip()
        if "after Evaluation are" in stripped:
            after_eval = True
            continue
        if "are Subsituted as" in stripped or "are Substituted as" in stripped:
            after_eval = False
            continue
        decision = DECISION_TABLE_RE.match(line)
        if decision:
            evaluations.append(
                RulesetEvaluation(
                    name=decision.group(1),
                    value=_unwrap_value(decision.group(2)),
                    kind="decision_table",
                )
            )
            continue
        if after_eval:
            evaluated = EVALUATED_VALUE_RE.match(line)
            if evaluated:
                evaluations.append(
                    RulesetEvaluation(
                        name=evaluated.group(1),
                        value=_unwrap_value(evaluated.group(2)),
                        kind="formula",
                    )
                )
    return evaluations


def _parse_outputs(section: str) -> list[RulesetVariable]:
    return [
        RulesetVariable(name=name, value=_unwrap_value(value))
        for name, value in OUTPUT_RE.findall(section)
    ]


def parse_ruleset_block(block: str) -> RulesetExecution:
    name_match = RULESET_NAME_RE.search(block)
    if not name_match:
        raise ValueError("ruleset block missing RULESET NAME")
    execution = RulesetExecution(name=name_match.group(1).strip())

    count_match = PRECONDITION_COUNT_RE.search(block)
    if count_match:
        execution.precondition.occurrence_count = int(count_match.group(1))

    precondition_match = PRECONDITION_RE.search(block)
    if precondition_match:
        execution.precondition.status = precondition_match.group(1).lower()
        execution.precondition.expression = precondition_match.group(2).strip()

    sections = _section_slices(block)
    input_section = sections.get("RULESET - INPUT VARIABLE AND VALUES ARE", "")
    formula_section = sections.get("RuleSet - Formulae/Decistion Table VALUES ARE", "")
    output_section = sections.get("RULESET - OUTPUT VARIABLE AND VALUES ARE", "")

    if input_section:
        execution.inputs = _parse_inputs(input_section)
    if formula_section:
        execution.evaluations = _parse_evaluations(formula_section)
    if output_section:
        execution.outputs = _parse_outputs(output_section)
    return execution


def iter_ruleset_blocks(text: str) -> list[str]:
    matches = list(RULESET_NAME_RE.finditer(text))
    blocks: list[str] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append(text[start:end])
    return blocks


def extract_rulesets(
    source: str,
    *,
    ruleset_name: str | None = None,
    satisfied_only: bool = False,
) -> RulesetLogExtract:
    """Parse a UW ruleset execution log and optionally filter by ruleset name."""
    text = read_text_source(source)
    if not is_ruleset_log(text):
        raise ValueError(f"Source does not look like a ruleset execution log: {source}")

    header = parse_ruleset_header(text)
    rulesets: list[RulesetExecution] = []
    needle = ruleset_name.casefold() if ruleset_name else None

    for block in iter_ruleset_blocks(text):
        execution = parse_ruleset_block(block)
        if needle is not None and execution.name.casefold() != needle:
            continue
        if satisfied_only and execution.precondition.status != "satisfied":
            continue
        rulesets.append(execution)

    return RulesetLogExtract(header=header, rulesets=rulesets)
