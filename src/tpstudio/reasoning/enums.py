"""Enumerations shared by the reasoning data model."""

from __future__ import annotations

from enum import Enum


class FactKind(str, Enum):
    """Broad kinds of atomic information understood by TPStudio."""

    CONCEPT_MENTION = "concept_mention"
    NUMERIC_VALUE = "numeric_value"
    RELATION = "relation"
    NEGATION = "negation"
