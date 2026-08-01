"""Intrinsic presentation evaluation of an observed quantity uncertainty."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from tpstudio.expectations import (
    UncertaintyQualityExpectationSet,
    UncertaintyQualitySpec,
)
from tpstudio.reasoning.quantity_extraction import QuantityObservation

from .models import EvaluationStatus
from .quantity_structure import QuantityStructuralEvaluation


class UncertaintyQualityCriterion(str, Enum):
    """Intrinsic presentation aspect checked on an uncertainty."""

    STRICTLY_POSITIVE = "strictly_positive"
    SIGNIFICANT_DIGITS = "significant_digits"
    DECIMAL_PLACE_ALIGNMENT = "decimal_place_alignment"


_CRITERION_ORDER = (
    UncertaintyQualityCriterion.STRICTLY_POSITIVE,
    UncertaintyQualityCriterion.SIGNIFICANT_DIGITS,
    UncertaintyQualityCriterion.DECIMAL_PLACE_ALIGNMENT,
)


def _significant_digits(value: Decimal) -> int:
    """Count significant digits while preserving explicit trailing zeroes."""

    digits = value.as_tuple().digits
    first_nonzero = next(
        (index for index, digit in enumerate(digits) if digit != 0), None
    )
    return 1 if first_nonzero is None else len(digits) - first_nonzero


@dataclass(frozen=True, slots=True)
class UncertaintyCriterionEvaluation:
    """Immutable result of one intrinsic uncertainty check."""

    criterion: UncertaintyQualityCriterion
    status: EvaluationStatus
    observation: QuantityObservation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.criterion, UncertaintyQualityCriterion):
            raise TypeError("Le critère doit être un UncertaintyQualityCriterion.")
        if not isinstance(self.status, EvaluationStatus):
            raise TypeError("Le statut doit être un EvaluationStatus.")
        if self.observation is not None and not isinstance(
            self.observation, QuantityObservation
        ):
            raise TypeError("L'observation doit être une QuantityObservation.")
        if self.status is EvaluationStatus.DEFERRED:
            raise ValueError("Un contrôle intrinsèque A68e ne peut être différé.")
        if self.status is EvaluationStatus.NOT_APPLICABLE:
            if self.observation is not None:
                raise ValueError("Un contrôle non applicable ne porte aucune preuve.")
            return
        if self.observation is None or self.observation.uncertainty is None:
            raise ValueError(
                "Un contrôle satisfait ou insatisfait exige une incertitude observée."
            )


def _criterion(
    criterion: UncertaintyQualityCriterion,
    *,
    enabled: bool,
    satisfied: bool,
    observation: QuantityObservation | None,
) -> UncertaintyCriterionEvaluation:
    if not enabled or observation is None or observation.uncertainty is None:
        return UncertaintyCriterionEvaluation(
            criterion, EvaluationStatus.NOT_APPLICABLE
        )
    return UncertaintyCriterionEvaluation(
        criterion,
        EvaluationStatus.SATISFIED if satisfied else EvaluationStatus.UNSATISFIED,
        observation,
    )


def _expected_criteria(
    specification: UncertaintyQualitySpec,
    observation: QuantityObservation | None,
) -> tuple[UncertaintyCriterionEvaluation, ...]:
    uncertainty = observation.uncertainty if observation is not None else None
    has_uncertainty = uncertainty is not None
    significant_digits = (
        _significant_digits(uncertainty) if uncertainty is not None else 0
    )
    value_exponent = observation.value.as_tuple().exponent if observation else None
    uncertainty_exponent = (
        uncertainty.as_tuple().exponent if uncertainty is not None else None
    )
    return (
        _criterion(
            UncertaintyQualityCriterion.STRICTLY_POSITIVE,
            enabled=specification.require_strictly_positive,
            satisfied=has_uncertainty and uncertainty > 0,  # type: ignore[operator]
            observation=observation,
        ),
        _criterion(
            UncertaintyQualityCriterion.SIGNIFICANT_DIGITS,
            enabled=specification.allowed_significant_digits is not None,
            satisfied=(
                has_uncertainty
                and significant_digits in specification.allowed_significant_digits
            ) if specification.allowed_significant_digits is not None else False,
            observation=observation,
        ),
        _criterion(
            UncertaintyQualityCriterion.DECIMAL_PLACE_ALIGNMENT,
            enabled=specification.require_matching_decimal_place,
            satisfied=has_uncertainty and value_exponent == uncertainty_exponent,
            observation=observation,
        ),
    )


@dataclass(frozen=True, slots=True)
class QuantityUncertaintyEvaluation:
    """Intrinsic uncertainty evaluation for A68d's selected observation."""

    expectation_set: UncertaintyQualityExpectationSet
    structural_evaluation: QuantityStructuralEvaluation
    specification: UncertaintyQualitySpec
    criteria: tuple[UncertaintyCriterionEvaluation, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.expectation_set, UncertaintyQualityExpectationSet
        ):
            raise TypeError(
                "Les attentes doivent former un UncertaintyQualityExpectationSet."
            )
        if not isinstance(self.structural_evaluation, QuantityStructuralEvaluation):
            raise TypeError("L'évaluation structurelle doit être valide.")
        if not isinstance(self.specification, UncertaintyQualitySpec):
            raise TypeError("La politique doit être une UncertaintyQualitySpec.")

        registered = self.expectation_set.get(self.specification.production_id)
        if registered is None or registered != self.specification:
            raise ValueError("La politique doit appartenir au jeu d'attendus.")
        if self.specification.production_id != self.production_id:
            raise ValueError("La politique ne correspond pas à la production évaluée.")
        if (
            self.structural_evaluation.expectation_set
            != self.expectation_set.quantity_expectation_set
        ):
            raise ValueError("Les jeux d'attendus de quantités sont incohérents.")

        criteria = tuple(self.criteria)
        object.__setattr__(self, "criteria", criteria)
        if any(
            not isinstance(item, UncertaintyCriterionEvaluation)
            for item in criteria
        ):
            raise TypeError(
                "Chaque critère doit être une UncertaintyCriterionEvaluation."
            )
        if tuple(item.criterion for item in criteria) != _CRITERION_ORDER:
            raise ValueError("Les trois critères doivent être uniques et ordonnés.")
        if any(
            item.observation is not None
            and item.observation is not self.selected_observation
            for item in criteria
        ):
            raise ValueError("Seule l'observation sélectionnée par A68d est permise.")
        expected = _expected_criteria(self.specification, self.selected_observation)
        if criteria != expected:
            raise ValueError("Les critères ne correspondent pas à la politique.")

    @property
    def production_id(self) -> str:
        return self.structural_evaluation.detection.production_id

    @property
    def selected_observation(self) -> QuantityObservation | None:
        return self.structural_evaluation.selected_observation

    def get(
        self, criterion: UncertaintyQualityCriterion
    ) -> UncertaintyCriterionEvaluation | None:
        for evaluation in self.criteria:
            if evaluation.criterion is criterion:
                return evaluation
        return None

    @property
    def failures(self) -> tuple[UncertaintyCriterionEvaluation, ...]:
        return tuple(
            item for item in self.criteria
            if item.status is EvaluationStatus.UNSATISFIED
        )

    @property
    def is_applicable(self) -> bool:
        return any(
            item.status is not EvaluationStatus.NOT_APPLICABLE
            for item in self.criteria
        )

    @property
    def satisfied(self) -> bool:
        return not self.failures


class QuantityUncertaintyEvaluator:
    """Evaluate uncertainty presentation on A68d's selected observation."""

    def evaluate(
        self,
        structural_evaluation: QuantityStructuralEvaluation,
        expectation_set: UncertaintyQualityExpectationSet,
    ) -> QuantityUncertaintyEvaluation:
        if not isinstance(structural_evaluation, QuantityStructuralEvaluation):
            raise TypeError("L'évaluation structurelle doit être valide.")
        if not isinstance(expectation_set, UncertaintyQualityExpectationSet):
            raise TypeError(
                "Les attentes doivent former un UncertaintyQualityExpectationSet."
            )
        production_id = structural_evaluation.detection.production_id
        specification = expectation_set.get(production_id)
        if specification is None:
            raise ValueError("Aucune politique d'incertitude pour cette production.")
        if (
            structural_evaluation.expectation_set
            != expectation_set.quantity_expectation_set
        ):
            raise ValueError("Les jeux d'attendus de quantités sont incohérents.")
        criteria = _expected_criteria(
            specification, structural_evaluation.selected_observation
        )
        return QuantityUncertaintyEvaluation(
            expectation_set, structural_evaluation, specification, criteria
        )


def evaluate_quantity_uncertainty(
    structural_evaluation: QuantityStructuralEvaluation,
    expectation_set: UncertaintyQualityExpectationSet,
) -> QuantityUncertaintyEvaluation:
    """Convenience wrapper around :class:`QuantityUncertaintyEvaluator`."""

    return QuantityUncertaintyEvaluator().evaluate(
        structural_evaluation, expectation_set
    )
