"""Generic distinction between declared and analyzable expectations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .models import ExpectedRelation
from .quantities import ExpectedQuantity, PresenceRequirement
from .quantity_series import ExpectedQuantitySeries
from .quantity_comparisons import ExpectedQuantityComparison
from .derived_quantities import ExpectedDerivedQuantity


class ExpectationSufficiency(str, Enum):
    """Scientific contract level available to the current analyzers."""

    STRUCTURAL_ONLY = "structural_only"
    ANALYZABLE = "analyzable"


@dataclass(frozen=True, slots=True)
class ExpectationSufficiencyAssessment:
    """Explainable, pure sufficiency assessment for one expectation."""

    sufficiency: ExpectationSufficiency
    reasons: tuple[str, ...]

    @property
    def is_analyzable(self) -> bool:
        return self.sufficiency is ExpectationSufficiency.ANALYZABLE


def assess_expectation_sufficiency(expectation: Any) -> ExpectationSufficiencyAssessment:
    """Assess only capabilities represented by the current expectation model.

    This is deliberately not a scientific correctness check.  It answers
    whether the current structural analyzers have at least one evaluable
    contract beyond a bare symbol/presence declaration.
    """

    if isinstance(expectation, ExpectedQuantity):
        if expectation.canonical_unit is not None:
            return ExpectationSufficiencyAssessment(
                ExpectationSufficiency.ANALYZABLE,
                ("canonical unit is available to the quantity evaluator",),
            )
        if expectation.unit_requirement is PresenceRequirement.IGNORE:
            return ExpectationSufficiencyAssessment(
                ExpectationSufficiency.ANALYZABLE,
                ("unit policy explicitly declares unit checking not applicable",),
            )
        if expectation.uncertainty_requirement is PresenceRequirement.REQUIRED:
            return ExpectationSufficiencyAssessment(
                ExpectationSufficiency.ANALYZABLE,
                ("required uncertainty is available to the quantity evaluator",),
            )
        return ExpectationSufficiencyAssessment(
            ExpectationSufficiency.STRUCTURAL_ONLY,
            ("quantity expectation only requires presence/symbol", "no evaluable unit or uncertainty rule"),
        )

    if isinstance(expectation, ExpectedQuantitySeries):
        if expectation.canonical_unit is not None or expectation.expected_length is not None:
            return ExpectationSufficiencyAssessment(
                ExpectationSufficiency.ANALYZABLE,
                ("série numérique avec unité ou cardinalité vérifiable",),
            )
        return ExpectationSufficiencyAssessment(
            ExpectationSufficiency.STRUCTURAL_ONLY,
            ("attente série sans contrainte vérifiable",),
        )

    if isinstance(expectation, ExpectedRelation):
        return ExpectationSufficiencyAssessment(
            ExpectationSufficiency.ANALYZABLE,
            ("canonical relation expression is available to relation matching",),
        )

    if isinstance(expectation, ExpectedQuantityComparison):
        return ExpectationSufficiencyAssessment(
            ExpectationSufficiency.ANALYZABLE,
            ("comparison operands, method and thresholds are declared",),
        )

    # GraphExpectation lives in projects.model; duck typing avoids an
    # expectations → projects import cycle while retaining a generic API.
    if all(hasattr(expectation, field) for field in (
        "production_id", "x_expression", "y_expression", "regression_required",
        "slope_quantity_id",
    )):
        fields = (
            expectation.x_expression,
            expectation.y_expression,
        )
        if all(isinstance(value, str) and value.strip() for value in fields):
            return ExpectationSufficiencyAssessment(
                ExpectationSufficiency.ANALYZABLE,
                ("graph axes, regression and derived quantities are declared",),
            )

    if isinstance(expectation, ExpectedDerivedQuantity):
        return ExpectationSufficiencyAssessment(
            ExpectationSufficiency.ANALYZABLE,
            ("derived quantity target, sources and supported calculation rule are declared",),
        )

    return ExpectationSufficiencyAssessment(
        ExpectationSufficiency.STRUCTURAL_ONLY,
        ("expectation type has no currently analyzable scientific contract",),
    )
