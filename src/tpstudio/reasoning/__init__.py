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
from .diagnostic_builder import DiagnosticBuilder
from .diagnostics import (
    Diagnostic,
    DiagnosticCategory,
    DiagnosticDefinition,
    DiagnosticRegistry,
    DiagnosticSet,
    DiagnosticSeverity,
    UnknownDiagnosticDefinitionError,
)
from .demo import (
    EndToEndCase,
    EndToEndReport,
    format_end_to_end_report,
    run_end_to_end_case,
)
from .evidence import Evidence
from .extractor import (
    ConceptExtractor,
    FactExtractor,
    extract_concepts,
    extract_facts,
)
from .fact_set import FactSet
from .facts import Fact
from .inference import InferenceEngine, InferenceResult
from .models import Location
from .relation_matching import (
    LiteralRelationMatcher,
    RelationDetection,
    RelationDetectionSet,
    RelationMatch,
    match_declared_relations,
)
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
    "DiagnosticBuilder",
    "DiagnosticCategory",
    "DiagnosticDefinition",
    "DiagnosticRegistry",
    "DiagnosticSet",
    "DiagnosticSeverity",
    "Evidence",
    "EndToEndCase",
    "EndToEndReport",
    "Fact",
    "FactAbsent",
    "FactExists",
    "FactExtractor",
    "FactKind",
    "FactKindExists",
    "FactSet",
    "InferenceEngine",
    "InferenceResult",
    "Location",
    "LiteralRelationMatcher",
    "Not",
    "Or",
    "PredicateExists",
    "Rule",
    "RuleConclusion",
    "RuleEvaluation",
    "RuleSet",
    "RelationDetection",
    "RelationDetectionSet",
    "RelationMatch",
    "SubjectExists",
    "UnknownDiagnosticDefinitionError",
    "extract_concepts",
    "extract_facts",
    "format_end_to_end_report",
    "match_declared_relations",
    "run_end_to_end_case",
]
