"""Immutable storage for teacher expectation sets."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .models import ExpectationSet


@dataclass(frozen=True, slots=True)
class ExpectationRegistry:
    """An ordered registry with one expectation set per identifier."""

    expectation_sets: tuple[ExpectationSet, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "expectation_sets", tuple(self.expectation_sets))
        identifiers = [item.id for item in self.expectation_sets]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(
                "Les identifiants des jeux d'attendus doivent être uniques."
            )

    def __iter__(self) -> Iterator[ExpectationSet]:
        return iter(self.expectation_sets)

    def __len__(self) -> int:
        return len(self.expectation_sets)

    def get(self, expectation_set_id: str) -> ExpectationSet | None:
        for expectation_set in self.expectation_sets:
            if expectation_set.id == expectation_set_id:
                return expectation_set
        return None

    expectation_set_by_id = get
