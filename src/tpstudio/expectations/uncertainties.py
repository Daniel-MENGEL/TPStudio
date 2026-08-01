"""Teacher-declared presentation policies for quantity uncertainties."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .quantities import PresenceRequirement, QuantityExpectationSet


@dataclass(frozen=True, slots=True)
class UncertaintyQualitySpec:
    """Presentation checks requested for one quantity uncertainty."""

    production_id: str
    require_strictly_positive: bool = True
    allowed_significant_digits: tuple[int, ...] | None = (1, 2)
    require_matching_decimal_place: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        if not self.production_id.strip():
            raise ValueError("L'identifiant de production ne peut pas être vide.")
        if type(self.require_strictly_positive) is not bool:
            raise TypeError("Le contrôle de positivité doit être un booléen.")
        if type(self.require_matching_decimal_place) is not bool:
            raise TypeError("Le contrôle du rang décimal doit être un booléen.")

        if self.allowed_significant_digits is not None:
            digits = tuple(self.allowed_significant_digits)
            if not digits:
                raise ValueError(
                    "Les chiffres significatifs autorisés ne peuvent pas être vides."
                )
            if any(type(value) is not int for value in digits):
                raise TypeError(
                    "Chaque nombre de chiffres significatifs doit être un entier."
                )
            if any(value <= 0 for value in digits):
                raise ValueError(
                    "Un nombre de chiffres significatifs doit être strictement positif."
                )
            object.__setattr__(
                self, "allowed_significant_digits", tuple(dict.fromkeys(digits))
            )

        if not (
            self.require_strictly_positive
            or self.allowed_significant_digits is not None
            or self.require_matching_decimal_place
        ):
            raise ValueError("Au moins un contrôle d'incertitude doit être actif.")


@dataclass(frozen=True, slots=True)
class UncertaintyQualityExpectationSet:
    """Uncertainty policies attached to detailed quantity expectations."""

    quantity_expectation_set: QuantityExpectationSet
    specifications: tuple[UncertaintyQualitySpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.quantity_expectation_set, QuantityExpectationSet):
            raise TypeError("Les quantités doivent former un QuantityExpectationSet.")
        specifications = tuple(self.specifications)
        if not specifications:
            raise ValueError("Un jeu de politiques d'incertitude ne peut pas être vide.")
        if any(
            not isinstance(specification, UncertaintyQualitySpec)
            for specification in specifications
        ):
            raise TypeError("Chaque politique doit être une UncertaintyQualitySpec.")
        object.__setattr__(self, "specifications", specifications)

        production_ids = [item.production_id for item in specifications]
        if len(production_ids) != len(set(production_ids)):
            raise ValueError("Les identifiants des politiques doivent être uniques.")

        for specification in specifications:
            quantity = self.quantity_expectation_set.get(
                specification.production_id
            )
            if quantity is None:
                raise ValueError(
                    "La politique cible une quantité attendue inconnue : "
                    f"{specification.production_id!r}."
                )
            if quantity.uncertainty_requirement is PresenceRequirement.IGNORE:
                raise ValueError(
                    "Une incertitude ignorée ne peut recevoir de politique qualité."
                )

    def __iter__(self) -> Iterator[UncertaintyQualitySpec]:
        return iter(self.specifications)

    def __len__(self) -> int:
        return len(self.specifications)

    def get(self, production_id: str) -> UncertaintyQualitySpec | None:
        for specification in self.specifications:
            if specification.production_id == production_id:
                return specification
        return None

    @property
    def in_evaluation_order(self) -> tuple[UncertaintyQualitySpec, ...]:
        """Policies ordered by the underlying scientific production plan."""

        by_production_id = {
            specification.production_id: specification
            for specification in self.specifications
        }
        return tuple(
            by_production_id[production.id]
            for production in self.quantity_expectation_set.plan.evaluation_order
            if production.id in by_production_id
        )
