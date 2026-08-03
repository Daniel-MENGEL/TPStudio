"""Structural evaluation of declared comparison justification elements."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from tpstudio.expectations.comparison_justifications import (
    ComparisonJustificationElementKind, ComparisonJustificationExpectationSet,
    ComparisonJustificationRequirement, ExpectedComparisonJustification,
)
from tpstudio.notebooks.binding_resolution import NotebookBindingResolution
from tpstudio.reasoning.comparison_justifications import (
    ComparisonJustificationDetection, extract_comparison_justification,
)

from .comparison_interpretations import ComparisonInterpretationEvaluation, ComparisonInterpretationEvaluationSet, ComparisonInterpretationEvaluationStatus
from .student_normalized_errors import StudentNormalizedErrorEvaluation, StudentNormalizedErrorEvaluationSet, StudentNormalizedErrorEvaluationStatus


class ComparisonJustificationEvaluationStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    NOT_EVALUABLE = "not_evaluable"


class ComparisonJustificationNotEvaluableReason(str, Enum):
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_AMBIGUOUS = "source_ambiguous"


def _same_objects(left, right): return len(left) == len(right) and all(a is b for a, b in zip(left, right))


def _groups(expectation):
    return tuple(dict.fromkeys(item.alternative_group for item in expectation.elements if item.alternative_group is not None))


def _has_structural_obligations(expectation):
    return any(
        item.requirement is ComparisonJustificationRequirement.REQUIRED
        for item in expectation.elements
    ) or bool(_groups(expectation))


def _classification(expectation, detection):
    if not detection.has_observations: return ComparisonJustificationEvaluationStatus.MISSING
    required_ok = all(detection.is_element_observed(item.element_id) for item in expectation.elements if item.requirement is ComparisonJustificationRequirement.REQUIRED)
    groups_ok = all(any(detection.is_element_observed(item.element_id) for item in expectation.elements if item.alternative_group == group) for group in _groups(expectation))
    return ComparisonJustificationEvaluationStatus.COMPLETE if _has_structural_obligations(expectation) and required_ok and groups_ok else ComparisonJustificationEvaluationStatus.PARTIAL


def _analyze(expectation, candidates, detection):
    resolved = tuple(item for item in candidates if item.resolved and isinstance(item.text, str))
    source = resolved[0] if len(resolved) == 1 else None
    if not resolved: reasons = (ComparisonJustificationNotEvaluableReason.SOURCE_UNAVAILABLE,)
    elif len(resolved) > 1: reasons = (ComparisonJustificationNotEvaluableReason.SOURCE_AMBIGUOUS,)
    else: reasons = ()
    if source is None:
        if detection is not None: raise ValueError("Une source absente ou ambiguë ne possède aucune détection.")
        return None, ComparisonJustificationEvaluationStatus.NOT_EVALUABLE, reasons
    if detection is None or detection.expectation is not expectation: raise ValueError("Une source unique exige sa détection.")
    return source, _classification(expectation, detection), ()


@dataclass(frozen=True, slots=True)
class ComparisonJustificationEvaluation:
    expectation: ExpectedComparisonJustification
    interpretation_evaluation: ComparisonInterpretationEvaluation
    student_normalized_error_evaluation: StudentNormalizedErrorEvaluation | None
    source_candidates: tuple[NotebookBindingResolution, ...]
    source_resolution: NotebookBindingResolution | None
    detection: ComparisonJustificationDetection | None
    status: ComparisonJustificationEvaluationStatus
    not_evaluable_reasons: tuple[ComparisonJustificationNotEvaluableReason, ...] = ()

    def __post_init__(self): self._validate(canonical=False)

    @classmethod
    def _from_canonical_detection(cls, *values):
        instance = object.__new__(cls)
        for name, value in zip(("expectation", "interpretation_evaluation", "student_normalized_error_evaluation", "source_candidates", "source_resolution", "detection", "status", "not_evaluable_reasons"), values): object.__setattr__(instance, name, value)
        instance._validate(canonical=True)
        return instance

    def _validate(self, *, canonical):
        if type(self.expectation) is not ExpectedComparisonJustification: raise TypeError("L'attente est invalide.")
        if type(self.interpretation_evaluation) is not ComparisonInterpretationEvaluation: raise TypeError("La référence A70e est invalide.")
        if self.interpretation_evaluation.comparison_id != self.expectation.comparison_id: raise ValueError("La référence A70e est étrangère.")
        student = self.student_normalized_error_evaluation
        if student is not None:
            if type(student) is not StudentNormalizedErrorEvaluation: raise TypeError("La référence A70d est invalide.")
            if student.comparison_id != self.expectation.comparison_id: raise ValueError("La référence A70d est étrangère.")
            if student.reference_evaluation is not self.interpretation_evaluation.reference_evaluation: raise ValueError("A70d et A70e doivent partager A70b.")
        if isinstance(self.source_candidates, (str, bytes)): raise TypeError("Les sources doivent former une collection.")
        candidates = tuple(self.source_candidates)
        if any(type(item) is not NotebookBindingResolution for item in candidates): raise TypeError("Une source est invalide.")
        if any(item.production_id != self.expectation.comparison_id for item in candidates): raise ValueError("Une source est étrangère.")
        object.__setattr__(self, "source_candidates", candidates)
        if self.source_resolution is not None and type(self.source_resolution) is not NotebookBindingResolution: raise TypeError("La source retenue est invalide.")
        if self.detection is not None and type(self.detection) is not ComparisonJustificationDetection: raise TypeError("La détection est invalide.")
        if type(self.status) is not ComparisonJustificationEvaluationStatus: raise TypeError("Le statut est invalide.")
        if isinstance(self.not_evaluable_reasons, (str, bytes)): raise TypeError("Les raisons doivent former une collection.")
        reasons = tuple(self.not_evaluable_reasons)
        if any(type(item) is not ComparisonJustificationNotEvaluableReason for item in reasons): raise TypeError("Une raison est invalide.")
        if len(reasons) != len(set(reasons)): raise ValueError("Les raisons doivent être uniques.")
        object.__setattr__(self, "not_evaluable_reasons", reasons)
        source, status, expected_reasons = _analyze(self.expectation, candidates, self.detection)
        if source is not None and not canonical:
            if self.detection != extract_comparison_justification(source.text, self.expectation): raise ValueError("La détection ne correspond pas exactement au texte résolu.")
        if self.source_resolution is not source or self.status is not status or reasons != expected_reasons: raise ValueError("L'évaluation ne respecte pas la politique A70g.")

    @property
    def comparison_id(self): return self.expectation.comparison_id
    @property
    def interpretation_status(self): return self.interpretation_evaluation.status
    @property
    def student_normalized_error_status(self): return self.student_normalized_error_evaluation.status if self.student_normalized_error_evaluation else None
    @property
    def observed_element_ids(self): return self.detection.observed_element_ids if self.detection else ()
    @property
    def observed_kinds(self): return self.detection.observed_kinds if self.detection else ()
    @property
    def missing_required_element_ids(self):
        return tuple(item.element_id for item in self.expectation.elements if item.requirement is ComparisonJustificationRequirement.REQUIRED and item.element_id not in self.observed_element_ids)
    @property
    def satisfied_alternative_groups(self):
        return tuple(group for group in _groups(self.expectation) if any(item.element_id in self.observed_element_ids for item in self.expectation.elements if item.alternative_group == group))
    @property
    def missing_alternative_groups(self): return tuple(group for group in _groups(self.expectation) if group not in self.satisfied_alternative_groups)
    @property
    def complete(self): return self.status is ComparisonJustificationEvaluationStatus.COMPLETE
    @property
    def partial(self): return self.status is ComparisonJustificationEvaluationStatus.PARTIAL
    @property
    def missing(self): return self.status is ComparisonJustificationEvaluationStatus.MISSING
    @property
    def evaluable(self): return self.status is not ComparisonJustificationEvaluationStatus.NOT_EVALUABLE
    @property
    def not_evaluable(self): return not self.evaluable


@dataclass(frozen=True, slots=True)
class ComparisonJustificationEvaluationSet:
    expectation_set: ComparisonJustificationExpectationSet
    interpretation_evaluation_set: ComparisonInterpretationEvaluationSet
    student_normalized_error_evaluation_set: StudentNormalizedErrorEvaluationSet | None
    evaluations: tuple[ComparisonJustificationEvaluation, ...]

    def __post_init__(self):
        if type(self.expectation_set) is not ComparisonJustificationExpectationSet: raise TypeError("Le jeu d'attentes A70g est invalide.")
        if type(self.interpretation_evaluation_set) is not ComparisonInterpretationEvaluationSet: raise TypeError("Le jeu A70e est invalide.")
        if self.expectation_set.comparison_expectation_set is not self.interpretation_evaluation_set.comparison_evaluation_set.expectation_set: raise ValueError("A70g et A70e doivent partager A70a.")
        student_set = self.student_normalized_error_evaluation_set
        if student_set is not None:
            if type(student_set) is not StudentNormalizedErrorEvaluationSet: raise TypeError("Le jeu A70d est invalide.")
            if student_set.comparison_evaluation_set is not self.interpretation_evaluation_set.comparison_evaluation_set: raise ValueError("A70d et A70e doivent partager A70b.")
        if isinstance(self.evaluations, (str, bytes)): raise TypeError("Les évaluations doivent former une collection.")
        evaluations = tuple(self.evaluations)
        if any(type(item) is not ComparisonJustificationEvaluation for item in evaluations): raise TypeError("Une évaluation est invalide.")
        object.__setattr__(self, "evaluations", evaluations)
        expected = self.expectation_set.in_evaluation_order
        if len(evaluations) != len(expected): raise ValueError("Une évaluation est requise par attente.")
        resolutions = self.interpretation_evaluation_set.comparison_evaluation_set.quantity_assessment_set.resolution_set
        for evaluation, expectation in zip(evaluations, expected):
            if evaluation.expectation is not expectation: raise ValueError("L'ordre ou l'identité des attentes est invalide.")
            if evaluation.interpretation_evaluation is not self.interpretation_evaluation_set.get(expectation.comparison_id): raise ValueError("La référence A70e est étrangère.")
            if evaluation.student_normalized_error_evaluation is not (student_set.get(expectation.comparison_id) if student_set else None): raise ValueError("La référence A70d est étrangère.")
            if not _same_objects(evaluation.source_candidates, resolutions.for_production(expectation.comparison_id)): raise ValueError("Les sources sont étrangères.")

    def __iter__(self) -> Iterator[ComparisonJustificationEvaluation]: return iter(self.evaluations)
    def __len__(self): return len(self.evaluations)
    def get(self, comparison_id): return next((item for item in self.evaluations if item.comparison_id == comparison_id), None)
    def for_status(self, status):
        if type(status) is not ComparisonJustificationEvaluationStatus: raise TypeError("Le statut est invalide.")
        return tuple(item for item in self.evaluations if item.status is status)
    def for_reason(self, reason):
        if type(reason) is not ComparisonJustificationNotEvaluableReason: raise TypeError("La raison est invalide.")
        return tuple(item for item in self.evaluations if reason in item.not_evaluable_reasons)
    @property
    def complete(self): return self.for_status(ComparisonJustificationEvaluationStatus.COMPLETE)
    @property
    def partial(self): return self.for_status(ComparisonJustificationEvaluationStatus.PARTIAL)
    @property
    def missing(self): return self.for_status(ComparisonJustificationEvaluationStatus.MISSING)
    @property
    def not_evaluable(self): return self.for_status(ComparisonJustificationEvaluationStatus.NOT_EVALUABLE)
    @property
    def all_evaluable(self): return not self.not_evaluable
    @property
    def all_complete(self): return len(self.complete) == len(self.evaluations)
    @property
    def has_partial(self): return bool(self.partial)
    @property
    def has_missing(self): return bool(self.missing)
    @property
    def has_not_evaluable(self): return bool(self.not_evaluable)


class ComparisonJustificationEvaluator:
    def evaluate(self, interpretation_evaluation_set, expectation_set, student_normalized_error_evaluation_set=None):
        if type(interpretation_evaluation_set) is not ComparisonInterpretationEvaluationSet: raise TypeError("Le jeu A70e est invalide.")
        if type(expectation_set) is not ComparisonJustificationExpectationSet: raise TypeError("Le jeu A70g est invalide.")
        if expectation_set.comparison_expectation_set is not interpretation_evaluation_set.comparison_evaluation_set.expectation_set: raise ValueError("A70g et A70e doivent partager A70a.")
        if student_normalized_error_evaluation_set is not None:
            if type(student_normalized_error_evaluation_set) is not StudentNormalizedErrorEvaluationSet: raise TypeError("Le jeu A70d est invalide.")
            if student_normalized_error_evaluation_set.comparison_evaluation_set is not interpretation_evaluation_set.comparison_evaluation_set: raise ValueError("A70d et A70e doivent partager A70b.")
        resolutions = interpretation_evaluation_set.comparison_evaluation_set.quantity_assessment_set.resolution_set
        evaluations = []
        for expectation in expectation_set.in_evaluation_order:
            interpretation = interpretation_evaluation_set.get(expectation.comparison_id)
            if interpretation is None: raise ValueError("La référence A70e est absente.")
            student = student_normalized_error_evaluation_set.get(expectation.comparison_id) if student_normalized_error_evaluation_set else None
            candidates = resolutions.for_production(expectation.comparison_id)
            resolved = tuple(item for item in candidates if item.resolved and isinstance(item.text, str))
            detection = extract_comparison_justification(resolved[0].text, expectation) if len(resolved) == 1 else None
            source, status, reasons = _analyze(expectation, candidates, detection)
            evaluations.append(ComparisonJustificationEvaluation._from_canonical_detection(expectation, interpretation, student, candidates, source, detection, status, reasons))
        return ComparisonJustificationEvaluationSet(expectation_set, interpretation_evaluation_set, student_normalized_error_evaluation_set, tuple(evaluations))


def evaluate_comparison_justifications(interpretation_evaluation_set, expectation_set, student_normalized_error_evaluation_set=None):
    """Delegate to the stateless A70g evaluator."""
    return ComparisonJustificationEvaluator().evaluate(interpretation_evaluation_set, expectation_set, student_normalized_error_evaluation_set)
