"""Objective evaluation of declared quantitative comparisons."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import (
    MAX_EMAX,
    MIN_EMIN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    ROUND_HALF_EVEN,
    localcontext,
)
from enum import Enum

from tpstudio.expectations.quantity_comparisons import (
    ComparisonPedagogicalContext,
    ExpectedQuantityComparison,
    NormalizedErrorThresholds,
    QuantityComparisonExpectationSet,
)
from tpstudio.reasoning.quantity_extraction import QuantityObservation

if False:  # Imported only for static annotation resolution.
    from tpstudio.assessment.notebook_quantities import (
        NotebookQuantityAssessmentItem,
        NotebookQuantityAssessmentSet,
    )


def _assessment_types():
    from tpstudio.assessment.notebook_quantities import (
        NotebookQuantityAssessmentItem,
        NotebookQuantityAssessmentSet,
    )

    return NotebookQuantityAssessmentItem, NotebookQuantityAssessmentSet


class QuantityComparisonEvaluationStatus(str, Enum):
    """Objective outcome of one normalized-error comparison."""

    COHERENT = "coherent"
    MODERATELY_INCOHERENT = "moderately_incoherent"
    STRONGLY_INCOHERENT = "strongly_incoherent"
    NOT_EVALUABLE = "not_evaluable"


class QuantityComparisonNotEvaluableReason(str, Enum):
    """Structured reason why a normalized error cannot be calculated."""

    LEFT_ASSESSMENT_UNAVAILABLE = "left_assessment_unavailable"
    RIGHT_ASSESSMENT_UNAVAILABLE = "right_assessment_unavailable"
    LEFT_ASSESSMENT_AMBIGUOUS = "left_assessment_ambiguous"
    RIGHT_ASSESSMENT_AMBIGUOUS = "right_assessment_ambiguous"
    LEFT_OBSERVATION_MISSING = "left_observation_missing"
    RIGHT_OBSERVATION_MISSING = "right_observation_missing"
    LEFT_VALUE_INVALID = "left_value_invalid"
    RIGHT_VALUE_INVALID = "right_value_invalid"
    LEFT_UNCERTAINTY_MISSING = "left_uncertainty_missing"
    RIGHT_UNCERTAINTY_MISSING = "right_uncertainty_missing"
    LEFT_UNCERTAINTY_NOT_STRICTLY_POSITIVE = (
        "left_uncertainty_not_strictly_positive"
    )
    RIGHT_UNCERTAINTY_NOT_STRICTLY_POSITIVE = (
        "right_uncertainty_not_strictly_positive"
    )
    LEFT_UNIT_MISSING = "left_unit_missing"
    RIGHT_UNIT_MISSING = "right_unit_missing"
    UNIT_MISMATCH = "unit_mismatch"


_EVALUABLE_STATUSES = (
    QuantityComparisonEvaluationStatus.COHERENT,
    QuantityComparisonEvaluationStatus.MODERATELY_INCOHERENT,
    QuantityComparisonEvaluationStatus.STRONGLY_INCOHERENT,
)


def _is_finite_decimal(value: object) -> bool:
    return type(value) is Decimal and value.is_finite()


def _exact_precision(*values: Decimal) -> int:
    minimum_exponent = min(value.as_tuple().exponent for value in values)
    maximum_adjusted = max(value.adjusted() for value in values)
    aligned_digits = maximum_adjusted - minimum_exponent + 1
    return max(28, aligned_digits * 2 + 12)


def _decimal_context(precision: int) -> Context:
    """Build the complete, caller-independent context used by A70b."""

    context = Context(
        prec=precision,
        rounding=ROUND_HALF_EVEN,
        Emin=MIN_EMIN,
        Emax=MAX_EMAX,
        capitals=1,
        clamp=0,
    )
    for signal in context.traps:
        context.traps[signal] = False
    for signal in (InvalidOperation, DivisionByZero, Overflow):
        context.traps[signal] = True
    context.clear_flags()
    return context


def _calculate(
    left_value: Decimal,
    right_value: Decimal,
    left_uncertainty: Decimal,
    right_uncertainty: Decimal,
    thresholds: NormalizedErrorThresholds,
) -> tuple[Decimal, QuantityComparisonEvaluationStatus]:
    values = (
        left_value,
        right_value,
        left_uncertainty,
        right_uncertainty,
        thresholds.coherence_limit,
        thresholds.strong_incoherence_limit,
    )
    with localcontext(_decimal_context(_exact_precision(*values))):
        difference = abs(left_value - right_value)
        square_sum = (
            left_uncertainty * left_uncertainty
            + right_uncertainty * right_uncertainty
        )
        difference_squared = difference * difference
        coherence_boundary = thresholds.coherence_limit**2 * square_sum
        strong_boundary = thresholds.strong_incoherence_limit**2 * square_sum
        if difference_squared < coherence_boundary:
            status = QuantityComparisonEvaluationStatus.COHERENT
        elif difference_squared < strong_boundary:
            status = QuantityComparisonEvaluationStatus.MODERATELY_INCOHERENT
        else:
            status = QuantityComparisonEvaluationStatus.STRONGLY_INCOHERENT
        with localcontext(_decimal_context(28)):
            normalized_error = difference / square_sum.sqrt()
    return normalized_error, status


def _observation(item: NotebookQuantityAssessmentItem | None) -> QuantityObservation | None:
    if item is None or item.assessment is None:
        return None
    return item.assessment.selected_observation


def _same_objects(left: tuple[object, ...], right: tuple[object, ...]) -> bool:
    return len(left) == len(right) and all(
        left_item is right_item for left_item, right_item in zip(left, right)
    )


def _analyze_candidates(
    left_candidates: tuple[NotebookQuantityAssessmentItem, ...],
    right_candidates: tuple[NotebookQuantityAssessmentItem, ...],
) -> tuple[
    NotebookQuantityAssessmentItem | None,
    NotebookQuantityAssessmentItem | None,
    QuantityObservation | None,
    QuantityObservation | None,
    tuple[QuantityComparisonNotEvaluableReason, ...],
]:
    """Apply the unique-ASSESSSED policy and derive all exact reasons."""

    left_assessed = tuple(
        item for item in left_candidates if item.assessed and item.assessment is not None
    )
    right_assessed = tuple(
        item
        for item in right_candidates
        if item.assessed and item.assessment is not None
    )
    left_item = left_assessed[0] if len(left_assessed) == 1 else None
    right_item = right_assessed[0] if len(right_assessed) == 1 else None
    reasons: list[QuantityComparisonNotEvaluableReason] = []
    if not left_assessed:
        reasons.append(QuantityComparisonNotEvaluableReason.LEFT_ASSESSMENT_UNAVAILABLE)
    elif len(left_assessed) > 1:
        reasons.append(QuantityComparisonNotEvaluableReason.LEFT_ASSESSMENT_AMBIGUOUS)
    if not right_assessed:
        reasons.append(QuantityComparisonNotEvaluableReason.RIGHT_ASSESSMENT_UNAVAILABLE)
    elif len(right_assessed) > 1:
        reasons.append(QuantityComparisonNotEvaluableReason.RIGHT_ASSESSMENT_AMBIGUOUS)

    left_observation = _observation(left_item)
    right_observation = _observation(right_item)
    for item, observation, missing, invalid in (
        (
            left_item,
            left_observation,
            QuantityComparisonNotEvaluableReason.LEFT_OBSERVATION_MISSING,
            QuantityComparisonNotEvaluableReason.LEFT_VALUE_INVALID,
        ),
        (
            right_item,
            right_observation,
            QuantityComparisonNotEvaluableReason.RIGHT_OBSERVATION_MISSING,
            QuantityComparisonNotEvaluableReason.RIGHT_VALUE_INVALID,
        ),
    ):
        if item is not None and observation is None:
            reasons.append(missing)
        elif observation is not None and not _is_finite_decimal(observation.value):
            reasons.append(invalid)
    for observation, missing, invalid in (
        (
            left_observation,
            QuantityComparisonNotEvaluableReason.LEFT_UNCERTAINTY_MISSING,
            QuantityComparisonNotEvaluableReason.LEFT_UNCERTAINTY_NOT_STRICTLY_POSITIVE,
        ),
        (
            right_observation,
            QuantityComparisonNotEvaluableReason.RIGHT_UNCERTAINTY_MISSING,
            QuantityComparisonNotEvaluableReason.RIGHT_UNCERTAINTY_NOT_STRICTLY_POSITIVE,
        ),
    ):
        if observation is not None:
            if observation.uncertainty is None:
                reasons.append(missing)
            elif (
                not _is_finite_decimal(observation.uncertainty)
                or observation.uncertainty <= 0
            ):
                reasons.append(invalid)
    for observation, missing in (
        (left_observation, QuantityComparisonNotEvaluableReason.LEFT_UNIT_MISSING),
        (right_observation, QuantityComparisonNotEvaluableReason.RIGHT_UNIT_MISSING),
    ):
        if observation is not None and observation.unit is None:
            reasons.append(missing)
    if (
        left_observation is not None
        and right_observation is not None
        and left_observation.unit is not None
        and right_observation.unit is not None
        and left_observation.unit != right_observation.unit
    ):
        reasons.append(QuantityComparisonNotEvaluableReason.UNIT_MISMATCH)
    return (
        left_item,
        right_item,
        left_observation,
        right_observation,
        tuple(reasons),
    )


@dataclass(frozen=True, slots=True)
class QuantityComparisonEvaluation:
    """Auditable objective result for one declared comparison."""

    expectation: ExpectedQuantityComparison
    left_candidates: tuple[NotebookQuantityAssessmentItem, ...]
    right_candidates: tuple[NotebookQuantityAssessmentItem, ...]
    left_item: NotebookQuantityAssessmentItem | None
    right_item: NotebookQuantityAssessmentItem | None
    status: QuantityComparisonEvaluationStatus
    not_evaluable_reasons: tuple[QuantityComparisonNotEvaluableReason, ...] = ()
    normalized_error: Decimal | None = None

    def __post_init__(self) -> None:
        item_type, _ = _assessment_types()
        if not isinstance(self.expectation, ExpectedQuantityComparison):
            raise TypeError("L'attente doit être une ExpectedQuantityComparison.")
        left = tuple(self.left_candidates)
        right = tuple(self.right_candidates)
        if any(not isinstance(item, item_type) for item in (*left, *right)):
            raise TypeError("Chaque candidat doit être un NotebookQuantityAssessmentItem.")
        if any(item.production_id != self.expectation.left_quantity_id for item in left):
            raise ValueError("Un candidat gauche vise une production étrangère.")
        if any(item.production_id != self.expectation.right_quantity_id for item in right):
            raise ValueError("Un candidat droit vise une production étrangère.")
        object.__setattr__(self, "left_candidates", left)
        object.__setattr__(self, "right_candidates", right)
        for selected, candidates in ((self.left_item, left), (self.right_item, right)):
            if selected is not None and not isinstance(selected, item_type):
                raise TypeError("Un item retenu doit être un NotebookQuantityAssessmentItem.")
            if selected is not None and not any(selected is item for item in candidates):
                raise ValueError("Un item retenu doit appartenir par identité aux candidats.")
        (
            expected_left_item,
            expected_right_item,
            left_observation,
            right_observation,
            expected_reasons,
        ) = _analyze_candidates(left, right)
        if self.left_item is not expected_left_item or self.right_item is not expected_right_item:
            raise ValueError(
                "Les items retenus doivent appliquer la politique d'unicité ASSESSED."
            )
        if not isinstance(self.status, QuantityComparisonEvaluationStatus):
            raise TypeError("Le statut doit être un QuantityComparisonEvaluationStatus.")
        reasons = tuple(self.not_evaluable_reasons)
        if any(not isinstance(reason, QuantityComparisonNotEvaluableReason) for reason in reasons):
            raise TypeError("Chaque raison doit être une QuantityComparisonNotEvaluableReason.")
        if len(reasons) != len(set(reasons)):
            raise ValueError("Les raisons de non-évaluabilité doivent être uniques.")
        object.__setattr__(self, "not_evaluable_reasons", reasons)
        if reasons != expected_reasons:
            raise ValueError(
                "Les raisons doivent correspondre exactement aux candidats observés."
            )
        if self.normalized_error is not None:
            if not _is_finite_decimal(self.normalized_error):
                raise TypeError("L'écart normalisé doit être un Decimal fini ou None.")
            if self.normalized_error < 0:
                raise ValueError("L'écart normalisé ne peut pas être négatif.")

        if self.status is QuantityComparisonEvaluationStatus.NOT_EVALUABLE:
            if self.normalized_error is not None or not reasons:
                raise ValueError("Un résultat non évaluable exige des raisons et aucun En.")
            return
        if reasons or self.normalized_error is None:
            raise ValueError("Un résultat évaluable exige En et aucune raison.")
        observations = (left_observation, right_observation)
        for item, observation in zip((self.left_item, self.right_item), observations):
            if item is None or not item.assessed or item.assessment is None:
                raise ValueError("Un résultat évaluable exige deux items ASSESSED.")
            if observation is None:
                raise ValueError("Un résultat évaluable exige deux observations.")
            if not _is_finite_decimal(observation.value):
                raise ValueError("Les valeurs doivent être des Decimal finis.")
            if not _is_finite_decimal(observation.uncertainty) or observation.uncertainty <= 0:
                raise ValueError("Les incertitudes doivent être des Decimal finis positifs.")
            if observation.unit is None:
                raise ValueError("Un résultat évaluable exige deux unités.")
        assert observations[0] is not None and observations[1] is not None
        if observations[0].unit != observations[1].unit:
            raise ValueError("Les unités doivent être littéralement identiques.")
        expected_error, expected_status = _calculate(
            observations[0].value, observations[1].value,
            observations[0].uncertainty, observations[1].uncertainty,
            self.expectation.thresholds,
        )
        if self.normalized_error != expected_error or self.status is not expected_status:
            raise ValueError("Le statut ou l'écart normalisé est incohérent.")

    @property
    def production_id(self) -> str:
        return self.expectation.production_id

    @property
    def left_quantity_id(self) -> str:
        return self.expectation.left_quantity_id

    @property
    def right_quantity_id(self) -> str:
        return self.expectation.right_quantity_id

    @property
    def thresholds(self) -> NormalizedErrorThresholds:
        return self.expectation.thresholds

    @property
    def pedagogical_context(self) -> ComparisonPedagogicalContext:
        return self.expectation.pedagogical_context

    @property
    def context_note(self) -> str:
        return self.expectation.context_note

    @property
    def evaluable(self) -> bool:
        return self.status in _EVALUABLE_STATUSES

    @property
    def not_evaluable(self) -> bool:
        return not self.evaluable

    @property
    def coherent(self) -> bool:
        return self.status is QuantityComparisonEvaluationStatus.COHERENT

    @property
    def moderately_incoherent(self) -> bool:
        return self.status is QuantityComparisonEvaluationStatus.MODERATELY_INCOHERENT

    @property
    def strongly_incoherent(self) -> bool:
        return self.status is QuantityComparisonEvaluationStatus.STRONGLY_INCOHERENT

    @property
    def left_observation(self) -> QuantityObservation | None:
        return _observation(self.left_item)

    @property
    def right_observation(self) -> QuantityObservation | None:
        return _observation(self.right_item)

    @property
    def left_value(self) -> Decimal | None:
        return self.left_observation.value if self.left_observation else None

    @property
    def right_value(self) -> Decimal | None:
        return self.right_observation.value if self.right_observation else None

    @property
    def left_uncertainty(self) -> Decimal | None:
        return self.left_observation.uncertainty if self.left_observation else None

    @property
    def right_uncertainty(self) -> Decimal | None:
        return self.right_observation.uncertainty if self.right_observation else None

    @property
    def unit(self) -> str | None:
        return self.left_observation.unit if self.evaluable and self.left_observation else None


def _validate_configuration(
    quantity_assessment_set: NotebookQuantityAssessmentSet,
    expectation_set: QuantityComparisonExpectationSet,
) -> None:
    _, set_type = _assessment_types()
    if not isinstance(quantity_assessment_set, set_type):
        raise TypeError("Les quantités doivent former un NotebookQuantityAssessmentSet.")
    plan = quantity_assessment_set.resolution_set.binding_plan.production_plan
    if expectation_set.production_plan is not plan:
        raise ValueError("Les évaluations et les comparaisons doivent partager le même plan.")
    for item in quantity_assessment_set.assessed:
        assert item.assessment is not None
        if item.assessment.quantity_expectation_set is not expectation_set.quantity_expectation_set:
            raise ValueError("Les évaluations doivent réutiliser le jeu d'attentes quantitatives.")


@dataclass(frozen=True, slots=True)
class QuantityComparisonEvaluationSet:
    """Ordered objective evaluations for one comparison expectation set."""

    expectation_set: QuantityComparisonExpectationSet
    quantity_assessment_set: NotebookQuantityAssessmentSet
    evaluations: tuple[QuantityComparisonEvaluation, ...]

    def __post_init__(self) -> None:
        _, set_type = _assessment_types()
        if not isinstance(self.expectation_set, QuantityComparisonExpectationSet):
            raise TypeError("Les attentes doivent former un QuantityComparisonExpectationSet.")
        if not isinstance(self.quantity_assessment_set, set_type):
            raise TypeError("Les quantités doivent former un NotebookQuantityAssessmentSet.")
        evaluations = tuple(self.evaluations)
        if any(not isinstance(item, QuantityComparisonEvaluation) for item in evaluations):
            raise TypeError("Chaque résultat doit être une QuantityComparisonEvaluation.")
        object.__setattr__(self, "evaluations", evaluations)
        _validate_configuration(self.quantity_assessment_set, self.expectation_set)
        expected = self.expectation_set.in_evaluation_order
        if len(evaluations) != len(expected):
            raise ValueError("Une évaluation est requise pour chaque comparaison.")
        if any(evaluation.expectation is not expectation for evaluation, expectation in zip(evaluations, expected)):
            raise ValueError("Les attentes doivent être réutilisées par identité et dans l'ordre.")
        for evaluation in evaluations:
            expected_left = self.quantity_assessment_set.for_production(
                evaluation.left_quantity_id
            )
            expected_right = self.quantity_assessment_set.for_production(
                evaluation.right_quantity_id
            )
            if not _same_objects(evaluation.left_candidates, expected_left):
                raise ValueError("Les candidats gauches sont étrangers au jeu évalué.")
            if not _same_objects(evaluation.right_candidates, expected_right):
                raise ValueError("Les candidats droits sont étrangers au jeu évalué.")

    def __iter__(self) -> Iterator[QuantityComparisonEvaluation]:
        return iter(self.evaluations)

    def __len__(self) -> int:
        return len(self.evaluations)

    def get(self, production_id: str) -> QuantityComparisonEvaluation | None:
        return next((item for item in self.evaluations if item.production_id == production_id), None)

    def for_quantity(self, quantity_production_id: str) -> tuple[QuantityComparisonEvaluation, ...]:
        production = self.expectation_set.production_plan.get(quantity_production_id)
        if production is None:
            raise ValueError(f"Production inconnue : {quantity_production_id!r}.")
        return tuple(item for item in self.evaluations if quantity_production_id in (item.left_quantity_id, item.right_quantity_id))

    def for_status(self, status: QuantityComparisonEvaluationStatus) -> tuple[QuantityComparisonEvaluation, ...]:
        if not isinstance(status, QuantityComparisonEvaluationStatus):
            raise TypeError("Le statut doit être un QuantityComparisonEvaluationStatus.")
        return tuple(item for item in self.evaluations if item.status is status)

    @property
    def coherent(self) -> tuple[QuantityComparisonEvaluation, ...]:
        return self.for_status(QuantityComparisonEvaluationStatus.COHERENT)

    @property
    def moderately_incoherent(self) -> tuple[QuantityComparisonEvaluation, ...]:
        return self.for_status(QuantityComparisonEvaluationStatus.MODERATELY_INCOHERENT)

    @property
    def strongly_incoherent(self) -> tuple[QuantityComparisonEvaluation, ...]:
        return self.for_status(QuantityComparisonEvaluationStatus.STRONGLY_INCOHERENT)

    @property
    def not_evaluable(self) -> tuple[QuantityComparisonEvaluation, ...]:
        return self.for_status(QuantityComparisonEvaluationStatus.NOT_EVALUABLE)

    @property
    def all_evaluable(self) -> bool:
        return not self.not_evaluable

    @property
    def has_not_evaluable(self) -> bool:
        return bool(self.not_evaluable)

    @property
    def has_incoherence(self) -> bool:
        return bool(self.moderately_incoherent or self.strongly_incoherent)

    @property
    def has_strong_incoherence(self) -> bool:
        return bool(self.strongly_incoherent)


class QuantityComparisonEvaluator:
    """Evaluate all declared normalized-error comparisons."""

    def evaluate(self, quantity_assessment_set: NotebookQuantityAssessmentSet, expectation_set: QuantityComparisonExpectationSet) -> QuantityComparisonEvaluationSet:
        _, set_type = _assessment_types()
        if not isinstance(quantity_assessment_set, set_type):
            raise TypeError("Les quantités doivent former un NotebookQuantityAssessmentSet.")
        if not isinstance(expectation_set, QuantityComparisonExpectationSet):
            raise TypeError("Les attentes doivent former un QuantityComparisonExpectationSet.")
        _validate_configuration(quantity_assessment_set, expectation_set)
        evaluations = tuple(self._evaluate_one(quantity_assessment_set, expectation) for expectation in expectation_set.in_evaluation_order)
        return QuantityComparisonEvaluationSet(expectation_set, quantity_assessment_set, evaluations)

    def _evaluate_one(self, assessment_set: NotebookQuantityAssessmentSet, expectation: ExpectedQuantityComparison) -> QuantityComparisonEvaluation:
        left_candidates = assessment_set.for_production(expectation.left_quantity_id)
        right_candidates = assessment_set.for_production(expectation.right_quantity_id)
        (
            left_item,
            right_item,
            left_observation,
            right_observation,
            reasons,
        ) = _analyze_candidates(left_candidates, right_candidates)
        if reasons:
            return QuantityComparisonEvaluation(expectation, left_candidates, right_candidates, left_item, right_item, QuantityComparisonEvaluationStatus.NOT_EVALUABLE, reasons)
        assert left_observation is not None and right_observation is not None
        assert left_observation.uncertainty is not None and right_observation.uncertainty is not None
        normalized_error, status = _calculate(left_observation.value, right_observation.value, left_observation.uncertainty, right_observation.uncertainty, expectation.thresholds)
        return QuantityComparisonEvaluation(expectation, left_candidates, right_candidates, left_item, right_item, status, normalized_error=normalized_error)


def evaluate_quantity_comparisons(quantity_assessment_set: NotebookQuantityAssessmentSet, expectation_set: QuantityComparisonExpectationSet) -> QuantityComparisonEvaluationSet:
    """Delegate to the stateless comparison evaluator."""

    return QuantityComparisonEvaluator().evaluate(quantity_assessment_set, expectation_set)
