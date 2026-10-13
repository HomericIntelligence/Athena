"""This module defines the repository review scorecard policy."""

from __future__ import annotations

import re

REPO_REVIEW_SECTION = re.compile(
    r"^(?P<number>[1-9][0-9]*)\. \*\*(?P<name>[^*:]+):", re.MULTILINE
)
REPO_REVIEW_WEIGHT = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z/ ]*?) (?P<weight>[1-9][0-9]?)%"
)
REQUIRED_SECTION_COUNT = 15


def evaluate_scorecard(criteria: str, skill: str) -> list[str]:
    """Require the review formula to name and weight each criterion unambiguously."""
    sections = [match.group("name") for match in REPO_REVIEW_SECTION.finditer(criteria)]
    expected_numbers = list(range(1, REQUIRED_SECTION_COUNT + 1))
    numbers = [
        int(match.group("number")) for match in REPO_REVIEW_SECTION.finditer(criteria)
    ]
    if numbers != expected_numbers or len(set(sections)) != len(sections):
        return [
            f"The criteria must define each of the {REQUIRED_SECTION_COUNT} uniquely "
            "numbered sections."
        ]
    weight_line = re.search(r"^Weights: (?P<weights>.+)$", skill, re.MULTILINE)
    if weight_line is None:
        return ["The scorecard weights are missing."]
    weights = [
        (match.group("name"), int(match.group("weight")))
        for match in REPO_REVIEW_WEIGHT.finditer(weight_line.group("weights"))
    ]
    errors: list[str] = []
    if len(weights) != REQUIRED_SECTION_COUNT or len(
        {name for name, _ in weights}
    ) != len(weights):
        errors.append(
            f"The scorecard must assign one weight to each of {REQUIRED_SECTION_COUNT} "
            "sections."
        )
    for name, _ in weights:
        if name not in sections:
            errors.append(f"The weight has no matching criteria section: '{name}'.")
    missing_sections = sorted(set(sections).difference(name for name, _ in weights))
    if missing_sections:
        errors.append(
            "The scorecard does not assign a weight to these criteria sections: "
            + ", ".join(f"'{name}'" for name in missing_sections)
            + "."
        )
    if sum(weight for _, weight in weights) != 100:
        errors.append("The scorecard weights must total 100 percent.")
    return errors
