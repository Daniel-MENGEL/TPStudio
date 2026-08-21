"""Teacher-declared scientific expectations, independent of reasoning."""

from .models import ExpectedConclusion, ExpectedRelation, ExpectationSet
from .notebook_bindings import (
    CellProductionBinding,
    CellTextScope,
    CellTextScopeKind,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
)
from .quantities import ExpectedQuantity, PresenceRequirement, QuantityExpectationSet
from .sufficiency import (
    ExpectationSufficiency,
    ExpectationSufficiencyAssessment,
    assess_expectation_sufficiency,
)
from .quantity_comparisons import (
    ComparisonPedagogicalContext,
    ExpectedQuantityComparison,
    NormalizedErrorThresholds,
    QuantityComparisonExpectationSet,
    QuantityComparisonMethod,
)
from .comparison_interpretations import (
    ComparisonInterpretationExpectationSet,
    ComparisonInterpretationKind,
    ExpectedComparisonInterpretation,
)
from .comparison_justifications import (
    ComparisonJustificationElementKind,
    ComparisonJustificationExpectationSet,
    ComparisonJustificationRequirement,
    ExpectedComparisonJustification,
    ExpectedComparisonJustificationElement,
)
from .registry import ExpectationRegistry
from .scientific_productions import (
    EvaluationBasis,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
)
from .uncertainties import (
    UncertaintyQualityExpectationSet,
    UncertaintyQualitySpec,
)
from .student_normalized_errors import (
    ExpectedStudentNormalizedError,
    StudentNormalizedErrorExpectationSet,
)
from .derived_quantities import (
    Add,
    Constant,
    DerivedExpression,
    DerivedQuantityEvaluation,
    DerivedQuantityEvaluationStatus,
    Divide,
    ExpectedDerivedQuantity,
    Multiply,
    OperandRef,
    Power,
    ProductionValue,
    RegressionParameter,
    RegressionParameterKind,
    RegressionParameterRef,
    Subtract,
    TeacherConstant,
    evaluate_derived_quantity,
)
from .source_resolution import (
    build_derived_source_resolution_context,
    DerivedQuantityRuntimeEvaluation,
    DerivedSourceResolution,
    DerivedSourceResolutionContext,
    DerivedSourceResolutionStatus,
    ResolvedDerivedSource,
    evaluate_derived_quantity_from_analysis,
    resolve_derived_quantity_sources,
)
from .derived_validation import (
    DerivedQuantityPlanValidation,
    validate_derived_quantity_expectation,
)

__all__ = [
    "CellProductionBinding",
    "CellTextScope",
    "CellTextScopeKind",
    "ComparisonPedagogicalContext",
    "ComparisonInterpretationExpectationSet",
    "ComparisonInterpretationKind",
    "ComparisonJustificationElementKind",
    "ComparisonJustificationExpectationSet",
    "ComparisonJustificationRequirement",
    "ExpectedConclusion",
    "ExpectedComparisonInterpretation",
    "ExpectedComparisonJustification",
    "ExpectedComparisonJustificationElement",
    "ExpectedQuantityComparison",
    "ExpectedQuantity",
    "ExpectedRelation",
    "ExpectedStudentNormalizedError",
    "EvaluationBasis",
    "ExpectationRegistry",
    "ExpectationSet",
    "NotebookBindingPlan",
    "NotebookCellSelector",
    "NotebookCellSelectorKind",
    "NormalizedErrorThresholds",
    "PresenceRequirement",
    "QuantityExpectationSet",
    "ExpectationSufficiency",
    "ExpectationSufficiencyAssessment",
    "assess_expectation_sufficiency",
    "QuantityComparisonExpectationSet",
    "QuantityComparisonMethod",
    "ScientificProductionKind",
    "ScientificProductionPlan",
    "ScientificProductionSpec",
    "StudentNormalizedErrorExpectationSet",
    "UncertaintyQualityExpectationSet",
    "UncertaintyQualitySpec",
    "Add",
    "Constant",
    "DerivedExpression",
    "DerivedQuantityEvaluation",
    "DerivedQuantityEvaluationStatus",
    "Divide",
    "ExpectedDerivedQuantity",
    "Multiply",
    "OperandRef",
    "Power",
    "ProductionValue",
    "RegressionParameter",
    "RegressionParameterKind",
    "RegressionParameterRef",
    "Subtract",
    "TeacherConstant",
    "evaluate_derived_quantity",
    "DerivedQuantityRuntimeEvaluation",
    "DerivedSourceResolution",
    "DerivedSourceResolutionContext",
    "DerivedSourceResolutionStatus",
    "ResolvedDerivedSource",
    "evaluate_derived_quantity_from_analysis",
    "resolve_derived_quantity_sources",
    "build_derived_source_resolution_context",
    "DerivedQuantityPlanValidation",
    "validate_derived_quantity_expectation",
]
