"""A small collection abstraction for facts."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .enums import FactKind
from .facts import Fact


class FactSet:
    """An insertion-ordered collection whose fact identifiers are unique."""

    def __init__(self, facts: Iterable[Fact] = ()) -> None:
        self._facts: dict[str, Fact] = {}
        for fact in facts:
            self.add(fact)

    def add(self, fact: Fact) -> None:
        """Add a fact.

        Adding the exact same fact again is idempotent. Reusing an identifier
        for different information is rejected because identifiers are the
        stable handles used by future rules and diagnostics.
        """

        existing = self._facts.get(fact.id)
        if existing is None:
            self._facts[fact.id] = fact
        elif existing != fact:
            raise ValueError(f"L'identifiant de fait {fact.id!r} est déjà utilisé.")

    def __iter__(self) -> Iterator[Fact]:
        return iter(self._facts.values())

    def __len__(self) -> int:
        return len(self._facts)

    def __bool__(self) -> bool:
        return bool(self._facts)

    def filter(
        self,
        *,
        kind: FactKind | None = None,
        subject: str | None = None,
    ) -> FactSet:
        """Return facts matching every supplied criterion."""

        return FactSet(
            fact
            for fact in self
            if (kind is None or fact.kind is kind)
            and (subject is None or fact.subject == subject)
        )

    def by_kind(self, kind: FactKind) -> FactSet:
        """Return all facts of ``kind``."""

        return self.filter(kind=kind)

    def by_subject(self, subject: str) -> FactSet:
        """Return all facts whose subject equals ``subject``."""

        return self.filter(subject=subject)

    find_by_kind = by_kind
    find_by_subject = by_subject
