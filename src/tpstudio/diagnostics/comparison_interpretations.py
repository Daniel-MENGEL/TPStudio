"""Structured diagnostics derived from A70e interpretation evaluations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from tpstudio.evaluation.comparison_interpretations import (
    ComparisonInterpretationEvaluation,
    ComparisonInterpretationEvaluationSet,
    ComparisonInterpretationEvaluationStatus,
    ComparisonInterpretationNotEvaluableReason,
)
from tpstudio.evaluation.quantity_comparisons import QuantityComparisonEvaluationStatus
from tpstudio.evaluation.student_normalized_errors import StudentNormalizedErrorEvaluationStatus
from tpstudio.expectations.comparison_interpretations import ComparisonInterpretationKind
from tpstudio.expectations.quantity_comparisons import ComparisonPedagogicalContext


class ComparisonInterpretationDiagnosticSource(str, Enum):
    CLASSIFICATION = "classification"
    EVALUABILITY = "evaluability"


class ComparisonInterpretationDiagnosticCode(str, Enum):
    INTERPRETATION_PARTIALLY_MATCHES = "interpretation_partially_matches"
    INTERPRETATION_CONTRADICTS = "interpretation_contradicts"
    INTERPRETATION_NOT_EVALUABLE = "interpretation_not_evaluable"

    @property
    def source(self) -> ComparisonInterpretationDiagnosticSource:
        return _definition_for(self).source

    @property
    def status(self) -> ComparisonInterpretationEvaluationStatus:
        return _definition_for(self).status

    @property
    def message_key(self) -> str:
        return _definition_for(self).message_key


@dataclass(frozen=True, slots=True)
class _DiagnosticDefinition:
    code: ComparisonInterpretationDiagnosticCode
    source: ComparisonInterpretationDiagnosticSource
    status: ComparisonInterpretationEvaluationStatus
    message_key: str


_DIAGNOSTIC_DEFINITIONS = (
    _DiagnosticDefinition(
        ComparisonInterpretationDiagnosticCode.INTERPRETATION_PARTIALLY_MATCHES,
        ComparisonInterpretationDiagnosticSource.CLASSIFICATION,
        ComparisonInterpretationEvaluationStatus.PARTIALLY_MATCHES_OBJECTIVE_CLASSIFICATION,
        "comparison_interpretation.partially_matches",
    ),
    _DiagnosticDefinition(
        ComparisonInterpretationDiagnosticCode.INTERPRETATION_CONTRADICTS,
        ComparisonInterpretationDiagnosticSource.CLASSIFICATION,
        ComparisonInterpretationEvaluationStatus.CONTRADICTS_OBJECTIVE_CLASSIFICATION,
        "comparison_interpretation.contradicts",
    ),
    _DiagnosticDefinition(
        ComparisonInterpretationDiagnosticCode.INTERPRETATION_NOT_EVALUABLE,
        ComparisonInterpretationDiagnosticSource.EVALUABILITY,
        ComparisonInterpretationEvaluationStatus.NOT_EVALUABLE,
        "comparison_interpretation.not_evaluable",
    ),
)


def _definition_for(code: ComparisonInterpretationDiagnosticCode) -> _DiagnosticDefinition:
    return next(item for item in _DIAGNOSTIC_DEFINITIONS if item.code is code)


def _code_for(status: ComparisonInterpretationEvaluationStatus) -> ComparisonInterpretationDiagnosticCode | None:
    definition = next((item for item in _DIAGNOSTIC_DEFINITIONS if item.status is status), None)
    return definition.code if definition else None


@dataclass(frozen=True, slots=True)
class ComparisonInterpretationDiagnostic:
    evaluation: ComparisonInterpretationEvaluation
    code: ComparisonInterpretationDiagnosticCode

    def __post_init__(self) -> None:
        if type(self.evaluation) is not ComparisonInterpretationEvaluation:
            raise TypeError("L'évaluation doit être exactement une évaluation A70e.")
        if type(self.code) is not ComparisonInterpretationDiagnosticCode:
            raise TypeError("Le code doit être exactement un code de diagnostic A70f.")
        expected = _code_for(self.evaluation.status)
        if expected is None:
            raise ValueError("Une interprétation conforme ne produit aucun diagnostic.")
        if self.code is not expected:
            raise ValueError("Le code ne correspond pas au statut A70e.")

    @property
    def comparison_id(self) -> str:
        return self.evaluation.comparison_id

    @property
    def production_id(self) -> str:
        return self.comparison_id

    @property
    def source(self) -> ComparisonInterpretationDiagnosticSource:
        return self.code.source

    @property
    def message_key(self) -> str:
        return self.code.message_key

    @property
    def status(self) -> ComparisonInterpretationEvaluationStatus:
        return self.evaluation.status

    @property
    def objective_status(self) -> QuantityComparisonEvaluationStatus:
        return self.evaluation.objective_status

    @property
    def observed_kind(self) -> ComparisonInterpretationKind | None:
        return self.evaluation.observed_kind

    @property
    def pedagogical_context(self) -> ComparisonPedagogicalContext:
        return self.evaluation.pedagogical_context

    @property
    def student_normalized_error_status(self) -> StudentNormalizedErrorEvaluationStatus | None:
        return self.evaluation.student_normalized_error_status

    @property
    def not_evaluable_reasons(self) -> tuple[ComparisonInterpretationNotEvaluableReason, ...]:
        return self.evaluation.not_evaluable_reasons


def _derive_diagnostics(evaluation_set: ComparisonInterpretationEvaluationSet) -> tuple[ComparisonInterpretationDiagnostic, ...]:
    if type(evaluation_set) is not ComparisonInterpretationEvaluationSet:
        raise TypeError("Les évaluations doivent former exactement un jeu A70e.")
    return tuple(
        ComparisonInterpretationDiagnostic(evaluation, code)
        for evaluation in evaluation_set
        if (code := _code_for(evaluation.status)) is not None
    )


@dataclass(frozen=True, slots=True)
class ComparisonInterpretationDiagnosticSet:
    evaluation_set: ComparisonInterpretationEvaluationSet
    diagnostics: tuple[ComparisonInterpretationDiagnostic, ...]

    def __post_init__(self) -> None:
        if type(self.evaluation_set) is not ComparisonInterpretationEvaluationSet:
            raise TypeError("Les évaluations doivent former exactement un jeu A70e.")
        if isinstance(self.diagnostics, (str, bytes)):
            raise TypeError("Les diagnostics doivent former une collection ordonnée.")
        diagnostics = tuple(self.diagnostics)
        if any(type(item) is not ComparisonInterpretationDiagnostic for item in diagnostics):
            raise TypeError("Chaque élément doit être exactement un diagnostic A70f.")
        object.__setattr__(self, "diagnostics", diagnostics)
        if len(diagnostics) != len(set(diagnostics)):
            raise ValueError("Un diagnostic ne peut pas être dupliqué.")
        expected = _derive_diagnostics(self.evaluation_set)
        if len(diagnostics) != len(expected) or any(
            actual.evaluation is not derived.evaluation or actual.code is not derived.code
            for actual, derived in zip(diagnostics, expected)
        ):
            raise ValueError("Les diagnostics ne correspondent pas exactement au jeu A70e.")

    def __iter__(self) -> Iterator[ComparisonInterpretationDiagnostic]:
        return iter(self.diagnostics)

    def __len__(self) -> int:
        return len(self.diagnostics)

    def get(self, comparison_id: str) -> ComparisonInterpretationDiagnostic | None:
        return next((item for item in self.diagnostics if item.comparison_id == comparison_id), None)

    def for_code(self, code: ComparisonInterpretationDiagnosticCode) -> tuple[ComparisonInterpretationDiagnostic, ...]:
        if type(code) is not ComparisonInterpretationDiagnosticCode:
            raise TypeError("Le code est invalide.")
        return tuple(item for item in self.diagnostics if item.code is code)

    def for_source(self, source: ComparisonInterpretationDiagnosticSource) -> tuple[ComparisonInterpretationDiagnostic, ...]:
        if type(source) is not ComparisonInterpretationDiagnosticSource:
            raise TypeError("La source est invalide.")
        return tuple(item for item in self.diagnostics if item.source is source)

    def for_status(self, status: ComparisonInterpretationEvaluationStatus) -> tuple[ComparisonInterpretationDiagnostic, ...]:
        if type(status) is not ComparisonInterpretationEvaluationStatus:
            raise TypeError("Le statut est invalide.")
        return tuple(item for item in self.diagnostics if item.status is status)

    @property
    def partial_matches(self):
        return self.for_code(ComparisonInterpretationDiagnosticCode.INTERPRETATION_PARTIALLY_MATCHES)

    @property
    def contradictions(self):
        return self.for_code(ComparisonInterpretationDiagnosticCode.INTERPRETATION_CONTRADICTS)

    @property
    def not_evaluable(self):
        return self.for_code(ComparisonInterpretationDiagnosticCode.INTERPRETATION_NOT_EVALUABLE)

    @property
    def has_diagnostics(self) -> bool:
        return bool(self.diagnostics)

    @property
    def has_partial_matches(self) -> bool:
        return bool(self.partial_matches)

    @property
    def has_contradictions(self) -> bool:
        return bool(self.contradictions)

    @property
    def has_not_evaluable(self) -> bool:
        return bool(self.not_evaluable)


class ComparisonInterpretationDiagnosticBuilder:
    def build(self, evaluation_set: ComparisonInterpretationEvaluationSet) -> ComparisonInterpretationDiagnosticSet:
        return ComparisonInterpretationDiagnosticSet(evaluation_set, _derive_diagnostics(evaluation_set))


def build_comparison_interpretation_diagnostics(evaluation_set: ComparisonInterpretationEvaluationSet) -> ComparisonInterpretationDiagnosticSet:
    """Delegate to the stateless A70f diagnostic builder."""

    return ComparisonInterpretationDiagnosticBuilder().build(evaluation_set)
