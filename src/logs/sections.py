from __future__ import annotations

from dataclasses import dataclass

# Canonical rating rows used on the Policywise / class-code summary sheet.
# Property sections (Building / BPP) use rows 5-15.
# Liability uses base/LCM/IRPM plus rows 17-19.
# Column letters are defaults for legacy dual-panel templates (U/V/W);
# excel_export detects F/G/H on the refined class-code template.


@dataclass(frozen=True)
class SectionSpec:
    ruleset_name: str
    column: str  # U / V / W
    # logical_key -> preferred source field names (first hit wins)
    field_aliases: dict[str, tuple[str, ...]]
    # logical_key -> Excel row number on this section's column
    cell_rows: dict[str, int]


SECTION_SPECS: tuple[SectionSpec, ...] = (
    SectionSpec(
        ruleset_name="Building",
        column="U",
        field_aliases={
            "base_lc": ("BaseLCfac", "BaseLCFactor"),
            "occ_rel": ("OccRelativityFactor",),
            "construction": ("BuiConstructionRelativitiesFactor",),
            "loi": ("BuildingRelativityFactor",),
            "ppc": ("PPCFac",),
            "bceg": ("BCEGFac",),
            "sprinkler": ("SprinkledFactor",),
            "deductible": ("FixedDedFactor", "FixDedFactor"),
            "lcm": ("LCMFactor",),
            "irpm": ("IRPMFactor",),
            "bi": ("400513BCvgFactor",),
        },
        cell_rows={
            "base_lc": 5,
            "occ_rel": 6,
            "construction": 7,
            "loi": 8,
            "ppc": 9,
            "bceg": 10,
            "sprinkler": 11,
            "deductible": 12,
            "lcm": 13,
            "irpm": 14,
            "bi": 15,
        },
    ),
    SectionSpec(
        ruleset_name="Business Personal Property",
        column="V",
        field_aliases={
            "base_lc": ("BaseLCFactor", "BaseLCfac"),
            "occ_rel": ("OccRelativityFactor",),
            "construction": (
                "BPPConstructionRelativitiesFactor",
                "BuiConstructionRelativitiesFactor",
            ),
            "loi": ("BusinessRelativityFactor", "BuildingRelativityFactor"),
            "ppc": ("PPCFac",),
            "bceg": ("BCEGFac",),
            "sprinkler": ("SprinkledFactor",),
            "deductible": ("FixDedFactor", "FixedDedFactor"),
            "lcm": ("LCMFactor",),
            "irpm": ("IRPMFactor",),
            "bi": ("400513BCvgFactor",),
        },
        cell_rows={
            "base_lc": 5,
            "occ_rel": 6,
            "construction": 7,
            "loi": 8,
            "ppc": 9,
            "bceg": 10,
            "sprinkler": 11,
            "deductible": 12,
            "lcm": 13,
            "irpm": 14,
            "bi": 15,
        },
    ),
    SectionSpec(
        ruleset_name="Liability",
        column="W",
        field_aliases={
            "base_lc": ("BaseLCFactor", "OccupantLiabBaseLCFac", "LessorLiabBaseLCFac"),
            "lcm": ("LCMFactor",),
            "irpm": ("IRPMFactor",),
            "liab_class": ("LiabilityClassGrpFactor",),
            "increased_limits": ("IncreasedLimitsFactor",),
            "prop_damage_ded": ("PropDamageDedFactor",),
        },
        cell_rows={
            "base_lc": 5,
            "lcm": 13,
            "irpm": 14,
            "liab_class": 17,
            "increased_limits": 18,
            "prop_damage_ded": 19,
        },
    ),
)

RATING_SECTION_NAMES: tuple[str, ...] = tuple(spec.ruleset_name for spec in SECTION_SPECS)


def all_alias_names(spec: SectionSpec) -> tuple[str, ...]:
    names: list[str] = []
    for aliases in spec.field_aliases.values():
        names.extend(aliases)
    return tuple(dict.fromkeys(names))
