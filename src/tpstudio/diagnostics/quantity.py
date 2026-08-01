"""Structured diagnostics derived from quantity evaluations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from tpstudio.evaluation import (
    EvaluationStatus,
    QuantityStructuralCriterion,
    QuantityStructuralEvaluation,
    QuantityUncertaintyEvaluation,
    UncertaintyQualityCriterion,
)
from tpstudio.expectations import PresenceRequirement
from tpstudio.reasoning.quantity_extraction import QuantityObservation


class QuantityDiagnosticSource(str, Enum):
    """Evaluation family from which a quantity diagnostic originates."""

    STRUCTURE = "structure"
    UNCERTAINTY_QUALITY = "uncertainty_quality"


class QuantityDiagnosticCode(str, Enum):
    """Stable identifier of a structured quantity diagnostic."""

    QUANTITY_MISSING = "quantity_missing"
    UNIT_MISSING = "unit_missing"
    UNCERTAINTY_MISSING = "uncertainty_missing"
    UNCERTAINTY_JUSTIFICATION_DEFERRED = (
        "uncertainty_justification_deferred"
    )
    UNCERTAINTY_NOT_STRICTLY_POSITIVE = "uncertainty_not_strictly_positive"
    UNCERTAINTY_SIGNIFICANT_DIGITS_INVALID = (
        "uncertainty_significant_digits_invalid"
    )
    UNCERTAINTY_DECIMAL_PLACE_MISMATCH = (
        "uncertainty_decimal_place_mismatch"
    )

    @property
    def source(self) -> QuantityDiagnosticSource:
        return _definition_for(self).source

    @property
    def criterion(
        self,
    ) -> QuantityStructuralCriterion | UncertaintyQualityCriterion:
        return _definition_for(self).criterion

    @property
    def status(self) -> EvaluationStatus:
        return _definition_for(self).status

    @property
    def message_key(self) -> str:
        return _definition_for(self).message_key


@dataclass(frozen=True, slots=True)
class _QuantityDiagnosticDefinition:
    code: QuantityDiagnosticCode
    source: QuantityDiagnosticSource
    criterion: QuantityStructuralCriterion | UncertaintyQualityCriterion
    status: EvaluationStatus
    message_key: str


_DIAGNOSTIC_DEFINITIONS = (
    _QuantityDiagnosticDefinition(
        QuantityDiagnosticCode.QUANTITY_MISSING,
        QuantityDiagnosticSource.STRUCTURE,
        QuantityStructuralCriterion.QUANTITY_PRESENT,
        EvaluationStatus.UNSATISFIED,
        "diagnostic.quantity.missing",
    ),
    _QuantityDiagnosticDefinition(
        QuantityDiagnosticCode.UNIT_MISSING,
        QuantityDiagnosticSource.STRUCTURE,
        QuantityStructuralCriterion.UNIT_PRESENT,
        EvaluationStatus.UNSATISFIED,
        "diagnostic.quantity.unit_missing",
    ),
    _QuantityDiagnosticDefinition(
        QuantityDiagnosticCode.UNCERTAINTY_MISSING,
        QuantityDiagnosticSource.STRUCTURE,
        QuantityStructuralCriterion.UNCERTAINTY_PRESENT,
        EvaluationStatus.UNSATISFIED,
        "diagnostic.quantity.uncertainty_missing",
    ),
    _QuantityDiagnosticDefinition(
        QuantityDiagnosticCode.UNCERTAINTY_JUSTIFICATION_DEFERRED,
        QuantityDiagnosticSource.STRUCTURE,
        QuantityStructuralCriterion.UNCERTAINTY_JUSTIFICATION_PRESENT,
        EvaluationStatus.DEFERRED,
        "diagnostic.quantity.uncertainty_justification_deferred",
    ),
    _QuantityDiagnosticDefinition(
        QuantityDiagnosticCode.UNCERTAINTY_NOT_STRICTLY_POSITIVE,
        QuantityDiagnosticSource.UNCERTAINTY_QUALITY,
        UncertaintyQualityCriterion.STRICTLY_POSITIVE,
        EvaluationStatus.UNSATISFIED,
        "diagnostic.quantity.uncertainty_not_strictly_positive",
    ),
    _QuantityDiagnosticDefinition(
        QuantityDiagnosticCode.UNCERTAINTY_SIGNIFICANT_DIGITS_INVALID,
        QuantityDiagnosticSource.UNCERTAINTY_QUALITY,
        UncertaintyQualityCriterion.SIGNIFICANT_DIGITS,
        EvaluationStatus.UNSATISFIED,
        "diagnostic.quantity.uncertainty_significant_digits_invalid",
    ),
    _QuantityDiagnosticDefinition(
        QuantityDiagnosticCode.UNCERTAINTY_DECIMAL_PLACE_MISMATCH,
        QuantityDiagnosticSource.UNCERTAINTY_QUALITY,
        UncertaintyQualityCriterion.DECIMAL_PLACE_ALIGNMENT,
        EvaluationStatus.UNSATISFIED,
        "diagnostic.quantity.uncertainty_decimal_place_mismatch",
    ),
)


def _definition_for(code: QuantityDiagnosticCode) -> _QuantityDiagnosticDefinition:
    return next(item for item in _DIAGNOSTIC_DEFINITIONS if item.code is code)


def _code_for(
    source: QuantityDiagnosticSource,
    criterion: QuantityStructuralCriterion | UncertaintyQualityCriterion,
    status: EvaluationStatus,
) -> QuantityDiagnosticCode:
    definition = next(
        (
            item
            for item in _DIAGNOSTIC_DEFINITIONS
            if item.source is source
            and item.criterion is criterion
            and item.status is status
        ),
        None,
    )
    if definition is None:
        raise ValueError("Aucun diagnostic ne correspond au résultat évalué.")
    return definition.code


@dataclass(frozen=True, slots=True)
class QuantityDiagnostic:
    """One stable diagnostic derived from quantity evaluation results."""

    code: QuantityDiagnosticCode
    production_id: str
    observation: QuantityObservation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, QuantityDiagnosticCode):
            raise TypeError("Le code doit être un QuantityDiagnosticCode.")
        if not self.production_id.strip():
            raise ValueError("L'identifiant de production ne peut pas être vide.")
        if self.observation is not None and not isinstance(
            self.observation, QuantityObservation
        ):
            raise TypeError("L'observation doit être une QuantityObservation.")
        if (
            self.observation is not None
            and self.observation.production_id != self.production_id
        ):
            raise ValueError("L'observation doit concerner la même production.")
        if self.code is QuantityDiagnosticCode.QUANTITY_MISSING:
            if self.observation is not None:
                raise ValueError("Une quantité absente ne possède aucune observation.")
        elif self.observation is None:
            raise ValueError("Ce diagnostic requiert l'observation sélectionnée.")

    @property
    def source(self) -> QuantityDiagnosticSource:
        return self.code.source

    @property
    def criterion(
        self,
    ) -> QuantityStructuralCriterion | UncertaintyQualityCriterion:
        return self.code.criterion

    @property
    def status(self) -> EvaluationStatus:
        return self.code.status

    @property
    def message_key(self) -> str:
        return self.code.message_key


def _derive_diagnostics(
    structural_evaluation: QuantityStructuralEvaluation,
    uncertainty_evaluation: QuantityUncertaintyEvaluation | None,
) -> tuple[QuantityDiagnostic, ...]:
    if not isinstance(structural_evaluation, QuantityStructuralEvaluation):
        raise TypeError("L'évaluation structurelle doit être valide.")
    if uncertainty_evaluation is not None and not isinstance(
        uncertainty_evaluation, QuantityUncertaintyEvaluation
    ):
        raise TypeError("L'évaluation d'incertitude doit être valide ou absente.")
    if (
        uncertainty_evaluation is not None
        and uncertainty_evaluation.structural_evaluation is not structural_evaluation
    ):
        raise ValueError("L'évaluation A68e doit réutiliser la même instance A68d.")

    production_id = structural_evaluation.detection.production_id
    observation = structural_evaluation.selected_observation
    diagnostics: list[QuantityDiagnostic] = []

    for failure in structural_evaluation.failures:
        code = _code_for(
            QuantityDiagnosticSource.STRUCTURE,
            failure.criterion,
            failure.status,
        )
        diagnostics.append(QuantityDiagnostic(code, production_id, observation))

    if uncertainty_evaluation is not None:
        for failure in uncertainty_evaluation.failures:
            code = _code_for(
                QuantityDiagnosticSource.UNCERTAINTY_QUALITY,
                failure.criterion,
                failure.status,
            )
            diagnostics.append(QuantityDiagnostic(code, production_id, observation))

    for deferred in structural_evaluation.required_deferred:
        if (
            deferred.criterion
            is QuantityStructuralCriterion.UNCERTAINTY_JUSTIFICATION_PRESENT
            and deferred.requirement is PresenceRequirement.REQUIRED
        ):
            code = _code_for(
                QuantityDiagnosticSource.STRUCTURE,
                deferred.criterion,
                deferred.status,
            )
            diagnostics.append(
                QuantityDiagnostic(code, production_id, observation)
            )

    return tuple(diagnostics)


@dataclass(frozen=True, slots=True)
class QuantityDiagnosticSet:
    """Immutable diagnostics and the evaluations from which they derive."""

    structural_evaluation: QuantityStructuralEvaluation
    uncertainty_evaluation: QuantityUncertaintyEvaluation | None
    diagnostics: tuple[QuantityDiagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.structural_evaluation, QuantityStructuralEvaluation):
            raise TypeError("L'évaluation structurelle doit être valide.")
        if self.uncertainty_evaluation is not None and not isinstance(
            self.uncertainty_evaluation, QuantityUncertaintyEvaluation
        ):
            raise TypeError("L'évaluation d'incertitude doit être valide ou absente.")
        if (
            self.uncertainty_evaluation is not None
            and self.uncertainty_evaluation.structural_evaluation
            is not self.structural_evaluation
        ):
            raise ValueError("Les évaluations A68d et A68e doivent être identiques.")

        diagnostics = tuple(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        if any(not isinstance(item, QuantityDiagnostic) for item in diagnostics):
            raise TypeError("Chaque élément doit être un QuantityDiagnostic.")
        if len({item.code for item in diagnostics}) != len(diagnostics):
            raise ValueError("Un code de diagnostic ne peut apparaître qu'une fois.")
        if any(item.production_id != self.production_id for item in diagnostics):
            raise ValueError("Tous les diagnostics doivent concerner la production.")
        if any(
            item.observation is not None
            and item.observation is not self.selected_observation
            for item in diagnostics
        ):
            raise ValueError("Seule l'observation sélectionnée par A68d est permise.")
        expected = _derive_diagnostics(
            self.structural_evaluation, self.uncertainty_evaluation
        )
        if diagnostics != expected:
            raise ValueError("Les diagnostics ne correspondent pas aux évaluations.")

    @property
    def production_id(self) -> str:
        return self.structural_evaluation.detection.production_id

    @property
    def selected_observation(self) -> QuantityObservation | None:
        return self.structural_evaluation.selected_observation

    def __iter__(self) -> Iterator[QuantityDiagnostic]:
        return iter(self.diagnostics)

    def __len__(self) -> int:
        return len(self.diagnostics)

    def get(self, code: QuantityDiagnosticCode) -> QuantityDiagnostic | None:
        for diagnostic in self.diagnostics:
            if diagnostic.code is code:
                return diagnostic
        return None

    @property
    def failures(self) -> tuple[QuantityDiagnostic, ...]:
        return tuple(
            item for item in self.diagnostics
            if item.status is EvaluationStatus.UNSATISFIED
        )

    @property
    def deferred(self) -> tuple[QuantityDiagnostic, ...]:
        return tuple(
            item for item in self.diagnostics
            if item.status is EvaluationStatus.DEFERRED
        )

    @property
    def has_failures(self) -> bool:
        return bool(self.failures)

    @property
    def has_deferred(self) -> bool:
        return bool(self.deferred)

    @property
    def is_empty(self) -> bool:
        return not self.diagnostics


class QuantityDiagnosticBuilder:
    """Translate A68d and A68e results into structured diagnostics."""

    def build(
        self,
        structural_evaluation: QuantityStructuralEvaluation,
        uncertainty_evaluation: QuantityUncertaintyEvaluation | None = None,
    ) -> QuantityDiagnosticSet:
        diagnostics = _derive_diagnostics(
            structural_evaluation, uncertainty_evaluation
        )
        return QuantityDiagnosticSet(
            structural_evaluation, uncertainty_evaluation, diagnostics
        )


def build_quantity_diagnostics(
    structural_evaluation: QuantityStructuralEvaluation,
    uncertainty_evaluation: QuantityUncertaintyEvaluation | None = None,
) -> QuantityDiagnosticSet:
    """Convenience wrapper around :class:`QuantityDiagnosticBuilder`."""

    return QuantityDiagnosticBuilder().build(
        structural_evaluation, uncertainty_evaluation
    )
