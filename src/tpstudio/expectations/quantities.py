"""Teacher-declared structural expectations for numerical quantities."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from .scientific_productions import (
    ScientificProductionKind,
    ScientificProductionPlan,
)


class PresenceRequirement(str, Enum):
    """Future presence-checking policy for one quantity component."""

    IGNORE = "ignore"
    OPTIONAL = "optional"
    REQUIRED = "required"


def _require_non_blank(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"Le champ {field_name!r} ne peut pas être vide.")


@dataclass(frozen=True, slots=True)
class ExpectedQuantity:
    """Literal structure expected for a future student quantity result."""

    production_id: str
    canonical_symbol: str
    accepted_symbols: tuple[str, ...] = ()
    canonical_unit: str | None = None
    accepted_units: tuple[str, ...] = ()
    unit_requirement: PresenceRequirement = PresenceRequirement.REQUIRED
    uncertainty_requirement: PresenceRequirement = PresenceRequirement.OPTIONAL
    uncertainty_justification_requirement: PresenceRequirement = (
        PresenceRequirement.IGNORE
    )
    description: str = ""

    def __post_init__(self) -> None:
        _require_non_blank(self.production_id, "production_id")
        _require_non_blank(self.canonical_symbol, "canonical_symbol")

        symbols = tuple(self.accepted_symbols)
        if any(not symbol.strip() for symbol in symbols):
            raise ValueError("Un symbole accepté ne peut pas être vide.")
        object.__setattr__(self, "accepted_symbols", tuple(dict.fromkeys(symbols)))

        if self.canonical_unit is not None:
            _require_non_blank(self.canonical_unit, "canonical_unit")
        units = tuple(self.accepted_units)
        if any(not unit.strip() for unit in units):
            raise ValueError("Une unité acceptée ne peut pas être vide.")
        object.__setattr__(self, "accepted_units", tuple(dict.fromkeys(units)))

        requirements = (
            self.unit_requirement,
            self.uncertainty_requirement,
            self.uncertainty_justification_requirement,
        )
        if any(
            not isinstance(requirement, PresenceRequirement)
            for requirement in requirements
        ):
            raise TypeError(
                "Chaque exigence de présence doit être une PresenceRequirement."
            )

        if (
            self.unit_requirement is PresenceRequirement.REQUIRED
            and self.canonical_unit is None
        ):
            raise ValueError("Une unité obligatoire requiert une unité canonique.")
        if self.accepted_units and self.canonical_unit is None:
            raise ValueError(
                "Des unités acceptées requièrent une unité canonique."
            )
        if (
            self.uncertainty_justification_requirement
            is PresenceRequirement.REQUIRED
            and self.uncertainty_requirement is not PresenceRequirement.REQUIRED
        ):
            raise ValueError(
                "Une justification obligatoire requiert une incertitude obligatoire."
            )
        if (
            self.uncertainty_justification_requirement
            is PresenceRequirement.OPTIONAL
            and self.uncertainty_requirement is PresenceRequirement.IGNORE
        ):
            raise ValueError(
                "Une justification optionnelle requiert une incertitude contrôlée."
            )

    @property
    def symbols(self) -> tuple[str, ...]:
        """Canonical symbol followed by exact declared variants."""

        return tuple(dict.fromkeys((self.canonical_symbol, *self.accepted_symbols)))

    @property
    def units(self) -> tuple[str, ...]:
        """Canonical unit, when present, followed by exact variants."""

        if self.canonical_unit is None:
            return ()
        return tuple(dict.fromkeys((self.canonical_unit, *self.accepted_units)))


@dataclass(frozen=True, slots=True)
class QuantityExpectationSet:
    """Detailed quantity specifications explicitly attached to one plan."""

    plan: ScientificProductionPlan
    quantities: tuple[ExpectedQuantity, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.plan, ScientificProductionPlan):
            raise TypeError("Le plan doit être un ScientificProductionPlan.")
        quantities = tuple(self.quantities)
        if not quantities:
            raise ValueError("Un jeu d'attendus de quantités ne peut pas être vide.")
        if any(not isinstance(quantity, ExpectedQuantity) for quantity in quantities):
            raise TypeError("Chaque attendu doit être une ExpectedQuantity.")
        object.__setattr__(self, "quantities", quantities)

        production_ids = [quantity.production_id for quantity in quantities]
        if len(production_ids) != len(set(production_ids)):
            raise ValueError(
                "Les identifiants des productions quantitatives doivent être uniques."
            )

        for quantity in quantities:
            production = self.plan.get(quantity.production_id)
            if production is None:
                raise ValueError(
                    f"Production inconnue pour la quantité : "
                    f"{quantity.production_id!r}."
                )
            if production.kind is not ScientificProductionKind.QUANTITY:
                raise ValueError(
                    "Un ExpectedQuantity doit cibler une production de type QUANTITY."
                )

    def __iter__(self) -> Iterator[ExpectedQuantity]:
        return iter(self.quantities)

    def __len__(self) -> int:
        return len(self.quantities)

    def get(self, production_id: str) -> ExpectedQuantity | None:
        for quantity in self.quantities:
            if quantity.production_id == production_id:
                return quantity
        return None

    @property
    def in_evaluation_order(self) -> tuple[ExpectedQuantity, ...]:
        """Quantity specifications ordered by their generic plan."""

        by_production_id = {
            quantity.production_id: quantity for quantity in self.quantities
        }
        return tuple(
            by_production_id[production.id]
            for production in self.plan.evaluation_order
            if production.id in by_production_id
        )
