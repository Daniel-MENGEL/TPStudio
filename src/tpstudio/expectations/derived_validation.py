"""Contextual validation of derived-quantity sources against a production plan."""

from __future__ import annotations

from dataclasses import dataclass

from .derived_quantities import (
    ExpectedDerivedQuantity,
    ProductionValue,
    RegressionParameter,
    TeacherConstant,
)
from .scientific_productions import ScientificProductionKind, ScientificProductionPlan


@dataclass(frozen=True, slots=True)
class DerivedQuantityPlanValidation:
    """Result of validating one derived expectation in a teacher plan."""

    valid: bool
    diagnostics: tuple[str, ...] = ()


def validate_derived_quantity_expectation(
    expectation: ExpectedDerivedQuantity,
    production_plan: ScientificProductionPlan,
) -> DerivedQuantityPlanValidation:
    """Validate source descriptors using only the contextual production plan.

    This deliberately does not inspect runtime observations, bindings, or
    dependency order.  Those belong respectively to source resolution and
    future dependency validation.
    """

    if not isinstance(expectation, ExpectedDerivedQuantity):
        raise TypeError("expectation doit être une ExpectedDerivedQuantity.")
    if not isinstance(production_plan, ScientificProductionPlan):
        raise TypeError("production_plan doit être un ScientificProductionPlan.")

    diagnostics: list[str] = []
    target = production_plan.get(expectation.production_id)
    if target is None:
        diagnostics.append(
            f"expectation cible {expectation.production_id!r}: production inexistante."
        )
    elif target.kind is not ScientificProductionKind.QUANTITY:
        diagnostics.append(
            f"expectation cible {expectation.production_id!r}: kind réel "
            f"{target.kind.value!r}, attendu {ScientificProductionKind.QUANTITY.value!r}."
        )

    for source in expectation.sources:
        if isinstance(source, TeacherConstant):
            continue

        source_id = source.production_id
        production = production_plan.get(source_id)
        if production is None:
            diagnostics.append(
                f"source {source_id!r}: production inexistante pour "
                f"{type(source).__name__}."
            )
            continue

        if isinstance(source, ProductionValue):
            expected_kinds = (ScientificProductionKind.QUANTITY,)
        else:
            expected_kinds = (ScientificProductionKind.PLOT,)

        if production.kind not in expected_kinds:
            expected = ", ".join(kind.value for kind in expected_kinds)
            diagnostics.append(
                f"source {source_id!r}: kind réel {production.kind.value!r}, "
                f"attendu {expected!r} pour {type(source).__name__}."
            )

    return DerivedQuantityPlanValidation(not diagnostics, tuple(diagnostics))
