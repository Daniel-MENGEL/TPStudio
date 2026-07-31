"""Structured facts and deterministic extraction for TPStudio."""

from .conditions import (
    AllOf,
    And,
    AnyOf,
    Condition,
    ConditionResult,
    FactAbsent,
    FactExists,
    FactKindExists,
    Not,
    Or,
    PredicateExists,
    SubjectExists,
)
from .enums import FactKind
from .evidence import Evidence
from .extractor import (
    ConceptExtractor,
    FactExtractor,
    extract_concepts,
    extract_facts,
)
from .fact_set import FactSet
from .facts import Fact
from .models import Diagnostic, Location
from .rule_set import RuleSet
from .rules import Rule, RuleConclusion, RuleEvaluation

__all__ = [
    "ConceptExtractor",
    "AllOf",
    "And",
    "AnyOf",
    "Condition",
    "ConditionResult",
    "Diagnostic",
    "Evidence",
    "Fact",
    "FactAbsent",
    "FactExists",
    "FactExtractor",
    "FactKind",
    "FactKindExists",
    "FactSet",
    "Location",
    "Not",
    "Or",
    "PredicateExists",
    "Rule",
    "RuleConclusion",
    "RuleEvaluation",
    "RuleSet",
    "SubjectExists",
    "extract_concepts",
    "extract_facts",
]
