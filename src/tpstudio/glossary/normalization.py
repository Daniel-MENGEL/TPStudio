"""Shared, accent-insensitive normalization for scientific text matching."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True, slots=True)
class NormalizedScientificText:
    """Normalized text together with offsets into its original source."""

    text: str
    starts: tuple[int, ...]
    ends: tuple[int, ...]

    def original_span(self, start: int, end: int) -> tuple[int, int]:
        """Map a non-empty normalized half-open span to the original text."""

        if start < 0 or end <= start or end > len(self.text):
            raise ValueError("La plage normalisée doit être non vide et valide.")
        return self.starts[start], self.ends[end - 1]


def normalize_scientific_text_with_offsets(text: str) -> NormalizedScientificText:
    """Normalize text while retaining exact source spans for every character.

    Matching is case- and accent-insensitive, ``œ`` is expanded to ``oe``, and
    whitespace runs are collapsed. Leading and trailing whitespace is omitted.
    Each resulting character retains the half-open span that produced it in the
    original string.
    """

    characters: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    pending_whitespace: tuple[int, int] | None = None

    for index, character in enumerate(text):
        if character.isspace():
            if characters:
                if pending_whitespace is None:
                    pending_whitespace = (index, index + 1)
                else:
                    pending_whitespace = (pending_whitespace[0], index + 1)
            continue

        transformed = character.casefold().replace("œ", "oe")
        transformed = "".join(
            part
            for part in unicodedata.normalize("NFD", transformed)
            if unicodedata.category(part) != "Mn"
        )
        if not transformed:
            continue

        if pending_whitespace is not None:
            characters.append(" ")
            starts.append(pending_whitespace[0])
            ends.append(pending_whitespace[1])
            pending_whitespace = None

        for part in transformed:
            characters.append(part)
            starts.append(index)
            ends.append(index + 1)

    return NormalizedScientificText(
        text="".join(characters),
        starts=tuple(starts),
        ends=tuple(ends),
    )


def normalize_scientific_text(text: str) -> str:
    """Return the comparison form used by the scientific matcher."""

    return normalize_scientific_text_with_offsets(text).text
