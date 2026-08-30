"""Transparent, teacher-controlled formative grading proposals."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import IntEnum


class RubricLevel(IntEnum):
    ABSENT = 0
    TO_REVIEW = 1
    PARTIAL = 2
    GOOD = 3
    VERY_GOOD = 4

    # Compatibility alias for grading decisions created before the five-level
    # scale.  It is intentionally absent from iteration over RubricLevel.
    SATISFACTORY = GOOD


@dataclass(frozen=True, slots=True)
class RubricCriterion:
    criterion_id: str
    label: str
    description: str
    weight: Decimal

    def __post_init__(self) -> None:
        for name in ("criterion_id", "label", "description"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} doit être une chaîne non vide.")
        if type(self.weight) is not Decimal or self.weight <= 0:
            raise ValueError("Le poids doit être un Decimal strictement positif.")


@dataclass(frozen=True, slots=True)
class FormativeGradingProfile:
    profile_id: str
    project_id: str
    title: str
    base_score: Decimal
    maximum_bonus: Decimal
    maximum_deduction: Decimal
    criteria: tuple[RubricCriterion, ...]

    def __post_init__(self) -> None:
        for name in ("profile_id", "project_id", "title"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} doit être une chaîne non vide.")
        for name in ("base_score", "maximum_bonus", "maximum_deduction"):
            if type(getattr(self, name)) is not Decimal:
                raise TypeError(f"{name} doit être un Decimal.")
        if not Decimal("0") <= self.base_score <= Decimal("20"):
            raise ValueError("La note de base doit être comprise entre 0 et 20.")
        if self.maximum_bonus < 0 or self.maximum_deduction < 0:
            raise ValueError("Bonus et retrait doivent être positifs.")
        criteria = tuple(self.criteria)
        if not criteria or any(type(item) is not RubricCriterion for item in criteria):
            raise ValueError("Le profil exige des critères valides.")
        ids = tuple(item.criterion_id for item in criteria)
        if len(ids) != len(set(ids)):
            raise ValueError("Les critères du barème doivent être uniques.")
        if sum((item.weight for item in criteria), Decimal("0")) != Decimal("1"):
            raise ValueError("La somme des poids doit être égale à 1.")
        object.__setattr__(self, "criteria", criteria)


@dataclass(frozen=True, slots=True)
class RubricDecision:
    criterion_id: str
    level: RubricLevel

    def __post_init__(self) -> None:
        if not isinstance(self.criterion_id, str) or not self.criterion_id.strip():
            raise ValueError("criterion_id doit être non vide.")
        if type(self.level) is not RubricLevel:
            raise TypeError("Le niveau doit être un RubricLevel.")


@dataclass(frozen=True, slots=True)
class RubricSuggestion:
    decision: RubricDecision
    rationale: str
    requires_human_review: bool = True

    def __post_init__(self) -> None:
        if type(self.decision) is not RubricDecision:
            raise TypeError("La suggestion doit contenir une décision de barème.")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("La justification de la suggestion est requise.")
        if type(self.requires_human_review) is not bool:
            raise TypeError("requires_human_review doit être booléen.")


@dataclass(frozen=True, slots=True)
class FormativeGradeProposal:
    profile: FormativeGradingProfile
    decisions: tuple[RubricDecision, ...]
    base_score: Decimal
    bonus: Decimal
    deduction: Decimal
    proposed_score: Decimal


def build_formative_grade_proposal(
    profile: FormativeGradingProfile,
    decisions: tuple[RubricDecision, ...],
) -> FormativeGradeProposal:
    """Compute an auditable proposal from explicit teacher decisions only."""

    if type(profile) is not FormativeGradingProfile:
        raise TypeError("Le profil de notation est invalide.")
    values = tuple(decisions)
    if any(type(item) is not RubricDecision for item in values):
        raise TypeError("Les décisions de notation sont invalides.")
    expected = tuple(item.criterion_id for item in profile.criteria)
    actual = tuple(item.criterion_id for item in values)
    if actual != expected:
        raise ValueError("Une décision ordonnée est requise pour chaque critère.")

    weights = {item.criterion_id: item.weight for item in profile.criteria}
    bonus = sum(
        (profile.maximum_bonus * weights[item.criterion_id]
         for item in values if item.level is RubricLevel.VERY_GOOD),
        Decimal("0"),
    )
    deduction = sum(
        (
            profile.maximum_deduction
            * weights[item.criterion_id]
            * (
                Decimal("1")
                if item.level is RubricLevel.ABSENT
                else Decimal("2") / Decimal("3")
                if item.level is RubricLevel.TO_REVIEW
                else Decimal("1") / Decimal("3")
            )
            for item in values
            if item.level in (
                RubricLevel.ABSENT, RubricLevel.TO_REVIEW, RubricLevel.PARTIAL,
            )
        ),
        Decimal("0"),
    )
    score = min(Decimal("20"), max(Decimal("0"), profile.base_score + bonus - deduction))
    quantum = Decimal("0.1")
    return FormativeGradeProposal(
        profile,
        values,
        profile.base_score,
        bonus.quantize(quantum, rounding=ROUND_HALF_UP),
        deduction.quantize(quantum, rounding=ROUND_HALF_UP),
        score.quantize(quantum, rounding=ROUND_HALF_UP),
    )
