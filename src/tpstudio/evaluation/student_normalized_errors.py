"""Compare a literal student En value with the internal A70b reference."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from tpstudio.expectations.student_normalized_errors import (
    ExpectedStudentNormalizedError,
    StudentNormalizedErrorExpectationSet,
)
from tpstudio.notebooks.binding_resolution import NotebookBindingResolution
from tpstudio.reasoning.student_normalized_errors import (
    StudentNormalizedErrorDetection,
    StudentNormalizedErrorObservation,
    extract_student_normalized_error,
)

from .quantity_comparisons import (
    QuantityComparisonEvaluation,
    QuantityComparisonEvaluationSet,
    QuantityComparisonEvaluationStatus,
)


_MAX_EXACT_DIFFERENCE_COEFFICIENT_DIGITS = 1000
_MAX_EXACT_DIFFERENCE_EXPONENT_SPAN = 10000


class StudentNormalizedErrorEvaluationStatus(str, Enum):
    """Numeric agreement of a student's En with the A70b reference."""

    MATCHES_REFERENCE = "matches_reference"
    DIFFERS_FROM_REFERENCE = "differs_from_reference"
    NOT_EVALUABLE = "not_evaluable"


class StudentNormalizedErrorNotEvaluableReason(str, Enum):
    """Reason why student En cannot be compared deterministically."""

    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_AMBIGUOUS = "source_ambiguous"
    STUDENT_VALUE_MISSING = "student_value_missing"
    STUDENT_VALUE_AMBIGUOUS = "student_value_ambiguous"
    STUDENT_VALUE_NEGATIVE = "student_value_negative"
    REFERENCE_NOT_EVALUABLE = "reference_not_evaluable"


def _same_objects(left: tuple[object, ...], right: tuple[object, ...]) -> bool:
    return len(left) == len(right) and all(
        left_item is right_item for left_item, right_item in zip(left, right)
    )


def _exact_difference(left: Decimal, right: Decimal) -> Decimal:
    """Return abs(left-right) without using the active Decimal context."""

    left_tuple = left.as_tuple()
    right_tuple = right.as_tuple()
    if any(
        len(value_tuple.digits) > _MAX_EXACT_DIFFERENCE_COEFFICIENT_DIGITS
        or abs(value_tuple.exponent) > _MAX_EXACT_DIFFERENCE_EXPONENT_SPAN
        for value_tuple in (left_tuple, right_tuple)
    ):
        raise ValueError("Un littéral dépasse la limite technique A70d.")
    exponent = min(left_tuple.exponent, right_tuple.exponent)
    if max(left_tuple.exponent, right_tuple.exponent) - exponent > _MAX_EXACT_DIFFERENCE_EXPONENT_SPAN:
        raise ValueError("L'écart d'exposants dépasse la limite technique A70d.")

    def coefficient(value_tuple) -> int:
        digits = int("".join(str(digit) for digit in value_tuple.digits) or "0")
        signed = -digits if value_tuple.sign else digits
        return signed * (10 ** (value_tuple.exponent - exponent))

    difference = abs(coefficient(left_tuple) - coefficient(right_tuple))
    digits = tuple(int(character) for character in str(difference))
    return Decimal((0, digits, exponent))


def _analyze(
    expectation: ExpectedStudentNormalizedError,
    reference: QuantityComparisonEvaluation,
    candidates: tuple[NotebookBindingResolution, ...],
    detection: StudentNormalizedErrorDetection | None,
) -> tuple[
    NotebookBindingResolution | None,
    StudentNormalizedErrorObservation | None,
    tuple[StudentNormalizedErrorNotEvaluableReason, ...],
]:
    resolved = tuple(
        item for item in candidates if item.resolved and isinstance(item.text, str)
    )
    source = resolved[0] if len(resolved) == 1 else None
    reasons: list[StudentNormalizedErrorNotEvaluableReason] = []
    if not resolved:
        reasons.append(StudentNormalizedErrorNotEvaluableReason.SOURCE_UNAVAILABLE)
    elif len(resolved) > 1:
        reasons.append(StudentNormalizedErrorNotEvaluableReason.SOURCE_AMBIGUOUS)

    observation: StudentNormalizedErrorObservation | None = None
    if source is not None:
        if detection is None:
            raise ValueError("Une source unique exige une détection textuelle.")
        if detection.expectation is not expectation:
            raise ValueError("La détection doit réutiliser exactement l'attente.")
        if detection.absent:
            reasons.append(StudentNormalizedErrorNotEvaluableReason.STUDENT_VALUE_MISSING)
        elif detection.ambiguous:
            reasons.append(StudentNormalizedErrorNotEvaluableReason.STUDENT_VALUE_AMBIGUOUS)
        else:
            observation = detection.selected_observation
            assert observation is not None
            if observation.value < 0:
                reasons.append(StudentNormalizedErrorNotEvaluableReason.STUDENT_VALUE_NEGATIVE)
    elif detection is not None:
        raise ValueError("Une source absente ou ambiguë ne possède aucune détection.")

    if (
        reference.status is QuantityComparisonEvaluationStatus.NOT_EVALUABLE
        or reference.normalized_error is None
    ):
        reasons.append(StudentNormalizedErrorNotEvaluableReason.REFERENCE_NOT_EVALUABLE)
    return source, observation, tuple(reasons)


@dataclass(frozen=True, slots=True)
class StudentNormalizedErrorEvaluation:
    """Auditable numeric comparison of one student En occurrence."""

    expectation: ExpectedStudentNormalizedError
    reference_evaluation: QuantityComparisonEvaluation
    source_candidates: tuple[NotebookBindingResolution, ...]
    source_resolution: NotebookBindingResolution | None
    detection: StudentNormalizedErrorDetection | None
    student_observation: StudentNormalizedErrorObservation | None
    status: StudentNormalizedErrorEvaluationStatus
    not_evaluable_reasons: tuple[StudentNormalizedErrorNotEvaluableReason, ...] = ()
    absolute_difference: Decimal | None = None

    def __post_init__(self) -> None:
        self._validate(detection_is_canonical=False)

    @classmethod
    def _from_canonical_detection(
        cls,
        expectation: ExpectedStudentNormalizedError,
        reference_evaluation: QuantityComparisonEvaluation,
        source_candidates: tuple[NotebookBindingResolution, ...],
        source_resolution: NotebookBindingResolution | None,
        detection: StudentNormalizedErrorDetection | None,
        student_observation: StudentNormalizedErrorObservation | None,
        status: StudentNormalizedErrorEvaluationStatus,
        not_evaluable_reasons: tuple[StudentNormalizedErrorNotEvaluableReason, ...] = (),
        absolute_difference: Decimal | None = None,
    ) -> StudentNormalizedErrorEvaluation:
        """Build from the extractor result already obtained by the evaluator."""

        instance = object.__new__(cls)
        for name, value in (
            ("expectation", expectation),
            ("reference_evaluation", reference_evaluation),
            ("source_candidates", source_candidates),
            ("source_resolution", source_resolution),
            ("detection", detection),
            ("student_observation", student_observation),
            ("status", status),
            ("not_evaluable_reasons", not_evaluable_reasons),
            ("absolute_difference", absolute_difference),
        ):
            object.__setattr__(instance, name, value)
        instance._validate(detection_is_canonical=True)
        return instance

    def _validate(self, *, detection_is_canonical: bool) -> None:
        if not isinstance(self.expectation, ExpectedStudentNormalizedError):
            raise TypeError("L'attente doit être un ExpectedStudentNormalizedError.")
        if not isinstance(self.reference_evaluation, QuantityComparisonEvaluation):
            raise TypeError("La référence doit être une QuantityComparisonEvaluation.")
        if self.reference_evaluation.production_id != self.expectation.comparison_id:
            raise ValueError("La référence ne correspond pas à la comparaison attendue.")
        candidates = tuple(self.source_candidates)
        if any(not isinstance(item, NotebookBindingResolution) for item in candidates):
            raise TypeError("Chaque source doit être une NotebookBindingResolution.")
        if any(item.production_id != self.expectation.comparison_id for item in candidates):
            raise ValueError("Une résolution vise une comparaison étrangère.")
        object.__setattr__(self, "source_candidates", candidates)
        if self.source_resolution is not None and not isinstance(
            self.source_resolution, NotebookBindingResolution
        ):
            raise TypeError("La source retenue doit être une NotebookBindingResolution.")
        if self.detection is not None and not isinstance(
            self.detection, StudentNormalizedErrorDetection
        ):
            raise TypeError("La détection doit être une StudentNormalizedErrorDetection.")
        if self.student_observation is not None and not isinstance(
            self.student_observation, StudentNormalizedErrorObservation
        ):
            raise TypeError("L'observation doit être une StudentNormalizedErrorObservation.")
        if not isinstance(self.status, StudentNormalizedErrorEvaluationStatus):
            raise TypeError("Le statut doit être un StudentNormalizedErrorEvaluationStatus.")
        reasons = tuple(self.not_evaluable_reasons)
        if any(not isinstance(item, StudentNormalizedErrorNotEvaluableReason) for item in reasons):
            raise TypeError("Chaque raison doit être une StudentNormalizedErrorNotEvaluableReason.")
        if len(reasons) != len(set(reasons)):
            raise ValueError("Les raisons doivent être uniques.")
        object.__setattr__(self, "not_evaluable_reasons", reasons)
        source, observation, expected_reasons = _analyze(
            self.expectation, self.reference_evaluation, candidates, self.detection
        )
        if source is not None and not detection_is_canonical:
            assert isinstance(source.text, str)
            canonical = extract_student_normalized_error(source.text, self.expectation)
            if self.detection != canonical:
                raise ValueError(
                    "La détection doit correspondre exactement au texte résolu."
                )
        if self.source_resolution is not source:
            raise ValueError("La source retenue ne respecte pas la politique d'unicité.")
        if self.student_observation is not observation:
            raise ValueError("L'observation retenue ne respecte pas la politique d'unicité.")
        if reasons != expected_reasons:
            raise ValueError("Les raisons ne correspondent pas exactement aux sources.")
        if self.absolute_difference is not None:
            if type(self.absolute_difference) is not Decimal:
                raise TypeError("La différence doit être exactement un Decimal.")
            if not self.absolute_difference.is_finite() or self.absolute_difference < 0:
                raise ValueError("La différence doit être finie et positive ou nulle.")
        if self.status is StudentNormalizedErrorEvaluationStatus.NOT_EVALUABLE:
            if not reasons or self.absolute_difference is not None:
                raise ValueError("Un résultat non évaluable exige des raisons et aucune différence.")
            return
        if reasons or observation is None or self.reference_evaluation.normalized_error is None:
            raise ValueError("Un résultat évaluable exige une observation et une référence.")
        expected_difference = _exact_difference(
            observation.value, self.reference_evaluation.normalized_error
        )
        if self.absolute_difference != expected_difference:
            raise ValueError("La différence absolue ne correspond pas aux valeurs.")
        expected_status = (
            StudentNormalizedErrorEvaluationStatus.MATCHES_REFERENCE
            if expected_difference <= self.expectation.absolute_tolerance
            else StudentNormalizedErrorEvaluationStatus.DIFFERS_FROM_REFERENCE
        )
        if self.status is not expected_status:
            raise ValueError("Le statut ne correspond pas à la tolérance déclarée.")

    @property
    def comparison_id(self) -> str:
        return self.expectation.comparison_id

    @property
    def reference_value(self) -> Decimal | None:
        return self.reference_evaluation.normalized_error

    @property
    def student_value(self) -> Decimal | None:
        return self.student_observation.value if self.student_observation else None

    @property
    def tolerance(self) -> Decimal:
        return self.expectation.absolute_tolerance

    @property
    def evaluable(self) -> bool:
        return self.status is not StudentNormalizedErrorEvaluationStatus.NOT_EVALUABLE

    @property
    def not_evaluable(self) -> bool:
        return not self.evaluable

    @property
    def matches_reference(self) -> bool:
        return self.status is StudentNormalizedErrorEvaluationStatus.MATCHES_REFERENCE

    @property
    def differs_from_reference(self) -> bool:
        return self.status is StudentNormalizedErrorEvaluationStatus.DIFFERS_FROM_REFERENCE

    @property
    def source_text_start(self) -> int | None:
        return self.student_observation.start if self.student_observation else None

    @property
    def source_text_end(self) -> int | None:
        return self.student_observation.end if self.student_observation else None


@dataclass(frozen=True, slots=True)
class StudentNormalizedErrorEvaluationSet:
    """Ordered student-En evaluations linked to their complete A70b set."""

    expectation_set: StudentNormalizedErrorExpectationSet
    comparison_evaluation_set: QuantityComparisonEvaluationSet
    evaluations: tuple[StudentNormalizedErrorEvaluation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.expectation_set, StudentNormalizedErrorExpectationSet):
            raise TypeError("Les attentes doivent former un StudentNormalizedErrorExpectationSet.")
        if not isinstance(self.comparison_evaluation_set, QuantityComparisonEvaluationSet):
            raise TypeError("Les références doivent former un QuantityComparisonEvaluationSet.")
        if self.expectation_set.comparison_expectation_set is not self.comparison_evaluation_set.expectation_set:
            raise ValueError("Les attentes A70a doivent être réutilisées par identité.")
        evaluations = tuple(self.evaluations)
        if any(not isinstance(item, StudentNormalizedErrorEvaluation) for item in evaluations):
            raise TypeError("Chaque résultat doit être un StudentNormalizedErrorEvaluation.")
        object.__setattr__(self, "evaluations", evaluations)
        expected = self.expectation_set.in_evaluation_order
        if len(evaluations) != len(expected):
            raise ValueError("Une évaluation est requise pour chaque attente.")
        resolutions = self.comparison_evaluation_set.quantity_assessment_set.resolution_set
        for evaluation, expectation in zip(evaluations, expected):
            if evaluation.expectation is not expectation:
                raise ValueError("Les attentes doivent être réutilisées par identité et dans l'ordre.")
            reference = self.comparison_evaluation_set.get(expectation.comparison_id)
            if evaluation.reference_evaluation is not reference:
                raise ValueError("La référence doit provenir par identité du set A70b.")
            candidates = resolutions.for_production(expectation.comparison_id)
            if not _same_objects(evaluation.source_candidates, candidates):
                raise ValueError("Les sources doivent provenir par identité des résolutions.")

    def __iter__(self) -> Iterator[StudentNormalizedErrorEvaluation]:
        return iter(self.evaluations)

    def __len__(self) -> int:
        return len(self.evaluations)

    def get(self, comparison_id: str) -> StudentNormalizedErrorEvaluation | None:
        return next((item for item in self.evaluations if item.comparison_id == comparison_id), None)

    def for_status(self, status: StudentNormalizedErrorEvaluationStatus) -> tuple[StudentNormalizedErrorEvaluation, ...]:
        if not isinstance(status, StudentNormalizedErrorEvaluationStatus):
            raise TypeError("Le statut doit être un StudentNormalizedErrorEvaluationStatus.")
        return tuple(item for item in self.evaluations if item.status is status)

    def for_reason(self, reason: StudentNormalizedErrorNotEvaluableReason) -> tuple[StudentNormalizedErrorEvaluation, ...]:
        if not isinstance(reason, StudentNormalizedErrorNotEvaluableReason):
            raise TypeError("La raison doit être une StudentNormalizedErrorNotEvaluableReason.")
        return tuple(item for item in self.evaluations if reason in item.not_evaluable_reasons)

    @property
    def matches(self) -> tuple[StudentNormalizedErrorEvaluation, ...]:
        return self.for_status(StudentNormalizedErrorEvaluationStatus.MATCHES_REFERENCE)

    @property
    def differences(self) -> tuple[StudentNormalizedErrorEvaluation, ...]:
        return self.for_status(StudentNormalizedErrorEvaluationStatus.DIFFERS_FROM_REFERENCE)

    @property
    def not_evaluable(self) -> tuple[StudentNormalizedErrorEvaluation, ...]:
        return self.for_status(StudentNormalizedErrorEvaluationStatus.NOT_EVALUABLE)

    @property
    def all_evaluable(self) -> bool:
        return not self.not_evaluable

    @property
    def has_differences(self) -> bool:
        return bool(self.differences)

    @property
    def has_not_evaluable(self) -> bool:
        return bool(self.not_evaluable)


class StudentNormalizedErrorEvaluator:
    """Evaluate literal student En values against existing A70b references."""

    def evaluate(
        self,
        comparison_evaluation_set: QuantityComparisonEvaluationSet,
        expectation_set: StudentNormalizedErrorExpectationSet,
    ) -> StudentNormalizedErrorEvaluationSet:
        if not isinstance(comparison_evaluation_set, QuantityComparisonEvaluationSet):
            raise TypeError("Les références doivent former un QuantityComparisonEvaluationSet.")
        if not isinstance(expectation_set, StudentNormalizedErrorExpectationSet):
            raise TypeError("Les attentes doivent former un StudentNormalizedErrorExpectationSet.")
        if expectation_set.comparison_expectation_set is not comparison_evaluation_set.expectation_set:
            raise ValueError("Les attentes A70a doivent être réutilisées par identité.")
        resolution_set = comparison_evaluation_set.quantity_assessment_set.resolution_set
        evaluations: list[StudentNormalizedErrorEvaluation] = []
        for expectation in expectation_set.in_evaluation_order:
            reference = comparison_evaluation_set.get(expectation.comparison_id)
            if reference is None:
                raise ValueError("La comparaison attendue est absente du set A70b.")
            candidates = resolution_set.for_production(expectation.comparison_id)
            resolved = tuple(item for item in candidates if item.resolved and isinstance(item.text, str))
            detection = (
                extract_student_normalized_error(resolved[0].text, expectation)
                if len(resolved) == 1
                else None
            )
            source, observation, reasons = _analyze(
                expectation, reference, candidates, detection
            )
            if reasons:
                evaluations.append(StudentNormalizedErrorEvaluation._from_canonical_detection(
                    expectation, reference, candidates, source, detection, observation,
                    StudentNormalizedErrorEvaluationStatus.NOT_EVALUABLE, reasons,
                ))
                continue
            assert observation is not None and reference.normalized_error is not None
            difference = _exact_difference(observation.value, reference.normalized_error)
            status = (
                StudentNormalizedErrorEvaluationStatus.MATCHES_REFERENCE
                if difference <= expectation.absolute_tolerance
                else StudentNormalizedErrorEvaluationStatus.DIFFERS_FROM_REFERENCE
            )
            evaluations.append(StudentNormalizedErrorEvaluation._from_canonical_detection(
                expectation, reference, candidates, source, detection, observation,
                status, absolute_difference=difference,
            ))
        return StudentNormalizedErrorEvaluationSet(
            expectation_set, comparison_evaluation_set, tuple(evaluations)
        )


def evaluate_student_normalized_errors(
    comparison_evaluation_set: QuantityComparisonEvaluationSet,
    expectation_set: StudentNormalizedErrorExpectationSet,
) -> StudentNormalizedErrorEvaluationSet:
    """Delegate to the stateless student normalized-error evaluator."""

    return StudentNormalizedErrorEvaluator().evaluate(
        comparison_evaluation_set, expectation_set
    )
