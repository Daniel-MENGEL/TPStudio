from dataclasses import replace
from pathlib import Path

from tests.orchestration.test_copy_analysis import _analyze
from tpstudio.graph_analysis import GraphAnalysisTechnicalStatus, GraphScientificClassification
from tpstudio.regression_matching import RegressionSeriesMatchStatus
from tpstudio.regression_plot_consistency import RegressionPlotConsistencyStatus
from tpstudio.regression_model import RegressionModelTechnicalStatus
from tpstudio.reporting import (
    TeacherGraphDiagnosticReason,
    TeacherGraphHeadlineStatus,
    build_teacher_graph_diagnostics,
)


def _evaluable_result(tmp_path: Path):
    result = _analyze(tmp_path)
    geometry = replace(
        result.all_graph_analyses[0],
        technical_status=GraphAnalysisTechnicalStatus.EVALUABLE,
        scientific_classification=GraphScientificClassification.LINEAR_COMPATIBLE,
    )
    model = replace(
        result.regression_model_analyses[0],
        series_id=geometry.series_id,
        technical_status=RegressionModelTechnicalStatus.EVALUABLE,
    )
    match = replace(
        result.regression_series_matches[0],
        status=RegressionSeriesMatchStatus.EXACT,
        matched_series_id=geometry.series_id,
    )
    consistency = replace(
        result.regression_plot_consistency_analyses[0],
        consistency_status=RegressionPlotConsistencyStatus.CONSISTENT,
    )
    return replace(
        result,
        graph_analyses=(geometry,),
        all_graph_analyses=(geometry,),
        regression_model_analyses=(model,),
        regression_series_matches=(match,),
        regression_plot_consistency_analyses=(consistency,),
    )


def test_diagnostic_projects_compatible_geometry_and_coherent_plot(tmp_path: Path) -> None:
    diagnostics = build_teacher_graph_diagnostics(_evaluable_result(tmp_path))
    diagnostic = diagnostics[0]
    assert diagnostic.headline_status is TeacherGraphHeadlineStatus.OK
    assert TeacherGraphDiagnosticReason.ALIGNMENT_COMPATIBLE in diagnostic.motifs
    assert TeacherGraphDiagnosticReason.PLOT_COHERENT in diagnostic.motifs
    assert diagnostic.requires_human_review is False
    assert all("LINEAR_COMPATIBLE" not in line for line in diagnostic.summary_lines)


def test_inconclusive_geometry_is_review_without_new_threshold(tmp_path: Path) -> None:
    result = _evaluable_result(tmp_path)
    geometry = replace(
        result.all_graph_analyses[0],
        scientific_classification=GraphScientificClassification.INCONCLUSIVE,
    )
    result = replace(result, graph_analyses=(geometry,), all_graph_analyses=(geometry,))
    diagnostic = build_teacher_graph_diagnostics(result)[0]
    assert diagnostic.headline_status is TeacherGraphHeadlineStatus.REVIEW
    assert TeacherGraphDiagnosticReason.ALIGNMENT_INCONCLUSIVE in diagnostic.motifs
    assert diagnostic.requires_human_review is True


def test_clearly_nonlinear_geometry_is_problem(tmp_path: Path) -> None:
    result = _evaluable_result(tmp_path)
    geometry = replace(
        result.all_graph_analyses[0],
        scientific_classification=GraphScientificClassification.CLEARLY_NONLINEAR,
    )
    result = replace(result, graph_analyses=(geometry,), all_graph_analyses=(geometry,))
    diagnostic = build_teacher_graph_diagnostics(result)[0]
    assert diagnostic.headline_status is TeacherGraphHeadlineStatus.PROBLEM
    assert TeacherGraphDiagnosticReason.ALIGNMENT_NONLINEAR in diagnostic.motifs


def test_no_expected_model_means_constrained_bias_is_descriptive_only(tmp_path: Path) -> None:
    result = _evaluable_result(tmp_path)
    diagnostic = build_teacher_graph_diagnostics(result, expected_model="LINEAR_THROUGH_ORIGIN")[0]
    assert all("décentr" not in line.lower() for line in diagnostic.summary_lines)
    assert not any("offset" in motif.value for motif in diagnostic.motifs)


def test_unmatched_plot_alone_stays_informational(tmp_path: Path) -> None:
    result = _evaluable_result(tmp_path)
    consistency = replace(
        result.regression_plot_consistency_analyses[0],
        consistency_status=RegressionPlotConsistencyStatus.UNMATCHED,
    )
    result = replace(result, regression_plot_consistency_analyses=(consistency,))
    diagnostic = build_teacher_graph_diagnostics(result)[0]
    assert diagnostic.headline_status is TeacherGraphHeadlineStatus.OK
    assert TeacherGraphDiagnosticReason.PLOT_NOT_IDENTIFIED in diagnostic.motifs
    assert diagnostic.requires_human_review is False


def test_plot_mismatch_remains_problem(tmp_path: Path) -> None:
    result = _evaluable_result(tmp_path)
    consistency = replace(
        result.regression_plot_consistency_analyses[0],
        consistency_status=RegressionPlotConsistencyStatus.PLOTTED_MODEL_MISMATCH,
    )
    result = replace(result, regression_plot_consistency_analyses=(consistency,))
    diagnostic = build_teacher_graph_diagnostics(result)[0]
    assert diagnostic.headline_status is TeacherGraphHeadlineStatus.PROBLEM
    assert TeacherGraphDiagnosticReason.PLOT_MISMATCH in diagnostic.motifs
    assert diagnostic.requires_human_review is False


def test_non_evaluable_model_is_review(tmp_path: Path) -> None:
    result = _evaluable_result(tmp_path)
    model = replace(
        result.regression_model_analyses[0],
        technical_status=RegressionModelTechnicalStatus.NOT_EVALUABLE,
    )
    result = replace(result, regression_model_analyses=(model,))
    diagnostic = build_teacher_graph_diagnostics(result)[0]
    assert diagnostic.headline_status is TeacherGraphHeadlineStatus.REVIEW
    assert TeacherGraphDiagnosticReason.MODEL_NOT_EVALUABLE in diagnostic.motifs
