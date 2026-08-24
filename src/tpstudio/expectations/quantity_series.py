"""Teacher-declared expectations for ordered numeric quantity series."""

from __future__ import annotations

from dataclasses import dataclass

from .quantities import PresenceRequirement
from .scientific_productions import ScientificProductionKind, ScientificProductionPlan


@dataclass(frozen=True, slots=True)
class ExpectedQuantitySeries:
    production_id: str
    canonical_symbol: str
    canonical_unit: str | None = None
    expected_length: int | None = None
    uncertainty_requirement: PresenceRequirement = PresenceRequirement.OPTIONAL
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.production_id, str) or not self.production_id.strip():
            raise ValueError("production_id ne peut pas être vide.")
        if not isinstance(self.canonical_symbol, str) or not self.canonical_symbol.strip():
            raise ValueError("canonical_symbol ne peut pas être vide.")
        if self.canonical_unit is not None and (
            not isinstance(self.canonical_unit, str) or not self.canonical_unit.strip()
        ):
            raise ValueError("canonical_unit doit être une chaîne non vide ou None.")
        if self.expected_length is not None and (
            type(self.expected_length) is not int or self.expected_length <= 0
        ):
            raise ValueError("expected_length doit être un entier strictement positif.")
        if not isinstance(self.uncertainty_requirement, PresenceRequirement):
            raise TypeError("La politique d'incertitude est invalide.")
        if not isinstance(self.description, str):
            raise TypeError("La description doit être une chaîne.")


@dataclass(frozen=True, slots=True)
class QuantitySeriesExpectationSet:
    production_plan: ScientificProductionPlan
    expectations: tuple[ExpectedQuantitySeries, ...] = ()

    def __post_init__(self) -> None:
        if type(self.production_plan) is not ScientificProductionPlan:
            raise TypeError("Le plan scientifique est invalide.")
        expectations = tuple(self.expectations)
        if any(type(item) is not ExpectedQuantitySeries for item in expectations):
            raise TypeError("Chaque attente doit être une ExpectedQuantitySeries.")
        ids = tuple(item.production_id for item in expectations)
        if len(ids) != len(set(ids)):
            raise ValueError("Les productions série doivent être uniques.")
        for item in expectations:
            production = self.production_plan.get(item.production_id)
            if production is None or production.kind is not ScientificProductionKind.QUANTITY:
                raise ValueError("Une série doit cibler une production QUANTITY connue.")
        object.__setattr__(self, "expectations", expectations)

    def __iter__(self):
        return iter(self.expectations)

    def __len__(self) -> int:
        return len(self.expectations)

    def get(self, production_id: str) -> ExpectedQuantitySeries | None:
        return next((item for item in self.expectations if item.production_id == production_id), None)
