"""Deterministic matching of glossary terms in student text."""

from __future__ import annotations

import re

from .models import Glossary, TermCategory, TermMatch
from .normalization import (
    normalize_scientific_text,
    normalize_scientific_text_with_offsets,
)


def match_terms(text: str, glossary: Glossary) -> list[TermMatch]:
    """Return one non-overlapping match per term, in source-text order.

    Matching is case- and accent-insensitive and uses word boundaries. The
    public ``start`` and ``end`` positions always refer to the original text,
    including when normalization collapses whitespace or expands ``œ``.
    """

    normalized_source = normalize_scientific_text_with_offsets(text)
    candidates: list[TermMatch] = []

    for term in glossary.terms:
        for spelling in term.spellings:
            normalized_spelling = normalize_scientific_text(spelling)
            if not normalized_spelling:
                continue

            pattern = re.compile(
                rf"(?<!\w){re.escape(normalized_spelling)}(?!\w)"
            )
            for occurrence in pattern.finditer(normalized_source.text):
                start, end = normalized_source.original_span(
                    occurrence.start(), occurrence.end()
                )
                candidates.append(
                    TermMatch(
                        term=term,
                        matched_text=text[start:end],
                        start=start,
                        end=end,
                        source=spelling,
                    )
                )

    # A longer spelling takes precedence when aliases overlap. A term is only
    # reported once because the diagnostic question is term presence, not term
    # frequency.
    candidates.sort(key=lambda match: (match.start, -(match.end - match.start)))
    accepted: list[TermMatch] = []
    seen_terms: set[str] = set()
    occupied_ranges: list[tuple[int, int]] = []

    for candidate in candidates:
        if candidate.term.id in seen_terms:
            continue
        if any(
            candidate.start < end and start < candidate.end
            for start, end in occupied_ranges
        ):
            continue
        accepted.append(candidate)
        seen_terms.add(candidate.term.id)
        occupied_ranges.append((candidate.start, candidate.end))

    return accepted


def matched_term_ids(text: str, glossary: Glossary) -> set[str]:
    return {match.term.id for match in match_terms(text, glossary)}


def matched_categories(text: str, glossary: Glossary) -> set[TermCategory]:
    return {match.term.category for match in match_terms(text, glossary)}


def has_scientific_vocabulary(text: str, glossary: Glossary) -> bool:
    return bool(match_terms(text, glossary))
