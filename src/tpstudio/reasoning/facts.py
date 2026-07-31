"""Atomic facts used by the future reasoning engine."""

from __future__ import annotations

from dataclasses import dataclass
from .enums import FactKind
from .evidence import Evidence


@dataclass(frozen=True, slots=True)
class Fact:
    """One immutable, atomic piece of structured information."""

    id: str
    kind: FactKind
    subject: str
    predicate: str
    value: object | None = None
    confidence: float = 1.0
    evidence: Evidence | None = None
    # Temporary read-only bridge for the pre-A63 prototype. These attributes
    # can disappear when Rules and Diagnostics receive their final contracts.
    source: str | None = None
    location: object | None = None

    def __post_init__(self) -> None:
        # Before A63, ``Fact(name, value, source, location)`` was publicly
        # importable. Accept that positional shape without making it the new
        # data model.
        if not isinstance(self.kind, (FactKind, str)):
            legacy_value = self.kind
            legacy_source = self.subject
            legacy_location = self.predicate
            object.__setattr__(self, "kind", FactKind.NUMERIC_VALUE)
            object.__setattr__(self, "subject", self.id)
            object.__setattr__(self, "predicate", "has_value")
            object.__setattr__(self, "value", legacy_value)
            object.__setattr__(self, "source", legacy_source)
            object.__setattr__(self, "location", legacy_location)

        if not self.id:
            raise ValueError("L'identifiant d'un fait ne peut pas être vide.")
        if not isinstance(self.kind, FactKind):
            raise TypeError("Le type d'un fait doit être une valeur de FactKind.")
        if not self.subject:
            raise ValueError("Le sujet d'un fait ne peut pas être vide.")
        if not self.predicate:
            raise ValueError("Le prédicat d'un fait ne peut pas être vide.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("La confiance d'un fait doit être comprise entre 0 et 1.")
