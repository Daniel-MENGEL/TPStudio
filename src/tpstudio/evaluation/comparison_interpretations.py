"""Evaluate literal comparison conclusions against objective A70b results."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from tpstudio.expectations.comparison_interpretations import (
    ComparisonInterpretationExpectationSet,
    ComparisonInterpretationKind,
    ExpectedComparisonInterpretation,
)
from tpstudio.expectations.quantity_comparisons import ComparisonPedagogicalContext
from tpstudio.notebooks.binding_resolution import NotebookBindingResolution
from tpstudio.reasoning.comparison_interpretations import (
    ComparisonInterpretationDetection,
    ComparisonInterpretationObservation,
    extract_comparison_interpretation,
)

from .quantity_comparisons import (
    QuantityComparisonEvaluation,
    QuantityComparisonEvaluationSet,
    QuantityComparisonEvaluationStatus,
)
from .student_normalized_errors import (
    StudentNormalizedErrorEvaluation,
    StudentNormalizedErrorEvaluationSet,
    StudentNormalizedErrorEvaluationStatus,
)


class ComparisonInterpretationEvaluationStatus(str, Enum):
    MATCHES_OBJECTIVE_CLASSIFICATION = "matches_objective_classification"
    CONTRADICTS_OBJECTIVE_CLASSIFICATION = "contradicts_objective_classification"
    PARTIALLY_MATCHES_OBJECTIVE_CLASSIFICATION = "partially_matches_objective_classification"
    NOT_EVALUABLE = "not_evaluable"


class ComparisonInterpretationNotEvaluableReason(str, Enum):
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_AMBIGUOUS = "source_ambiguous"
    INTERPRETATION_MISSING = "interpretation_missing"
    INTERPRETATION_AMBIGUOUS = "interpretation_ambiguous"
    OBJECTIVE_CLASSIFICATION_NOT_EVALUABLE = "objective_classification_not_evaluable"


def _same_objects(left: tuple[object, ...], right: tuple[object, ...]) -> bool:
    return len(left) == len(right) and all(a is b for a, b in zip(left, right))


def _mapped_status(
    reference: QuantityComparisonEvaluation,
    kind: ComparisonInterpretationKind,
) -> ComparisonInterpretationEvaluationStatus:
    objective = reference.status
    if objective is QuantityComparisonEvaluationStatus.COHERENT:
        return (
            ComparisonInterpretationEvaluationStatus.MATCHES_OBJECTIVE_CLASSIFICATION
            if kind is ComparisonInterpretationKind.COHERENT
            else ComparisonInterpretationEvaluationStatus.CONTRADICTS_OBJECTIVE_CLASSIFICATION
        )
    if objective is QuantityComparisonEvaluationStatus.MODERATELY_INCOHERENT:
        if kind is ComparisonInterpretationKind.INCOHERENT:
            return ComparisonInterpretationEvaluationStatus.MATCHES_OBJECTIVE_CLASSIFICATION
        if kind in (ComparisonInterpretationKind.STRONGLY_INCOHERENT, ComparisonInterpretationKind.METHOD_LIMITATION):
            return ComparisonInterpretationEvaluationStatus.PARTIALLY_MATCHES_OBJECTIVE_CLASSIFICATION
        return ComparisonInterpretationEvaluationStatus.CONTRADICTS_OBJECTIVE_CLASSIFICATION
    if objective is QuantityComparisonEvaluationStatus.STRONGLY_INCOHERENT:
        if kind is ComparisonInterpretationKind.STRONGLY_INCOHERENT:
            return ComparisonInterpretationEvaluationStatus.MATCHES_OBJECTIVE_CLASSIFICATION
        if kind is ComparisonInterpretationKind.INCOHERENT:
            return ComparisonInterpretationEvaluationStatus.PARTIALLY_MATCHES_OBJECTIVE_CLASSIFICATION
        if kind is ComparisonInterpretationKind.COHERENT:
            return ComparisonInterpretationEvaluationStatus.CONTRADICTS_OBJECTIVE_CLASSIFICATION
        return (
            ComparisonInterpretationEvaluationStatus.MATCHES_OBJECTIVE_CLASSIFICATION
            if reference.pedagogical_context is ComparisonPedagogicalContext.METHOD_LIMITATION_EXPECTED
            else ComparisonInterpretationEvaluationStatus.PARTIALLY_MATCHES_OBJECTIVE_CLASSIFICATION
        )
    return ComparisonInterpretationEvaluationStatus.NOT_EVALUABLE


def _analyze(
    expectation: ExpectedComparisonInterpretation,
    reference: QuantityComparisonEvaluation,
    candidates: tuple[NotebookBindingResolution, ...],
    detection: ComparisonInterpretationDetection | None,
) -> tuple[
    NotebookBindingResolution | None,
    ComparisonInterpretationObservation | None,
    ComparisonInterpretationEvaluationStatus,
    tuple[ComparisonInterpretationNotEvaluableReason, ...],
]:
    resolved = tuple(item for item in candidates if item.resolved and isinstance(item.text, str))
    source = resolved[0] if len(resolved) == 1 else None
    reasons: list[ComparisonInterpretationNotEvaluableReason] = []
    if not resolved:
        reasons.append(ComparisonInterpretationNotEvaluableReason.SOURCE_UNAVAILABLE)
    elif len(resolved) > 1:
        reasons.append(ComparisonInterpretationNotEvaluableReason.SOURCE_AMBIGUOUS)
    observation = None
    if source is not None:
        if detection is None or detection.expectation is not expectation:
            raise ValueError("Une source unique exige la détection de cette attente.")
        if detection.absent:
            reasons.append(ComparisonInterpretationNotEvaluableReason.INTERPRETATION_MISSING)
        elif detection.ambiguous:
            reasons.append(ComparisonInterpretationNotEvaluableReason.INTERPRETATION_AMBIGUOUS)
        else:
            observation = detection.selected_observation
    elif detection is not None:
        raise ValueError("Une source absente ou ambiguë ne possède aucune détection.")
    if reference.status is QuantityComparisonEvaluationStatus.NOT_EVALUABLE:
        reasons.append(ComparisonInterpretationNotEvaluableReason.OBJECTIVE_CLASSIFICATION_NOT_EVALUABLE)
    status = (
        ComparisonInterpretationEvaluationStatus.NOT_EVALUABLE
        if reasons
        else _mapped_status(reference, observation.kind)  # type: ignore[union-attr]
    )
    return source, observation, status, tuple(reasons)


@dataclass(frozen=True, slots=True)
class ComparisonInterpretationEvaluation:
    expectation: ExpectedComparisonInterpretation
    reference_evaluation: QuantityComparisonEvaluation
    student_normalized_error_evaluation: StudentNormalizedErrorEvaluation | None
    source_candidates: tuple[NotebookBindingResolution, ...]
    source_resolution: NotebookBindingResolution | None
    detection: ComparisonInterpretationDetection | None
    observation: ComparisonInterpretationObservation | None
    status: ComparisonInterpretationEvaluationStatus
    not_evaluable_reasons: tuple[ComparisonInterpretationNotEvaluableReason, ...] = ()

    def __post_init__(self) -> None:
        self._validate(canonical=False)

    @classmethod
    def _from_canonical_detection(cls, *values):
        instance = object.__new__(cls)
        names = (
            "expectation", "reference_evaluation", "student_normalized_error_evaluation",
            "source_candidates", "source_resolution", "detection", "observation",
            "status", "not_evaluable_reasons",
        )
        for name, value in zip(names, values):
            object.__setattr__(instance, name, value)
        instance._validate(canonical=True)
        return instance

    def _validate(self, *, canonical: bool) -> None:
        if type(self.expectation) is not ExpectedComparisonInterpretation:
            raise TypeError("L'attente doit être exactement une attente d'interprétation.")
        if type(self.reference_evaluation) is not QuantityComparisonEvaluation:
            raise TypeError("La référence doit être exactement une évaluation A70b.")
        if self.reference_evaluation.production_id != self.expectation.comparison_id:
            raise ValueError("La référence vise une comparaison étrangère.")
        student = self.student_normalized_error_evaluation
        if student is not None:
            if type(student) is not StudentNormalizedErrorEvaluation:
                raise TypeError("L'évaluation En étudiante doit être une évaluation A70d.")
            if student.comparison_id != self.expectation.comparison_id:
                raise ValueError("L'évaluation A70d vise une comparaison étrangère.")
            if student.reference_evaluation is not self.reference_evaluation:
                raise ValueError("A70d et A70e doivent partager la référence A70b par identité.")
        if isinstance(self.source_candidates, (str, bytes)):
            raise TypeError("Les sources doivent former une collection ordonnée.")
        candidates = tuple(self.source_candidates)
        if any(type(item) is not NotebookBindingResolution for item in candidates):
            raise TypeError("Chaque source doit être exactement une résolution de binding.")
        if any(item.production_id != self.expectation.comparison_id for item in candidates):
            raise ValueError("Une source vise une comparaison étrangère.")
        object.__setattr__(self, "source_candidates", candidates)
        if self.source_resolution is not None and type(self.source_resolution) is not NotebookBindingResolution:
            raise TypeError("La source retenue doit être une résolution de binding.")
        if self.detection is not None and type(self.detection) is not ComparisonInterpretationDetection:
            raise TypeError("La détection est invalide.")
        if self.observation is not None and type(self.observation) is not ComparisonInterpretationObservation:
            raise TypeError("L'observation est invalide.")
        if type(self.status) is not ComparisonInterpretationEvaluationStatus:
            raise TypeError("Le statut d'évaluation est invalide.")
        if isinstance(self.not_evaluable_reasons, (str, bytes)):
            raise TypeError("Les raisons doivent former une collection ordonnée.")
        reasons = tuple(self.not_evaluable_reasons)
        if any(type(reason) is not ComparisonInterpretationNotEvaluableReason for reason in reasons):
            raise TypeError("Une raison de non-évaluabilité est invalide.")
        if len(reasons) != len(set(reasons)):
            raise ValueError("Les raisons doivent être uniques.")
        object.__setattr__(self, "not_evaluable_reasons", reasons)
        source, observation, status, expected_reasons = _analyze(
            self.expectation, self.reference_evaluation, candidates, self.detection
        )
        if source is not None and not canonical:
            assert isinstance(source.text, str)
            if self.detection != extract_comparison_interpretation(source.text, self.expectation):
                raise ValueError("La détection ne correspond pas exactement au texte résolu.")
        if self.source_resolution is not source:
            raise ValueError("La source retenue ne respecte pas la politique d'unicité.")
        if self.observation is not observation:
            raise ValueError("L'observation retenue ne respecte pas la politique d'unicité.")
        if self.status is not status or reasons != expected_reasons:
            raise ValueError("Le statut ou les raisons ne respectent pas la politique A70e.")

    @property
    def comparison_id(self) -> str:
        return self.expectation.comparison_id

    @property
    def objective_status(self) -> QuantityComparisonEvaluationStatus:
        return self.reference_evaluation.status

    @property
    def observed_kind(self) -> ComparisonInterpretationKind | None:
        return self.observation.kind if self.observation else None

    @property
    def pedagogical_context(self) -> ComparisonPedagogicalContext:
        return self.reference_evaluation.pedagogical_context

    @property
    def student_normalized_error_status(self) -> StudentNormalizedErrorEvaluationStatus | None:
        return self.student_normalized_error_evaluation.status if self.student_normalized_error_evaluation else None

    @property
    def evaluable(self) -> bool:
        return self.status is not ComparisonInterpretationEvaluationStatus.NOT_EVALUABLE

    @property
    def not_evaluable(self) -> bool:
        return not self.evaluable

    @property
    def matches(self) -> bool:
        return self.status is ComparisonInterpretationEvaluationStatus.MATCHES_OBJECTIVE_CLASSIFICATION

    @property
    def partially_matches(self) -> bool:
        return self.status is ComparisonInterpretationEvaluationStatus.PARTIALLY_MATCHES_OBJECTIVE_CLASSIFICATION

    @property
    def contradicts(self) -> bool:
        return self.status is ComparisonInterpretationEvaluationStatus.CONTRADICTS_OBJECTIVE_CLASSIFICATION

    @property
    def source_text_start(self) -> int | None:
        return self.observation.start if self.observation else None

    @property
    def source_text_end(self) -> int | None:
        return self.observation.end if self.observation else None


@dataclass(frozen=True, slots=True)
class ComparisonInterpretationEvaluationSet:
    expectation_set: ComparisonInterpretationExpectationSet
    comparison_evaluation_set: QuantityComparisonEvaluationSet
    student_normalized_error_evaluation_set: StudentNormalizedErrorEvaluationSet | None
    evaluations: tuple[ComparisonInterpretationEvaluation, ...]

    def __post_init__(self) -> None:
        if type(self.expectation_set) is not ComparisonInterpretationExpectationSet:
            raise TypeError("Les attentes doivent former exactement un jeu A70e.")
        if type(self.comparison_evaluation_set) is not QuantityComparisonEvaluationSet:
            raise TypeError("Les références doivent former exactement un jeu A70b.")
        if self.expectation_set.comparison_expectation_set is not self.comparison_evaluation_set.expectation_set:
            raise ValueError("A70e et A70b doivent réutiliser les attentes A70a par identité.")
        student_set = self.student_normalized_error_evaluation_set
        if student_set is not None:
            if type(student_set) is not StudentNormalizedErrorEvaluationSet:
                raise TypeError("Les En étudiants doivent former exactement un jeu A70d.")
            if student_set.comparison_evaluation_set is not self.comparison_evaluation_set:
                raise ValueError("A70d et A70e doivent partager le jeu A70b par identité.")
        if isinstance(self.evaluations, (str, bytes)):
            raise TypeError("Les évaluations doivent former une collection ordonnée.")
        evaluations = tuple(self.evaluations)
        if any(type(item) is not ComparisonInterpretationEvaluation for item in evaluations):
            raise TypeError("Chaque résultat doit être une évaluation A70e.")
        object.__setattr__(self, "evaluations", evaluations)
        expected = self.expectation_set.in_evaluation_order
        if len(evaluations) != len(expected):
            raise ValueError("Une évaluation est requise pour chaque attente A70e.")
        resolutions = self.comparison_evaluation_set.quantity_assessment_set.resolution_set
        for evaluation, expectation in zip(evaluations, expected):
            if evaluation.expectation is not expectation:
                raise ValueError("Les attentes doivent être réutilisées par identité et dans l'ordre.")
            if evaluation.reference_evaluation is not self.comparison_evaluation_set.get(expectation.comparison_id):
                raise ValueError("La référence A70b doit provenir du set par identité.")
            expected_student = student_set.get(expectation.comparison_id) if student_set else None
            if evaluation.student_normalized_error_evaluation is not expected_student:
                raise ValueError("La référence A70d doit provenir du set par identité lorsqu'elle existe.")
            if not _same_objects(evaluation.source_candidates, resolutions.for_production(expectation.comparison_id)):
                raise ValueError("Les sources doivent provenir du resolution_set associé.")

    def __iter__(self) -> Iterator[ComparisonInterpretationEvaluation]:
        return iter(self.evaluations)

    def __len__(self) -> int:
        return len(self.evaluations)

    def get(self, comparison_id: str) -> ComparisonInterpretationEvaluation | None:
        return next((item for item in self.evaluations if item.comparison_id == comparison_id), None)

    def for_status(self, status: ComparisonInterpretationEvaluationStatus) -> tuple[ComparisonInterpretationEvaluation, ...]:
        if type(status) is not ComparisonInterpretationEvaluationStatus:
            raise TypeError("Le statut est invalide.")
        return tuple(item for item in self.evaluations if item.status is status)

    def for_reason(self, reason: ComparisonInterpretationNotEvaluableReason) -> tuple[ComparisonInterpretationEvaluation, ...]:
        if type(reason) is not ComparisonInterpretationNotEvaluableReason:
            raise TypeError("La raison est invalide.")
        return tuple(item for item in self.evaluations if reason in item.not_evaluable_reasons)

    @property
    def matches(self):
        return self.for_status(ComparisonInterpretationEvaluationStatus.MATCHES_OBJECTIVE_CLASSIFICATION)

    @property
    def partial_matches(self):
        return self.for_status(ComparisonInterpretationEvaluationStatus.PARTIALLY_MATCHES_OBJECTIVE_CLASSIFICATION)

    @property
    def contradictions(self):
        return self.for_status(ComparisonInterpretationEvaluationStatus.CONTRADICTS_OBJECTIVE_CLASSIFICATION)

    @property
    def not_evaluable(self):
        return self.for_status(ComparisonInterpretationEvaluationStatus.NOT_EVALUABLE)

    @property
    def all_evaluable(self) -> bool:
        return not self.not_evaluable

    @property
    def has_contradictions(self) -> bool:
        return bool(self.contradictions)

    @property
    def has_partial_matches(self) -> bool:
        return bool(self.partial_matches)

    @property
    def has_not_evaluable(self) -> bool:
        return bool(self.not_evaluable)


class ComparisonInterpretationEvaluator:
    def evaluate(
        self,
        comparison_evaluation_set: QuantityComparisonEvaluationSet,
        expectation_set: ComparisonInterpretationExpectationSet,
        student_normalized_error_evaluation_set: StudentNormalizedErrorEvaluationSet | None = None,
    ) -> ComparisonInterpretationEvaluationSet:
        if type(comparison_evaluation_set) is not QuantityComparisonEvaluationSet:
            raise TypeError("Les références doivent former exactement un jeu A70b.")
        if type(expectation_set) is not ComparisonInterpretationExpectationSet:
            raise TypeError("Les attentes doivent former exactement un jeu A70e.")
        if expectation_set.comparison_expectation_set is not comparison_evaluation_set.expectation_set:
            raise ValueError("A70e et A70b doivent réutiliser les attentes A70a par identité.")
        if student_normalized_error_evaluation_set is not None:
            if type(student_normalized_error_evaluation_set) is not StudentNormalizedErrorEvaluationSet:
                raise TypeError("Les En étudiants doivent former exactement un jeu A70d.")
            if student_normalized_error_evaluation_set.comparison_evaluation_set is not comparison_evaluation_set:
                raise ValueError("A70d et A70e doivent partager le jeu A70b par identité.")
        resolutions = comparison_evaluation_set.quantity_assessment_set.resolution_set
        evaluations = []
        for expectation in expectation_set.in_evaluation_order:
            reference = comparison_evaluation_set.get(expectation.comparison_id)
            if reference is None:
                raise ValueError("La comparaison attendue est absente du set A70b.")
            student = student_normalized_error_evaluation_set.get(expectation.comparison_id) if student_normalized_error_evaluation_set else None
            candidates = resolutions.for_production(expectation.comparison_id)
            resolved = tuple(item for item in candidates if item.resolved and isinstance(item.text, str))
            detection = extract_comparison_interpretation(resolved[0].text, expectation) if len(resolved) == 1 else None
            source, observation, status, reasons = _analyze(expectation, reference, candidates, detection)
            evaluations.append(ComparisonInterpretationEvaluation._from_canonical_detection(
                expectation, reference, student, candidates, source, detection, observation, status, reasons
            ))
        return ComparisonInterpretationEvaluationSet(
            expectation_set, comparison_evaluation_set,
            student_normalized_error_evaluation_set, tuple(evaluations)
        )


def evaluate_comparison_interpretations(
    comparison_evaluation_set: QuantityComparisonEvaluationSet,
    expectation_set: ComparisonInterpretationExpectationSet,
    student_normalized_error_evaluation_set: StudentNormalizedErrorEvaluationSet | None = None,
) -> ComparisonInterpretationEvaluationSet:
    """Delegate to the stateless comparison-interpretation evaluator."""

    return ComparisonInterpretationEvaluator().evaluate(
        comparison_evaluation_set, expectation_set, student_normalized_error_evaluation_set
    )
