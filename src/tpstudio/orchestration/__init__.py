"""Public read-only copy orchestration API."""

from .copy_analysis import (
    CopyAnalysisOptions,
    CopyAnalysisResult,
    CopyProductionResolution,
    CopyProductionResolutionSet,
    FinalConclusionObservation,
    ProductionResolutionStatus,
    RelationEvaluation,
    RelationObservationStatus,
    SnellsLawsCopyAnalyzer,
    analyze_snells_laws_copy,
    summarize_copy_analysis,
)
from tpstudio.conclusion import ConclusionEvaluation
from tpstudio.regression import (
    RegressionMethod,
    RegressionObservation,
    RegressionTargetKind,
    RegressionTechnicalStatus,
    extract_regression_observations,
)
from tpstudio.regression_matching import (
    RegressionSeriesMatch,
    RegressionSeriesMatchStatus,
    match_regression_to_series,
    match_regressions_to_series,
)
from tpstudio.regression_model import (
    RegressionModelAnalysis,
    RegressionModelTechnicalStatus,
    analyze_regression_model,
    analyze_regression_models,
    evaluate_regression_model,
)
from tpstudio.regression_plot_matching import (
    RegressionPlotMatch,
    RegressionPlotMatchStatus,
    match_regression_to_plots,
    match_regressions_to_plots,
)
from tpstudio.graph_analysis import (
    GraphAnalysis,
    GraphAnalysisTechnicalStatus,
    GraphScientificClassification,
    analyze_graph_series,
    analyze_graph_series_collection,
)
from .graph_adapter import (
    GraphCheckStatus,
    GraphEvaluation,
    GraphObservation,
    GraphSeriesData,
    GraphSeriesRole,
    GraphSeriesSource,
    GraphSeriesStatus,
    evaluate_saved_graph,
    observe_saved_graph,
    extract_all_graph_series_data,
)
from .notebook_inspection import (
    NotebookCopySource,
    NotebookTechnicalInspection,
    inspect_notebook,
    load_and_normalize_notebook,
    load_notebook_copy,
)
from .observed_values import (
    ObservedScalarValue,
    ObservedValueDetection,
    ObservedValueSource,
    code_literal_values,
    detect_observed_values,
)

__all__ = [name for name in globals() if not name.startswith("_")]
