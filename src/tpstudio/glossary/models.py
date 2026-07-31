"""Data contracts for scientific glossaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TermCategory = Literal[
    "phenomenon",
    "quantity",
    "instrument",
    "method",
    "unit",
]


@dataclass(frozen=True, slots=True)
class ScientificTerm:
    """One canonical scientific concept and its textual variants."""

    id: str
    label: str
    category: TermCategory
    aliases: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    tp_tags: tuple[str, ...] = ()
    related_terms: tuple[str, ...] = ()
    expected_units: tuple[str, ...] = ()
    description: str = ""
    diagnostic_groups: tuple[str, ...] = ()

    @property
    def spellings(self) -> tuple[str, ...]:
        """Canonical label and aliases, preserving their declaration order."""

        return (self.label, *self.aliases)


@dataclass(frozen=True, slots=True)
class Glossary:
    """A named collection of scientific terms."""

    id: str
    title: str
    terms: tuple[ScientificTerm, ...]

    def __post_init__(self) -> None:
        term_ids = [term.id for term in self.terms]
        if len(term_ids) != len(set(term_ids)):
            raise ValueError("Les identifiants des termes d’un glossaire doivent être uniques.")

    def term_by_id(self, term_id: str) -> ScientificTerm | None:
        for term in self.terms:
            if term.id == term_id:
                return term
        return None


@dataclass(frozen=True, slots=True)
class TermMatch:
    """A term occurrence in the original text."""

    term: ScientificTerm
    matched_text: str
    start: int
    end: int
    source: str
