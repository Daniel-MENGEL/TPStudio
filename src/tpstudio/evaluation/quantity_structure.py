"""Structural evaluation of one detected textual quantity."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tpstudio.expectations import (
    PresenceRequirement,
    QuantityExpectationSet,
    ScientificProductionKind,
)
from tpstudio.reasoning.quantity_extraction import (
    QuantityDetection,
    QuantityObservation,
)

from .models import EvaluationStatus


class QuantityStructuralCriterion(str, Enum):
    """Structural aspect checked for an observed quantity."""

    QUANTITY_PRESENT = "quantity_present"
    UNIT_PRESENT = "unit_present"
    UNCERTAINTY_PRESENT = "uncertainty_present"
    UNCERTAINTY_JUSTIFICATION_PRESENT = "uncertainty_justification_present"


_CRITERION_ORDER = (
    QuantityStructuralCriterion.QUANTITY_PRESENT,
    QuantityStructuralCriterion.UNIT_PRESENT,
    QuantityStructuralCriterion.UNCERTAINTY_PRESENT,
    QuantityStructuralCriterion.UNCERTAINTY_JUSTIFICATION_PRESENT,
)


@dataclass(frozen=True, slots=True)
class QuantityCriterionEvaluation:
    """Immutable result of one quantity structural check."""

    criterion: QuantityStructuralCriterion
    requirement: PresenceRequirement
    status: EvaluationStatus
    observation: QuantityObservation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.criterion, QuantityStructuralCriterion):
            raise TypeError("Le critère doit être un QuantityStructuralCriterion.")
        if not isinstance(self.requirement, PresenceRequirement):
            raise TypeError("L'exigence doit être une PresenceRequirement.")
        if not isinstance(self.status, EvaluationStatus):
            raise TypeError("Le statut doit être un EvaluationStatus.")
        if self.observation is not None and not isinstance(
            self.observation, QuantityObservation
        ):
            raise TypeError("L'observation doit être une QuantityObservation.")

        if self.criterion is QuantityStructuralCriterion.QUANTITY_PRESENT:
            self._validate_quantity_presence()
        elif self.criterion in (
            QuantityStructuralCriterion.UNIT_PRESENT,
            QuantityStructuralCriterion.UNCERTAINTY_PRESENT,
        ):
            self._validate_component_presence()
        else:
            self._validate_justification_presence()

    def _validate_quantity_presence(self) -> None:
        if self.requirement is PresenceRequirement.IGNORE:
            raise ValueError("La présence de la quantité ne peut pas être ignorée.")
        if self.status in (
            EvaluationStatus.NOT_APPLICABLE,
            EvaluationStatus.DEFERRED,
        ):
            raise ValueError("Statut incohérent pour la présence de la quantité.")
        if self.observation is not None:
            if self.status is not EvaluationStatus.SATISFIED:
                raise ValueError("Une quantité observée satisfait sa présence.")
            return
        expected_status = (
            EvaluationStatus.UNSATISFIED
            if self.requirement is PresenceRequirement.REQUIRED
            else EvaluationStatus.SATISFIED
        )
        if self.status is not expected_status:
            raise ValueError("Statut incohérent pour une quantité absente.")

    def _validate_component_presence(self) -> None:
        if self.status is EvaluationStatus.DEFERRED:
            raise ValueError("Un contrôle structurel observable ne peut être différé.")
        if self.requirement is PresenceRequirement.IGNORE or self.observation is None:
            if (
                self.status is not EvaluationStatus.NOT_APPLICABLE
                or self.observation is not None
            ):
                raise ValueError("Un contrôle non applicable ne porte aucune preuve.")
            return
        if self.requirement is PresenceRequirement.OPTIONAL:
            if self.status is not EvaluationStatus.SATISFIED:
                raise ValueError("Un élément optionnel est structurellement satisfait.")
            return
        expected_status = (
            EvaluationStatus.SATISFIED
            if self.observed
            else EvaluationStatus.UNSATISFIED
        )
        if self.status is not expected_status:
            raise ValueError("Le statut ne correspond pas à l'élément observé.")

    def _validate_justification_presence(self) -> None:
        if self.observation is not None:
            raise ValueError("Aucune observation de justification n'existe en A68d.")
        if self.requirement is PresenceRequirement.IGNORE:
            if self.status is not EvaluationStatus.NOT_APPLICABLE:
                raise ValueError("Une justification ignorée n'est pas applicable.")
        elif self.status not in (
            EvaluationStatus.NOT_APPLICABLE,
            EvaluationStatus.DEFERRED,
        ):
            raise ValueError("Une justification est non applicable ou différée.")

    @property
    def observed(self) -> bool | None:
        """Observed presence, or ``None`` when A68d cannot observe it."""

        if self.criterion is QuantityStructuralCriterion.QUANTITY_PRESENT:
            return self.observation is not None
        if self.criterion is QuantityStructuralCriterion.UNIT_PRESENT:
            return (
                self.observation.unit is not None
                if self.observation is not None
                else None
            )
        if self.criterion is QuantityStructuralCriterion.UNCERTAINTY_PRESENT:
            return (
                self.observation.uncertainty is not None
                if self.observation is not None
                else None
            )
        return None


def _component_evaluation(
    criterion: QuantityStructuralCriterion,
    requirement: PresenceRequirement,
    observation: QuantityObservation | None,
) -> QuantityCriterionEvaluation:
    if observation is None or requirement is PresenceRequirement.IGNORE:
        return QuantityCriterionEvaluation(
            criterion, requirement, EvaluationStatus.NOT_APPLICABLE
        )
    present = (
        observation.unit is not None
        if criterion is QuantityStructuralCriterion.UNIT_PRESENT
        else observation.uncertainty is not None
    )
    status = (
        EvaluationStatus.SATISFIED
        if requirement is PresenceRequirement.OPTIONAL or present
        else EvaluationStatus.UNSATISFIED
    )
    return QuantityCriterionEvaluation(criterion, requirement, status, observation)


def _expected_criteria(
    *,
    production_required: bool,
    unit_requirement: PresenceRequirement,
    uncertainty_requirement: PresenceRequirement,
    justification_requirement: PresenceRequirement,
    observation: QuantityObservation | None,
) -> tuple[QuantityCriterionEvaluation, ...]:
    quantity_requirement = (
        PresenceRequirement.REQUIRED
        if production_required
        else PresenceRequirement.OPTIONAL
    )
    quantity_status = (
        EvaluationStatus.SATISFIED
        if observation is not None or not production_required
        else EvaluationStatus.UNSATISFIED
    )
    justification_status = (
        EvaluationStatus.NOT_APPLICABLE
        if observation is None
        or justification_requirement is PresenceRequirement.IGNORE
        else EvaluationStatus.DEFERRED
    )
    return (
        QuantityCriterionEvaluation(
            QuantityStructuralCriterion.QUANTITY_PRESENT,
            quantity_requirement,
            quantity_status,
            observation,
        ),
        _component_evaluation(
            QuantityStructuralCriterion.UNIT_PRESENT,
            unit_requirement,
            observation,
        ),
        _component_evaluation(
            QuantityStructuralCriterion.UNCERTAINTY_PRESENT,
            uncertainty_requirement,
            observation,
        ),
        QuantityCriterionEvaluation(
            QuantityStructuralCriterion.UNCERTAINTY_JUSTIFICATION_PRESENT,
            justification_requirement,
            justification_status,
        ),
    )


@dataclass(frozen=True, slots=True)
class QuantityStructuralEvaluation:
    """Complete structural evaluation of one expected quantity."""

    expectation_set: QuantityExpectationSet
    detection: QuantityDetection
    selected_observation: QuantityObservation | None
    criteria: tuple[QuantityCriterionEvaluation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.expectation_set, QuantityExpectationSet):
            raise TypeError("L'attendu doit être un QuantityExpectationSet.")
        if not isinstance(self.detection, QuantityDetection):
            raise TypeError("La détection doit être une QuantityDetection.")
        if self.selected_observation is not None and not isinstance(
            self.selected_observation, QuantityObservation
        ):
            raise TypeError("L'observation sélectionnée doit être valide.")

        expectation = self.expectation_set.get(self.detection.production_id)
        if expectation is None:
            raise ValueError("La production détectée est absente du jeu d'attendus.")
        if self.detection.expectation != expectation:
            raise ValueError("La détection ne correspond pas à l'attendu enregistré.")
        production = self.expectation_set.plan.get(self.detection.production_id)
        if (
            production is None
            or production.kind is not ScientificProductionKind.QUANTITY
        ):
            raise ValueError("La production évaluée doit être de type QUANTITY.")

        if self.detection.observations:
            if self.selected_observation is None:
                raise ValueError("Une observation détectée doit être sélectionnée.")
            if self.selected_observation not in self.detection.observations:
                raise ValueError("L'observation sélectionnée doit provenir de la détection.")
        elif self.selected_observation is not None:
            raise ValueError("Une détection vide ne peut sélectionner d'observation.")
        if any(
            observation.production_id != self.detection.production_id
            for observation in self.detection.observations
        ):
            raise ValueError("Toutes les observations doivent concerner la production.")

        criteria = tuple(self.criteria)
        object.__setattr__(self, "criteria", criteria)
        if any(
            not isinstance(item, QuantityCriterionEvaluation) for item in criteria
        ):
            raise TypeError(
                "Chaque critère doit être une QuantityCriterionEvaluation."
            )
        if tuple(item.criterion for item in criteria) != _CRITERION_ORDER:
            raise ValueError("Les quatre critères doivent être uniques et ordonnés.")
        expected = _expected_criteria(
            production_required=production.required,
            unit_requirement=expectation.unit_requirement,
            uncertainty_requirement=expectation.uncertainty_requirement,
            justification_requirement=(
                expectation.uncertainty_justification_requirement
            ),
            observation=self.selected_observation,
        )
        if criteria != expected:
            raise ValueError("Les critères ne correspondent pas au contexte évalué.")

    def get(
        self, criterion: QuantityStructuralCriterion
    ) -> QuantityCriterionEvaluation | None:
        """Return one criterion evaluation, or ``None`` when unknown."""

        for evaluation in self.criteria:
            if evaluation.criterion is criterion:
                return evaluation
        return None

    @property
    def failures(self) -> tuple[QuantityCriterionEvaluation, ...]:
        return tuple(
            item for item in self.criteria
            if item.status is EvaluationStatus.UNSATISFIED
        )

    @property
    def deferred(self) -> tuple[QuantityCriterionEvaluation, ...]:
        return tuple(
            item for item in self.criteria
            if item.status is EvaluationStatus.DEFERRED
        )

    @property
    def required_deferred(self) -> tuple[QuantityCriterionEvaluation, ...]:
        return tuple(
            item for item in self.deferred
            if item.requirement is PresenceRequirement.REQUIRED
        )

    @property
    def is_complete(self) -> bool:
        return not self.deferred

    @property
    def is_required_complete(self) -> bool:
        return not self.required_deferred

    @property
    def satisfied(self) -> bool:
        return not self.failures and self.is_required_complete


class QuantityStructuralEvaluator:
    """Evaluate structural requirements on one coherent observation."""

    def evaluate(
        self,
        detection: QuantityDetection,
        expectation_set: QuantityExpectationSet,
    ) -> QuantityStructuralEvaluation:
        expectation = expectation_set.get(detection.production_id)
        if expectation is None:
            raise ValueError("La production détectée est absente du jeu d'attendus.")
        if detection.expectation != expectation:
            raise ValueError("La détection ne correspond pas à l'attendu enregistré.")
        production = expectation_set.plan.get(detection.production_id)
        if (
            production is None
            or production.kind is not ScientificProductionKind.QUANTITY
        ):
            raise ValueError("La production évaluée doit être de type QUANTITY.")

        def selection_key(observation: QuantityObservation) -> tuple[int, ...]:
            components = (
                (expectation.unit_requirement, observation.unit is not None),
                (
                    expectation.uncertainty_requirement,
                    observation.uncertainty is not None,
                ),
            )
            required = sum(
                present
                for requirement, present in components
                if requirement is PresenceRequirement.REQUIRED
            )
            optional = sum(
                present
                for requirement, present in components
                if requirement is PresenceRequirement.OPTIONAL
            )
            return (-required, -optional, observation.start, observation.end)

        selected = (
            min(detection.observations, key=selection_key)
            if detection.observations
            else None
        )
        criteria = _expected_criteria(
            production_required=production.required,
            unit_requirement=expectation.unit_requirement,
            uncertainty_requirement=expectation.uncertainty_requirement,
            justification_requirement=(
                expectation.uncertainty_justification_requirement
            ),
            observation=selected,
        )
        return QuantityStructuralEvaluation(
            expectation_set, detection, selected, criteria
        )


def evaluate_quantity_structure(
    detection: QuantityDetection,
    expectation_set: QuantityExpectationSet,
) -> QuantityStructuralEvaluation:
    """Convenience wrapper around :class:`QuantityStructuralEvaluator`."""

    return QuantityStructuralEvaluator().evaluate(detection, expectation_set)
