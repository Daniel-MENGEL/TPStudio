"""Scientific vocabulary resources and deterministic text matching."""

from .defaults import default_scientific_glossary
from .matcher import (
    has_scientific_vocabulary,
    match_terms,
    matched_categories,
    matched_term_ids,
)
from .models import Glossary, ScientificTerm, TermCategory, TermMatch
from .registry import GlossaryRegistry

__all__ = [
    "Glossary",
    "GlossaryRegistry",
    "ScientificTerm",
    "TermCategory",
    "TermMatch",
    "default_scientific_glossary",
    "has_scientific_vocabulary",
    "match_terms",
    "matched_categories",
    "matched_term_ids",
]
