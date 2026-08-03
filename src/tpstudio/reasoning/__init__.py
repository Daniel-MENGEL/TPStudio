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
from .quantity_extraction import (
    LiteralQuantityExtractor,
    QuantityDetection,
    QuantityObservation,
    extract_expected_quantity,
)
from .relation_matching import (
    LiteralRelationMatcher,
    RelationDetection,
    RelationDetectionSet,
    RelationMatch,
    match_declared_relations,
)
from .student_normalized_errors import (
    LiteralStudentNormalizedErrorExtractor,
    StudentNormalizedErrorDetection,
    StudentNormalizedErrorObservation,
    extract_student_normalized_error,
)
from .comparison_interpretations import (
    ComparisonInterpretationDetection,
    ComparisonInterpretationObservation,
    LiteralComparisonInterpretationExtractor,
    extract_comparison_interpretation,
)
from .comparison_justifications import (
    ComparisonJustificationDetection,
    ComparisonJustificationObservation,
    LiteralComparisonJustificationExtractor,
    extract_comparison_justification,
)
from .rule_set import RuleSet
from .rules import Rule, RuleConclusion, RuleEvaluation

__all__ = [
    "ConceptExtractor",
    "ComparisonInterpretationDetection",
    "ComparisonInterpretationObservation",
    "ComparisonJustificationDetection",
    "ComparisonJustificationObservation",
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
    "LiteralComparisonInterpretationExtractor",
    "LiteralComparisonJustificationExtractor",
    "LiteralQuantityExtractor",
    "LiteralStudentNormalizedErrorExtractor",
    "Not",
    "Or",
    "PredicateExists",
    "QuantityDetection",
    "QuantityObservation",
    "Rule",
    "RuleConclusion",
    "RuleEvaluation",
    "RuleSet",
    "RelationDetection",
    "RelationDetectionSet",
    "RelationMatch",
    "SubjectExists",
    "StudentNormalizedErrorDetection",
    "StudentNormalizedErrorObservation",
    "UnknownDiagnosticDefinitionError",
    "extract_concepts",
    "extract_comparison_interpretation",
    "extract_comparison_justification",
    "extract_facts",
    "extract_expected_quantity",
    "extract_student_normalized_error",
    "format_end_to_end_report",
    "match_declared_relations",
    "run_end_to_end_case",
]
