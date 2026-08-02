"""Structured diagnostics for objective quantity comparisons."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from tpstudio.evaluation.quantity_comparisons import (
    QuantityComparisonEvaluation,
    QuantityComparisonEvaluationSet,
    QuantityComparisonEvaluationStatus,
    QuantityComparisonNotEvaluableReason,
)
from tpstudio.expectations.quantity_comparisons import (
    ComparisonPedagogicalContext,
)


class QuantityComparisonDiagnosticSource(str, Enum):
    """Objective source family for one comparison diagnostic."""

    CLASSIFICATION = "classification"
    EVALUABILITY = "evaluability"


class QuantityComparisonDiagnosticCode(str, Enum):
    """Stable code for one comparison diagnostic."""

    COMPARISON_MODERATELY_INCOHERENT = "comparison_moderately_incoherent"
    COMPARISON_STRONGLY_INCOHERENT = "comparison_strongly_incoherent"
    COMPARISON_NOT_EVALUABLE = "comparison_not_evaluable"

    @property
    def source(self) -> QuantityComparisonDiagnosticSource:
        return _definition_for(self).source

    @property
    def status(self) -> QuantityComparisonEvaluationStatus:
        return _definition_for(self).status

    @property
    def message_key(self) -> str:
        return _definition_for(self).message_key


@dataclass(frozen=True, slots=True)
class _DiagnosticDefinition:
    code: QuantityComparisonDiagnosticCode
    source: QuantityComparisonDiagnosticSource
    status: QuantityComparisonEvaluationStatus
    message_key: str


_DIAGNOSTIC_DEFINITIONS = (
    _DiagnosticDefinition(
        QuantityComparisonDiagnosticCode.COMPARISON_MODERATELY_INCOHERENT,
        QuantityComparisonDiagnosticSource.CLASSIFICATION,
        QuantityComparisonEvaluationStatus.MODERATELY_INCOHERENT,
        "comparison.moderately_incoherent",
    ),
    _DiagnosticDefinition(
        QuantityComparisonDiagnosticCode.COMPARISON_STRONGLY_INCOHERENT,
        QuantityComparisonDiagnosticSource.CLASSIFICATION,
        QuantityComparisonEvaluationStatus.STRONGLY_INCOHERENT,
        "comparison.strongly_incoherent",
    ),
    _DiagnosticDefinition(
        QuantityComparisonDiagnosticCode.COMPARISON_NOT_EVALUABLE,
        QuantityComparisonDiagnosticSource.EVALUABILITY,
        QuantityComparisonEvaluationStatus.NOT_EVALUABLE,
        "comparison.not_evaluable",
    ),
)


def _definition_for(code: QuantityComparisonDiagnosticCode) -> _DiagnosticDefinition:
    return next(item for item in _DIAGNOSTIC_DEFINITIONS if item.code is code)


def _code_for(
    status: QuantityComparisonEvaluationStatus,
) -> QuantityComparisonDiagnosticCode | None:
    definition = next(
        (item for item in _DIAGNOSTIC_DEFINITIONS if item.status is status), None
    )
    return definition.code if definition is not None else None


@dataclass(frozen=True, slots=True)
class QuantityComparisonDiagnostic:
    """One objective diagnostic retaining its A70b evaluation."""

    evaluation: QuantityComparisonEvaluation
    code: QuantityComparisonDiagnosticCode

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation, QuantityComparisonEvaluation):
            raise TypeError("L'évaluation doit être une QuantityComparisonEvaluation.")
        if not isinstance(self.code, QuantityComparisonDiagnosticCode):
            raise TypeError("Le code doit être un QuantityComparisonDiagnosticCode.")
        expected = _code_for(self.evaluation.status)
        if expected is None:
            raise ValueError("Une comparaison cohérente ne produit aucun diagnostic.")
        if self.code is not expected:
            raise ValueError("Le code ne correspond pas au statut de l'évaluation.")

    @property
    def production_id(self) -> str:
        return self.evaluation.production_id

    @property
    def source(self) -> QuantityComparisonDiagnosticSource:
        return self.code.source

    @property
    def message_key(self) -> str:
        return self.code.message_key

    @property
    def status(self) -> QuantityComparisonEvaluationStatus:
        return self.evaluation.status

    @property
    def normalized_error(self) -> Decimal | None:
        return self.evaluation.normalized_error

    @property
    def pedagogical_context(self) -> ComparisonPedagogicalContext:
        return self.evaluation.pedagogical_context

    @property
    def context_note(self) -> str:
        return self.evaluation.context_note

    @property
    def not_evaluable_reasons(
        self,
    ) -> tuple[QuantityComparisonNotEvaluableReason, ...]:
        return self.evaluation.not_evaluable_reasons


def _derive_diagnostics(
    evaluation_set: QuantityComparisonEvaluationSet,
) -> tuple[QuantityComparisonDiagnostic, ...]:
    if not isinstance(evaluation_set, QuantityComparisonEvaluationSet):
        raise TypeError("Les évaluations doivent former un QuantityComparisonEvaluationSet.")
    return tuple(
        QuantityComparisonDiagnostic(evaluation, code)
        for evaluation in evaluation_set
        if (code := _code_for(evaluation.status)) is not None
    )


@dataclass(frozen=True, slots=True)
class QuantityComparisonDiagnosticSet:
    """Ordered diagnostics retaining their complete A70b evaluation set."""

    evaluation_set: QuantityComparisonEvaluationSet
    diagnostics: tuple[QuantityComparisonDiagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation_set, QuantityComparisonEvaluationSet):
            raise TypeError("Les évaluations doivent former un QuantityComparisonEvaluationSet.")
        diagnostics = tuple(self.diagnostics)
        if any(not isinstance(item, QuantityComparisonDiagnostic) for item in diagnostics):
            raise TypeError("Chaque élément doit être un QuantityComparisonDiagnostic.")
        object.__setattr__(self, "diagnostics", diagnostics)
        evaluations = tuple(self.evaluation_set)
        if any(
            not any(item.evaluation is evaluation for evaluation in evaluations)
            for item in diagnostics
        ):
            raise ValueError("Chaque diagnostic doit réutiliser une évaluation du set.")
        if len({item.production_id for item in diagnostics}) != len(diagnostics):
            raise ValueError("Une comparaison ne peut produire qu'un diagnostic.")
        expected = _derive_diagnostics(self.evaluation_set)
        if len(diagnostics) != len(expected) or any(
            actual.evaluation is not derived.evaluation or actual.code is not derived.code
            for actual, derived in zip(diagnostics, expected)
        ):
            raise ValueError("Les diagnostics ne correspondent pas aux évaluations.")

    def __iter__(self) -> Iterator[QuantityComparisonDiagnostic]:
        return iter(self.diagnostics)

    def __len__(self) -> int:
        return len(self.diagnostics)

    def get(self, production_id: str) -> QuantityComparisonDiagnostic | None:
        return next(
            (item for item in self.diagnostics if item.production_id == production_id),
            None,
        )

    def for_code(self, code: QuantityComparisonDiagnosticCode) -> tuple[QuantityComparisonDiagnostic, ...]:
        if not isinstance(code, QuantityComparisonDiagnosticCode):
            raise TypeError("Le code doit être un QuantityComparisonDiagnosticCode.")
        return tuple(item for item in self.diagnostics if item.code is code)

    def for_source(self, source: QuantityComparisonDiagnosticSource) -> tuple[QuantityComparisonDiagnostic, ...]:
        if not isinstance(source, QuantityComparisonDiagnosticSource):
            raise TypeError("La source doit être une QuantityComparisonDiagnosticSource.")
        return tuple(item for item in self.diagnostics if item.source is source)

    def for_status(self, status: QuantityComparisonEvaluationStatus) -> tuple[QuantityComparisonDiagnostic, ...]:
        if not isinstance(status, QuantityComparisonEvaluationStatus):
            raise TypeError("Le statut doit être un QuantityComparisonEvaluationStatus.")
        return tuple(item for item in self.diagnostics if item.status is status)

    @property
    def moderate_incoherences(self) -> tuple[QuantityComparisonDiagnostic, ...]:
        return self.for_code(QuantityComparisonDiagnosticCode.COMPARISON_MODERATELY_INCOHERENT)

    @property
    def strong_incoherences(self) -> tuple[QuantityComparisonDiagnostic, ...]:
        return self.for_code(QuantityComparisonDiagnosticCode.COMPARISON_STRONGLY_INCOHERENT)

    @property
    def not_evaluable(self) -> tuple[QuantityComparisonDiagnostic, ...]:
        return self.for_code(QuantityComparisonDiagnosticCode.COMPARISON_NOT_EVALUABLE)

    @property
    def has_diagnostics(self) -> bool:
        return bool(self.diagnostics)

    @property
    def has_incoherence(self) -> bool:
        return bool(self.moderate_incoherences or self.strong_incoherences)

    @property
    def has_strong_incoherence(self) -> bool:
        return bool(self.strong_incoherences)

    @property
    def has_not_evaluable(self) -> bool:
        return bool(self.not_evaluable)


class QuantityComparisonDiagnosticBuilder:
    """Build objective diagnostics without recalculating A70b results."""

    def build(
        self, evaluation_set: QuantityComparisonEvaluationSet
    ) -> QuantityComparisonDiagnosticSet:
        return QuantityComparisonDiagnosticSet(
            evaluation_set, _derive_diagnostics(evaluation_set)
        )


def build_quantity_comparison_diagnostics(
    evaluation_set: QuantityComparisonEvaluationSet,
) -> QuantityComparisonDiagnosticSet:
    """Delegate to the stateless comparison diagnostic builder."""

    return QuantityComparisonDiagnosticBuilder().build(evaluation_set)
