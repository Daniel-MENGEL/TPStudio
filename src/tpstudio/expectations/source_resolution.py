"""Runtime resolution of sources used by derived expectations.

This module deliberately stops at the boundary between existing analysis
objects and the closed derived-expression evaluator.  It does not inspect
notebooks, fit models, or calculate a derived formula itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
import math
from typing import Any

from .derived_quantities import (
    DerivedOperand,
    DerivedQuantityEvaluation,
    ExpectedDerivedQuantity,
    ProductionValue,
    RegressionParameter,
    RegressionParameterKind,
    TeacherConstant,
    evaluate_derived_quantity,
)


class DerivedSourceResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    MISSING_PRODUCTION = "missing_production"
    MISSING_ANALYSIS = "missing_analysis"
    NON_NUMERIC = "non_numeric"
    NON_SCALAR = "non_scalar"
    MISSING_REGRESSION = "missing_regression"
    MISSING_PARAMETER = "missing_parameter"
    INVALID_CONSTANT = "invalid_constant"
    CONFLICTING_ANALYSES = "conflicting_analyses"
    UNSUPPORTED_REGRESSION_MODEL = "unsupported_regression_model"


@dataclass(frozen=True, slots=True)
class DerivedSourceResolutionContext:
    """Small adapter context, indexed by production id.

    Values may be already-normalized scalars or existing assessment objects
    exposing a selected scalar observation.  The resolver never mutates them.
    """

    quantity_values: Mapping[str, object]
    graph_analyses: Mapping[str, object] = field(default_factory=dict)
    regression_model_analyses: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.quantity_values, Mapping):
            raise TypeError("quantity_values doit être un mapping.")
        if not isinstance(self.graph_analyses, Mapping):
            raise TypeError("graph_analyses doit être un mapping.")
        if not isinstance(self.regression_model_analyses, Mapping):
            raise TypeError("regression_model_analyses doit être un mapping.")


@dataclass(frozen=True, slots=True)
class ResolvedDerivedSource:
    source: DerivedOperand
    status: DerivedSourceResolutionStatus
    value: Decimal | None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DerivedSourceResolution:
    status: DerivedSourceResolutionStatus
    sources: tuple[ResolvedDerivedSource, ...]
    resolved_values: Mapping[DerivedOperand, Decimal]
    diagnostics: tuple[str, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.status is DerivedSourceResolutionStatus.RESOLVED


@dataclass(frozen=True, slots=True)
class DerivedQuantityRuntimeEvaluation:
    resolution: DerivedSourceResolution
    evaluation: DerivedQuantityEvaluation | None


def _to_decimal(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    # numpy scalar values expose item(); normalize them without importing or
    # coupling this boundary to numpy itself.
    item = getattr(value, "item", None)
    if callable(item):
        try:
            unwrapped = item()
        except Exception:
            return None
        if unwrapped is not value:
            return _to_decimal(unwrapped)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        try:
            result = Decimal(str(value))
        except Exception:
            return None
        return result if result.is_finite() else None
    return None


def _scalar_candidate(value: object) -> object:
    """Unwrap known assessment-shaped scalar containers only."""
    selected = getattr(value, "selected_observation", None)
    if selected is not None:
        return selected
    assessment = getattr(value, "assessment", None)
    if assessment is not None:
        selected = getattr(assessment, "selected_observation", None)
        if selected is not None:
            return selected
    observed_value = getattr(value, "value", None)
    if observed_value is not None and value.__class__.__name__ in {
        "ObservedScalarValue", "QuantityObservation",
    }:
        return observed_value
    return value


def _production_value(source: ProductionValue, context: DerivedSourceResolutionContext) -> ResolvedDerivedSource:
    if source.production_id not in context.quantity_values:
        return ResolvedDerivedSource(
            source, DerivedSourceResolutionStatus.MISSING_PRODUCTION, None,
            (f"production QUANTITY absente: {source.production_id}",),
        )
    raw = _scalar_candidate(context.quantity_values[source.production_id])
    if isinstance(raw, (list, tuple)) or hasattr(raw, "shape") and getattr(raw, "ndim", 0) != 0:
        return ResolvedDerivedSource(
            source, DerivedSourceResolutionStatus.NON_SCALAR, None,
            (f"source non scalaire: {source.production_id}",),
        )
    value = _to_decimal(raw)
    if value is None:
        return ResolvedDerivedSource(
            source, DerivedSourceResolutionStatus.NON_NUMERIC, None,
            (f"source non numérique: {source.production_id}",),
        )
    return ResolvedDerivedSource(source, DerivedSourceResolutionStatus.RESOLVED, value)


def _analysis_parameter(
    analysis: object,
    parameter: RegressionParameterKind,
) -> tuple[DerivedSourceResolutionStatus, Decimal | None, str | None]:
    # SLOPE/INTERCEPT have affine semantics only.  RegressionModelAnalysis
    # exposes an explicit degree; do not reinterpret polynomial coefficients.
    if hasattr(analysis, "degree"):
        degree = getattr(analysis, "degree")
        if degree != 1:
            return (
                DerivedSourceResolutionStatus.UNSUPPORTED_REGRESSION_MODEL,
                None,
                f"modèle de degré {degree!r} non affine pour {parameter.value}",
            )
    technical_status = getattr(
        getattr(analysis, "technical_status", None),
        "value",
        getattr(analysis, "technical_status", None),
    )
    if technical_status is not None and technical_status not in {"evaluable", "EVALUABLE"}:
        return DerivedSourceResolutionStatus.MISSING_REGRESSION, None, "régression non évaluable"
    parameter_name = parameter.value
    direct = getattr(analysis, parameter_name, None)
    if direct is None:
        coefficients = getattr(analysis, "coefficients", None)
        index = 0 if parameter is RegressionParameterKind.SLOPE else 1
        if coefficients is None or len(coefficients) <= index:
            return DerivedSourceResolutionStatus.MISSING_PARAMETER, None, f"paramètre absent: {parameter_name}"
        direct = coefficients[index]
    value = _to_decimal(direct)
    if value is None:
        return DerivedSourceResolutionStatus.NON_NUMERIC, None, f"paramètre non numérique: {parameter_name}"
    return DerivedSourceResolutionStatus.RESOLVED, value, None


def _regression_value(source: RegressionParameter, context: DerivedSourceResolutionContext) -> ResolvedDerivedSource:
    model = context.regression_model_analyses.get(source.production_id)
    graph = context.graph_analyses.get(source.production_id)
    if model is None and graph is None:
        return ResolvedDerivedSource(
            source, DerivedSourceResolutionStatus.MISSING_ANALYSIS, None,
            (f"analyse de régression absente: {source.production_id}",),
        )

    model_status = model_value = model_reason = None
    graph_status = graph_value = graph_reason = None
    if model is not None:
        model_status, model_value, model_reason = _analysis_parameter(model, source.parameter)
    if graph is not None:
        graph_status, graph_value, graph_reason = _analysis_parameter(graph, source.parameter)

    usable = tuple(
        (label, value) for label, status, value in (
            ("RegressionModelAnalysis", model_status, model_value),
            ("GraphAnalysis", graph_status, graph_value),
        )
        if status is DerivedSourceResolutionStatus.RESOLVED and value is not None
    )
    if len(usable) == 2:
        first, second = usable[0][1], usable[1][1]
        tolerance = max(abs(first), abs(second), Decimal("1")) * Decimal("1e-12")
        if abs(first - second) > tolerance:
            return ResolvedDerivedSource(
                source, DerivedSourceResolutionStatus.CONFLICTING_ANALYSES, None,
                (f"valeurs concurrentes pour {source.parameter.value}: "
                 f"{usable[0][0]}={first}, {usable[1][0]}={second}",),
            )
        return ResolvedDerivedSource(source, DerivedSourceResolutionStatus.RESOLVED, first)
    if len(usable) == 1:
        return ResolvedDerivedSource(source, DerivedSourceResolutionStatus.RESOLVED, usable[0][1])

    # No usable value was available. Preserve the most informative status;
    # an invalid analysis does not block a valid fallback, handled above.
    status = model_status if model_status is not None else graph_status
    reason = model_reason if model_reason is not None else graph_reason
    if status is None:
        status = DerivedSourceResolutionStatus.MISSING_ANALYSIS
    if reason is None:
        reason = f"paramètre de régression absent: {source.parameter.value}"
    if status is DerivedSourceResolutionStatus.NON_NUMERIC:
        return ResolvedDerivedSource(
            source, DerivedSourceResolutionStatus.NON_NUMERIC, None,
            (reason,),
        )
    return ResolvedDerivedSource(source, status, None, (reason,))


def _resolve_one(source: DerivedOperand, context: DerivedSourceResolutionContext) -> ResolvedDerivedSource:
    if isinstance(source, TeacherConstant):
        value = _to_decimal(source.value)
        if value is None:
            return ResolvedDerivedSource(source, DerivedSourceResolutionStatus.INVALID_CONSTANT, None, ("constante professeur invalide",))
        return ResolvedDerivedSource(source, DerivedSourceResolutionStatus.RESOLVED, value)
    if isinstance(source, ProductionValue):
        return _production_value(source, context)
    if isinstance(source, RegressionParameter):
        return _regression_value(source, context)
    raise TypeError("Opérande dérivé inconnu.")


def resolve_derived_quantity_sources(
    expectation: ExpectedDerivedQuantity,
    context: DerivedSourceResolutionContext,
) -> DerivedSourceResolution:
    if not isinstance(expectation, ExpectedDerivedQuantity):
        raise TypeError("expectation doit être une ExpectedDerivedQuantity.")
    if not isinstance(context, DerivedSourceResolutionContext):
        raise TypeError("context doit être un DerivedSourceResolutionContext.")
    items = tuple(_resolve_one(source, context) for source in expectation.sources)
    failures = tuple(item for item in items if not item.status is DerivedSourceResolutionStatus.RESOLVED)
    if failures:
        status = failures[0].status
        return DerivedSourceResolution(
            status, items, {}, tuple(reason for item in failures for reason in item.reasons),
        )
    values = {item.source: item.value for item in items if item.value is not None}
    return DerivedSourceResolution(DerivedSourceResolutionStatus.RESOLVED, items, values)


def evaluate_derived_quantity_from_analysis(
    expectation: ExpectedDerivedQuantity,
    context: DerivedSourceResolutionContext,
) -> DerivedQuantityRuntimeEvaluation:
    resolution = resolve_derived_quantity_sources(expectation, context)
    if not resolution.resolved:
        return DerivedQuantityRuntimeEvaluation(resolution, None)
    return DerivedQuantityRuntimeEvaluation(
        resolution, evaluate_derived_quantity(expectation, resolution.resolved_values)
    )
