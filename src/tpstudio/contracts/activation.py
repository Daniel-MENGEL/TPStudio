"""Explicit, provenance-preserving activation of validated candidates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tpstudio.expectations import (
    ExpectedQuantity,
    PresenceRequirement,
    ScientificProductionKind,
)

from .candidate import CandidateKind, CandidateScientificContract
from .mapping import CandidateProductionMatch, ValidationState


class ActivationStatus(str, Enum):
    """Outcome of an explicit candidate-to-expectation activation request."""

    ACTIVATED = "activated"
    NOT_ACCEPTED = "not_accepted"
    INSUFFICIENT_INFORMATION = "insufficient_information"


@dataclass(frozen=True, slots=True)
class ActivatedCandidateExpectation:
    """An active expectation with the decision and TeX provenance retained."""

    status: ActivationStatus
    candidate_id: str
    production_id: str
    validation_state: ValidationState
    expectation: ExpectedQuantity | None
    source_document: str
    source_location: tuple[int, int]
    source_text: str
    reason: str


def activate_validated_candidate_quantity(
    match: CandidateProductionMatch,
    candidate_contract: CandidateScientificContract,
    production_plan,
) -> ActivatedCandidateExpectation:
    """Build one quantity expectation only after explicit acceptance.

    This helper is intentionally non-mutating: callers may later place the
    returned ``ExpectedQuantity`` in a validated ``QuantityExpectationSet``.
    It never invents a reference value, unit, formula, or uncertainty policy.
    """

    if not isinstance(match, CandidateProductionMatch):
        raise TypeError("match doit être un CandidateProductionMatch.")
    if not isinstance(candidate_contract, CandidateScientificContract):
        raise TypeError("candidate_contract doit être un CandidateScientificContract.")
    candidate = next(
        (item for item in candidate_contract.items if item.candidate_id == match.candidate_id),
        None,
    )
    if candidate is None:
        raise ValueError(f"Candidat inconnu : {match.candidate_id!r}.")
    production = production_plan.get(match.production_id)
    if production is None:
        raise ValueError(f"Production inconnue : {match.production_id!r}.")

    provenance = dict(
        candidate_id=candidate.candidate_id,
        production_id=match.production_id,
        validation_state=match.validation_state,
        source_document=candidate.source_document,
        source_location=candidate.source_location,
        source_text=candidate.source_text,
    )
    if match.validation_state is not ValidationState.ACCEPTED:
        return ActivatedCandidateExpectation(
            status=ActivationStatus.NOT_ACCEPTED,
            expectation=None,
            reason="Une proposition doit être explicitement ACCEPTED par le professeur.",
            **provenance,
        )
    if candidate.kind is not CandidateKind.QUANTITY:
        return ActivatedCandidateExpectation(
            status=ActivationStatus.INSUFFICIENT_INFORMATION,
            expectation=None,
            reason="Seules les quantités candidates sont activables par cet adaptateur.",
            **provenance,
        )
    if production.kind is not ScientificProductionKind.QUANTITY:
        return ActivatedCandidateExpectation(
            status=ActivationStatus.INSUFFICIENT_INFORMATION,
            expectation=None,
            reason="La production cible n'est pas une QUANTITY.",
            **provenance,
        )
    if not candidate.scientific_symbol:
        return ActivatedCandidateExpectation(
            status=ActivationStatus.INSUFFICIENT_INFORMATION,
            expectation=None,
            reason="Le candidat ne fournit aucun symbole scientifique exploitable.",
            **provenance,
        )

    expectation = ExpectedQuantity(
        production_id=match.production_id,
        canonical_symbol=candidate.scientific_symbol,
        unit_requirement=PresenceRequirement.OPTIONAL,
        uncertainty_requirement=PresenceRequirement.IGNORE,
        description=(
            "Attente minimale activée depuis une proposition TeX acceptée; "
            "aucune valeur de référence ni formule dérivée n'est inventée."
        ),
    )
    return ActivatedCandidateExpectation(
        status=ActivationStatus.ACTIVATED,
        expectation=expectation,
        reason="Proposition explicitement ACCEPTED; attente quantitative minimale créée.",
        **provenance,
    )
