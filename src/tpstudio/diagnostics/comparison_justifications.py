"""Structured diagnostics derived from A70g justification evaluations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from tpstudio.evaluation.comparison_justifications import (
    ComparisonJustificationEvaluation, ComparisonJustificationEvaluationSet,
    ComparisonJustificationEvaluationStatus, ComparisonJustificationNotEvaluableReason,
)
from tpstudio.evaluation.comparison_interpretations import ComparisonInterpretationEvaluationStatus
from tpstudio.evaluation.student_normalized_errors import StudentNormalizedErrorEvaluationStatus
from tpstudio.expectations.comparison_justifications import ComparisonJustificationElementKind
from tpstudio.expectations.quantity_comparisons import ComparisonPedagogicalContext


class ComparisonJustificationDiagnosticSource(str, Enum):
    COMPLETENESS = "completeness"
    EVALUABILITY = "evaluability"


class ComparisonJustificationDiagnosticCode(str, Enum):
    JUSTIFICATION_PARTIAL = "justification_partial"
    JUSTIFICATION_MISSING = "justification_missing"
    JUSTIFICATION_NOT_EVALUABLE = "justification_not_evaluable"

    @property
    def source(self): return _definition_for(self).source
    @property
    def status(self): return _definition_for(self).status
    @property
    def message_key(self): return _definition_for(self).message_key


@dataclass(frozen=True, slots=True)
class _Definition:
    code: ComparisonJustificationDiagnosticCode
    source: ComparisonJustificationDiagnosticSource
    status: ComparisonJustificationEvaluationStatus
    message_key: str


_DEFINITIONS = (
    _Definition(ComparisonJustificationDiagnosticCode.JUSTIFICATION_PARTIAL, ComparisonJustificationDiagnosticSource.COMPLETENESS, ComparisonJustificationEvaluationStatus.PARTIAL, "comparison_justification.partial"),
    _Definition(ComparisonJustificationDiagnosticCode.JUSTIFICATION_MISSING, ComparisonJustificationDiagnosticSource.COMPLETENESS, ComparisonJustificationEvaluationStatus.MISSING, "comparison_justification.missing"),
    _Definition(ComparisonJustificationDiagnosticCode.JUSTIFICATION_NOT_EVALUABLE, ComparisonJustificationDiagnosticSource.EVALUABILITY, ComparisonJustificationEvaluationStatus.NOT_EVALUABLE, "comparison_justification.not_evaluable"),
)


def _definition_for(code): return next(item for item in _DEFINITIONS if item.code is code)
def _code_for(status):
    definition = next((item for item in _DEFINITIONS if item.status is status), None)
    return definition.code if definition else None


@dataclass(frozen=True, slots=True)
class ComparisonJustificationDiagnostic:
    evaluation: ComparisonJustificationEvaluation
    code: ComparisonJustificationDiagnosticCode

    def __post_init__(self):
        if type(self.evaluation) is not ComparisonJustificationEvaluation: raise TypeError("L'évaluation doit être exactement une évaluation A70g.")
        if type(self.code) is not ComparisonJustificationDiagnosticCode: raise TypeError("Le code est invalide.")
        expected = _code_for(self.evaluation.status)
        if expected is None: raise ValueError("Une justification complète ne produit aucun diagnostic.")
        if self.code is not expected: raise ValueError("Le code ne correspond pas au statut A70g.")

    @property
    def comparison_id(self): return self.evaluation.comparison_id
    @property
    def production_id(self): return self.comparison_id
    @property
    def source(self): return self.code.source
    @property
    def message_key(self): return self.code.message_key
    @property
    def status(self): return self.evaluation.status
    @property
    def interpretation_status(self): return self.evaluation.interpretation_status
    @property
    def student_normalized_error_status(self): return self.evaluation.student_normalized_error_status
    @property
    def observed_element_ids(self): return self.evaluation.observed_element_ids
    @property
    def observed_kinds(self): return self.evaluation.observed_kinds
    @property
    def missing_required_element_ids(self): return self.evaluation.missing_required_element_ids
    @property
    def satisfied_alternative_groups(self): return self.evaluation.satisfied_alternative_groups
    @property
    def missing_alternative_groups(self): return self.evaluation.missing_alternative_groups
    @property
    def not_evaluable_reasons(self): return self.evaluation.not_evaluable_reasons
    @property
    def pedagogical_context(self): return self.evaluation.interpretation_evaluation.pedagogical_context


def _derive(evaluation_set):
    if type(evaluation_set) is not ComparisonJustificationEvaluationSet: raise TypeError("Le jeu A70g est invalide.")
    return tuple(ComparisonJustificationDiagnostic(item, code) for item in evaluation_set if (code := _code_for(item.status)) is not None)


@dataclass(frozen=True, slots=True)
class ComparisonJustificationDiagnosticSet:
    evaluation_set: ComparisonJustificationEvaluationSet
    diagnostics: tuple[ComparisonJustificationDiagnostic, ...]

    def __post_init__(self):
        if type(self.evaluation_set) is not ComparisonJustificationEvaluationSet: raise TypeError("Le jeu A70g est invalide.")
        if isinstance(self.diagnostics, (str, bytes)): raise TypeError("Les diagnostics doivent former une collection.")
        diagnostics = tuple(self.diagnostics)
        if any(type(item) is not ComparisonJustificationDiagnostic for item in diagnostics): raise TypeError("Un diagnostic est invalide.")
        object.__setattr__(self, "diagnostics", diagnostics)
        if len(diagnostics) != len(set(diagnostics)): raise ValueError("Un diagnostic est dupliqué.")
        expected = _derive(self.evaluation_set)
        if len(diagnostics) != len(expected) or any(a.evaluation is not b.evaluation or a.code is not b.code for a, b in zip(diagnostics, expected)): raise ValueError("Les diagnostics ne correspondent pas au jeu A70g.")

    def __iter__(self) -> Iterator[ComparisonJustificationDiagnostic]: return iter(self.diagnostics)
    def __len__(self): return len(self.diagnostics)
    def get(self, comparison_id): return next((item for item in self.diagnostics if item.comparison_id == comparison_id), None)
    def for_code(self, code):
        if type(code) is not ComparisonJustificationDiagnosticCode: raise TypeError("Le code est invalide.")
        return tuple(item for item in self.diagnostics if item.code is code)
    def for_source(self, source):
        if type(source) is not ComparisonJustificationDiagnosticSource: raise TypeError("La source est invalide.")
        return tuple(item for item in self.diagnostics if item.source is source)
    def for_status(self, status):
        if type(status) is not ComparisonJustificationEvaluationStatus: raise TypeError("Le statut est invalide.")
        return tuple(item for item in self.diagnostics if item.status is status)
    def for_missing_required_element(self, element_id): return tuple(item for item in self.diagnostics if element_id in item.missing_required_element_ids)
    def for_missing_alternative_group(self, group_id): return tuple(item for item in self.diagnostics if group_id in item.missing_alternative_groups)
    @property
    def partial(self): return self.for_code(ComparisonJustificationDiagnosticCode.JUSTIFICATION_PARTIAL)
    @property
    def missing(self): return self.for_code(ComparisonJustificationDiagnosticCode.JUSTIFICATION_MISSING)
    @property
    def not_evaluable(self): return self.for_code(ComparisonJustificationDiagnosticCode.JUSTIFICATION_NOT_EVALUABLE)
    @property
    def has_diagnostics(self): return bool(self.diagnostics)
    @property
    def has_partial(self): return bool(self.partial)
    @property
    def has_missing(self): return bool(self.missing)
    @property
    def has_not_evaluable(self): return bool(self.not_evaluable)


class ComparisonJustificationDiagnosticBuilder:
    def build(self, evaluation_set): return ComparisonJustificationDiagnosticSet(evaluation_set, _derive(evaluation_set))


def build_comparison_justification_diagnostics(evaluation_set):
    """Delegate to the stateless A70h diagnostic builder."""
    return ComparisonJustificationDiagnosticBuilder().build(evaluation_set)
