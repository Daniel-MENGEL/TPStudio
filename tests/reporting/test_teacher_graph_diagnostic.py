from dataclasses import replace
from pathlib import Path

from tests.orchestration.test_copy_analysis import _analyze
from tpstudio.graph_analysis import GraphAnalysisTechnicalStatus, GraphScientificClassification
from tpstudio.regression_matching import RegressionSeriesMatchStatus
from tpstudio.regression_plot_consistency import RegressionPlotConsistencyStatus
from tpstudio.regression_model import RegressionModelTechnicalStatus
from tpstudio.projects import ExpectedGraphModel
from tpstudio.orchestration.graph_adapter import GraphSeriesRole
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


def _two_regression_result(tmp_path: Path):
    result = _evaluable_result(tmp_path)
    first_observation = result.regression_observations[0]
    first_model = result.regression_model_analyses[0]
    first_match = result.regression_series_matches[0]
    first_consistency = result.regression_plot_consistency_analyses[0]
    first_geometry = result.all_graph_analyses[0]
    second_id = f"{first_observation.regression_id}-second"
    second_series_id = f"{first_geometry.series_id}-second"
    second_observation = replace(first_observation, regression_id=second_id)
    second_model = replace(first_model, regression_id=second_id, series_id=second_series_id)
    second_match = replace(first_match, regression_id=second_id, matched_series_id=second_series_id)
    second_consistency = replace(first_consistency, regression_id=second_id, model_series_id=second_series_id)
    second_geometry = replace(first_geometry, series_id=second_series_id)
    return replace(
        result,
        regression_observations=(first_observation, second_observation),
        regression_model_analyses=(first_model, second_model),
        regression_series_matches=(first_match, second_match),
        regression_plot_consistency_analyses=(first_consistency, second_consistency),
        graph_analyses=(first_geometry, second_geometry),
        all_graph_analyses=(first_geometry, second_geometry),
    )


def _project_conflict(result, second_model: ExpectedGraphModel):
    evaluation = result.graph_evaluations[0]
    conflicting_expectation = replace(
        evaluation.expectation,
        production_id="conflicting-graph",
        expected_model=second_model,
    )
    return replace(
        result,
        graph_evaluations=(
            replace(evaluation, expectation=conflicting_expectation),
            evaluation,
        ),
    )


def test_diagnostic_projects_compatible_geometry_and_coherent_plot(tmp_path: Path) -> None:
    diagnostics = build_teacher_graph_diagnostics(_evaluable_result(tmp_path))
    diagnostic = diagnostics[0]
    assert diagnostic.headline_status is TeacherGraphHeadlineStatus.OK
    assert TeacherGraphDiagnosticReason.ALIGNMENT_COMPATIBLE in diagnostic.motifs
    assert TeacherGraphDiagnosticReason.PLOT_COHERENT in diagnostic.motifs
    assert diagnostic.requires_human_review is False
    assert diagnostic.expected_model is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN
    assert all("LINEAR_COMPATIBLE" not in line for line in diagnostic.summary_lines)


def test_project_contract_takes_precedence_over_global_fallback(tmp_path: Path) -> None:
    result = _evaluable_result(tmp_path)
    without_fallback = build_teacher_graph_diagnostics(result)[0]
    with_fallback = build_teacher_graph_diagnostics(
        result,
        expected_model=ExpectedGraphModel.AFFINE,
    )[0]
    assert with_fallback.expected_model is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN
    assert (with_fallback.headline_status, with_fallback.motifs, with_fallback.summary_lines) == (
        without_fallback.headline_status,
        without_fallback.motifs,
        without_fallback.summary_lines,
    )


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
    diagnostic = build_teacher_graph_diagnostics(
        result, expected_model=ExpectedGraphModel.LINEAR_THROUGH_ORIGIN
    )[0]
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


def test_project_contract_conflict_blocks_global_fallback(tmp_path: Path) -> None:
    result = _project_conflict(_evaluable_result(tmp_path), ExpectedGraphModel.AFFINE)
    diagnostic = build_teacher_graph_diagnostics(
        result, expected_model=ExpectedGraphModel.QUADRATIC
    )[0]
    assert diagnostic.expected_model is None


def test_project_contract_conflict_without_fallback_is_none(tmp_path: Path) -> None:
    result = _project_conflict(_evaluable_result(tmp_path), ExpectedGraphModel.AFFINE)
    assert build_teacher_graph_diagnostics(result)[0].expected_model is None


def test_explicit_series_mapping_overrides_project_conflict(tmp_path: Path) -> None:
    result = _project_conflict(_evaluable_result(tmp_path), ExpectedGraphModel.AFFINE)
    series_id = result.regression_model_analyses[0].series_id
    diagnostic = build_teacher_graph_diagnostics(
        result,
        expected_model=ExpectedGraphModel.QUADRATIC,
        expected_models_by_series={series_id: ExpectedGraphModel.AFFINE},
    )[0]
    assert diagnostic.expected_model is ExpectedGraphModel.AFFINE


def test_identical_project_contracts_are_retained(tmp_path: Path) -> None:
    result = _project_conflict(_evaluable_result(tmp_path), ExpectedGraphModel.LINEAR_THROUGH_ORIGIN)
    assert build_teacher_graph_diagnostics(result)[0].expected_model is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN


def test_per_series_mapping_keeps_two_graph_contracts_distinct(tmp_path: Path) -> None:
    result = _two_regression_result(tmp_path)
    first, second = result.regression_model_analyses
    diagnostics = build_teacher_graph_diagnostics(
        result,
        expected_models_by_series={
            first.series_id: ExpectedGraphModel.LINEAR_THROUGH_ORIGIN,
            second.series_id: ExpectedGraphModel.AFFINE,
        },
    )
    assert [item.expected_model for item in diagnostics] == [
        ExpectedGraphModel.LINEAR_THROUGH_ORIGIN,
        ExpectedGraphModel.AFFINE,
    ]


def test_series_without_project_contract_uses_fallback_only_when_absent(tmp_path: Path) -> None:
    result = replace(_evaluable_result(tmp_path), graph_evaluations=())
    without_contract = build_teacher_graph_diagnostics(result, expected_model=None)[0]
    with_fallback = build_teacher_graph_diagnostics(
        result, expected_model=ExpectedGraphModel.AFFINE
    )[0]
    assert without_contract.expected_model is None
    assert with_fallback.expected_model is ExpectedGraphModel.AFFINE
    assert (without_contract.headline_status, without_contract.motifs, without_contract.summary_lines) == (
        with_fallback.headline_status, with_fallback.motifs, with_fallback.summary_lines
    )


def test_two_regressions_on_same_series_share_contract(tmp_path: Path) -> None:
    result = _two_regression_result(tmp_path)
    second_model = replace(
        result.regression_model_analyses[1],
        series_id=result.regression_model_analyses[0].series_id,
    )
    result = replace(result, regression_model_analyses=(result.regression_model_analyses[0], second_model))
    diagnostics = build_teacher_graph_diagnostics(
        result,
        expected_models_by_series={
            result.regression_model_analyses[0].series_id: ExpectedGraphModel.AFFINE,
        },
    )
    assert [item.expected_model for item in diagnostics] == [
        ExpectedGraphModel.AFFINE,
        ExpectedGraphModel.AFFINE,
    ]


def test_project_contract_currently_covers_all_observed_series_roles(tmp_path: Path) -> None:
    result = _evaluable_result(tmp_path)
    evaluation = result.graph_evaluations[0]
    observation = evaluation.observation
    measured = observation.series_data[0]
    fit = replace(
        measured,
        series_id=f"{measured.series_id}-fit",
        role=GraphSeriesRole.FIT,
    )
    observation = replace(observation, series_data=(measured, fit))
    evaluation = replace(evaluation, observation=observation)
    model = replace(result.regression_model_analyses[0], series_id=fit.series_id)
    geometry = replace(result.all_graph_analyses[0], series_id=fit.series_id)
    result = replace(
        result,
        graph_evaluations=(evaluation,),
        regression_model_analyses=(model,),
        graph_analyses=(geometry,),
        all_graph_analyses=(geometry,),
    )
    assert build_teacher_graph_diagnostics(result)[0].expected_model is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN
