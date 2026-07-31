"""Traceability information attached to facts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Evidence:
    """The exact source span from which a fact was extracted.

    ``start`` is inclusive and ``end`` is exclusive, following Python's slice
    convention. Both offsets always refer to ``source_text``.
    """

    source_text: str
    start: int
    end: int
    matched_term: str | None = None

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("Le début d'une preuve ne peut pas être négatif.")
        if self.end < self.start:
            raise ValueError("La fin d'une preuve doit suivre son début.")
        if self.end > len(self.source_text):
            raise ValueError("La preuve dépasse la longueur du texte source.")

    @property
    def excerpt(self) -> str:
        """Return the portion of original text supporting the fact."""

        return self.source_text[self.start : self.end]
