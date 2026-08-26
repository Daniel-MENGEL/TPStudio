from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import importlib.util

import pytest

from tpstudio.reporting import TeacherCopyReport, build_teacher_copy_report
from tpstudio.graph_analysis import GraphScientificClassification
from tpstudio.regression_matching import RegressionSeriesMatchStatus
from tpstudio.regression_model import RegressionModelTechnicalStatus
from tpstudio.regression_plot_consistency import (
    RegressionPlotComparisonSource, RegressionPlotConsistencyStatus,
)


def _copy_test_module():
    path = Path("tests/orchestration/test_copy_analysis.py")
    spec = importlib.util.spec_from_file_location("copy_analysis_fixture", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_builder_projects_analysis_without_path_or_mutation(tmp_path) -> None:
    result = _copy_test_module()._analyze(tmp_path)
    report = build_teacher_copy_report(result)
    assert type(report) is TeacherCopyReport
    assert report.project_id == "snells-laws-mvp"
    assert report.source_id == "synthetic"
    assert len(report.productions) == 24
    assert str(tmp_path) not in repr(report)
    assert not hasattr(report, "score") and not hasattr(report, "grade")
    with pytest.raises(FrozenInstanceError): report.title = "x"


def test_overview_and_human_review_follow_analysis(tmp_path) -> None:
    module = _copy_test_module()
    result = module._analyze(tmp_path, module._notebook(placeholder=True, error=True))
    report = build_teacher_copy_report(result)
    assert report.overview.placeholder_count >= 1
    assert report.overview.technical_error_count == 1
    assert report.human_review.required
    assert report.priorities


def test_builder_rejects_non_analysis() -> None:
    with pytest.raises(TypeError): build_teacher_copy_report(object())


def test_graph_regression_projection_is_separate_and_teacher_safe(tmp_path) -> None:
    report = build_teacher_copy_report(_copy_test_module()._analyze(tmp_path))
    assert isinstance(report.regression_graphs, tuple)
    for item in report.regression_graphs:
        assert item.headline_text
        assert not any(token in item.headline_text for token in (
            "CONSISTENT", "NUMERICALLY_EQUIVALENT", "STRUCTURAL_MATCH", "EXACT",
        ))
        assert not any(token in line for line in item.summary_lines for token in (
            "CONSISTENT", "NUMERICALLY_EQUIVALENT", "STRUCTURAL_MATCH", "EXACT",
        ))
    # The historical expectation-linked graph projection remains available.
    assert hasattr(report, "graph")


def _projected_graph_report(tmp_path, *, match_status=None, consistency_status=None,
                            model_status=RegressionModelTechnicalStatus.EVALUABLE,
                            source=RegressionPlotComparisonSource.EXTRACTED_PLOT_VALUES,
                            geometry_status=None):
    module = _copy_test_module()
    result = module._analyze(tmp_path)
    match = result.regression_series_matches[0]
    model = result.regression_model_analyses[0]
    consistency = result.regression_plot_consistency_analyses[0]
    if match_status is not None:
        match = replace(match, status=match_status, matched_series_id="measured-1")
    model = replace(model, series_id="measured-1", technical_status=model_status)
    if consistency_status is not None:
        consistency = replace(
            consistency, model_series_id="measured-1", consistency_status=consistency_status,
            comparison_source=source, plotted_series_id="plot-1",
        )
    if geometry_status is not None:
        geometry = replace(
            result.graph_analyses[0], series_id="measured-1",
            scientific_classification=geometry_status,
        )
        result = replace(result, graph_analyses=(geometry,))
    return build_teacher_copy_report(replace(
        result, regression_series_matches=(match,), regression_model_analyses=(model,),
        regression_plot_consistency_analyses=(consistency,),
    )).regression_graphs[0]


def test_graph_projection_statuses_and_priorities(tmp_path) -> None:
    mismatch = _projected_graph_report(
        tmp_path, match_status=RegressionSeriesMatchStatus.EXACT,
        consistency_status=RegressionPlotConsistencyStatus.PLOTTED_MODEL_MISMATCH,
    )
    assert mismatch.headline_status.value == "problem"
    assert mismatch.requires_human_review is False
    assert "ne correspond pas" in " ".join(mismatch.summary_lines)

    equivalent = _projected_graph_report(
        tmp_path, match_status=RegressionSeriesMatchStatus.EXACT,
        consistency_status=RegressionPlotConsistencyStatus.NUMERICALLY_EQUIVALENT,
    )
    assert equivalent.headline_status.value == "ok"
    assert "numériquement équivalente" in " ".join((equivalent.headline_text, *equivalent.summary_lines))

    ambiguous_series = _projected_graph_report(
        tmp_path, match_status=RegressionSeriesMatchStatus.AMBIGUOUS,
        consistency_status=RegressionPlotConsistencyStatus.NOT_EVALUABLE,
    )
    assert ambiguous_series.headline_status.value == "review"
    assert ambiguous_series.requires_human_review is True

    ambiguous_plot = _projected_graph_report(
        tmp_path, match_status=RegressionSeriesMatchStatus.EXACT,
        consistency_status=RegressionPlotConsistencyStatus.AMBIGUOUS,
    )
    assert ambiguous_plot.headline_status.value == "review"
    assert ambiguous_plot.requires_human_review is True


def test_graph_projection_snell_unmatched_is_informational(tmp_path) -> None:
    summary = _projected_graph_report(
        tmp_path, match_status=RegressionSeriesMatchStatus.EXACT,
        consistency_status=RegressionPlotConsistencyStatus.UNMATCHED,
    )
    assert summary.headline_status.value == "info"
    assert summary.requires_human_review is False
    assert "Régression affine détectée" == summary.headline_text
    assert "Aucune courbe de modèle distincte" in " ".join(summary.summary_lines)


def test_graph_projection_non_evaluable_model_and_reversed(tmp_path) -> None:
    non_evaluable = _projected_graph_report(
        tmp_path, match_status=RegressionSeriesMatchStatus.EXACT,
        consistency_status=RegressionPlotConsistencyStatus.UNMATCHED,
        model_status=RegressionModelTechnicalStatus.NOT_EVALUABLE,
    )
    assert non_evaluable.headline_status.value == "review"
    assert non_evaluable.requires_human_review is True

    reversed_summary = _projected_graph_report(
        tmp_path, match_status=RegressionSeriesMatchStatus.REVERSED,
        consistency_status=RegressionPlotConsistencyStatus.UNMATCHED,
        model_status=RegressionModelTechnicalStatus.UNSUPPORTED_MATCH,
    )
    assert reversed_summary.headline_status.value == "problem"
    assert reversed_summary.requires_human_review is True
    assert "axes utilisés" in " ".join(reversed_summary.summary_lines)


def test_graph_projection_priority_and_secondary_geometry(tmp_path) -> None:
    mismatch_over_reversed = _projected_graph_report(
        tmp_path, match_status=RegressionSeriesMatchStatus.REVERSED,
        consistency_status=RegressionPlotConsistencyStatus.PLOTTED_MODEL_MISMATCH,
    )
    assert mismatch_over_reversed.headline_status.value == "problem"
    assert "courbe incohérente" in mismatch_over_reversed.headline_text

    inconclusive = _projected_graph_report(
        tmp_path, match_status=RegressionSeriesMatchStatus.EXACT,
        consistency_status=RegressionPlotConsistencyStatus.CONSISTENT,
        geometry_status=GraphScientificClassification.INCONCLUSIVE,
    )
    assert inconclusive.headline_status.value == "ok"
    assert inconclusive.requires_human_review is False
    assert "géométrie du nuage demande" in " ".join(inconclusive.summary_lines)


def test_quantity_counts_follow_scientific_assessment_not_value_presence(tmp_path) -> None:
    module = _copy_test_module()
    notebook = module._notebook()
    cell = module._cell_with(
        notebook, "### Résultat — Première méthode de mesure de l'indice"
    )
    cell.source = cell.source.replace("n = (1.50 ± 0.05)", "n = 1.50")
    result = module._analyze(tmp_path, notebook)
    report = build_teacher_copy_report(result)
    expected_evaluable = sum(
        item.assessed
        and item.assessment is not None
        and item.assessment.is_structurally_satisfied
        for item in result.quantity_evaluations
    )
    assert report.overview.evaluable_quantity_count == expected_evaluable
    assert report.overview.non_evaluable_quantity_count == len(report.quantities) - expected_evaluable
    non_evaluable_with_value = tuple(
        item for item in report.quantities if not item.evaluable and item.value is not None
    )
    assert non_evaluable_with_value
    assert all(item.value is not None for item in non_evaluable_with_value)
    assert any(item.evaluable and item.value is not None for item in report.quantities)


def test_external_path_strings_are_removed_from_teacher_model(tmp_path) -> None:
    result = _copy_test_module()._analyze(tmp_path)
    private_paths = (
        "/Users/example/private/data.csv",
        "/home/student/private/file.txt",
    )
    inspection = replace(
        result.technical_inspection,
        referenced_external_paths=private_paths,
    )
    report = build_teacher_copy_report(replace(result, technical_inspection=inspection))
    assert report.technical.external_path_reference_count == 2
    assert not hasattr(report.technical, "referenced_external_paths")
    assert all(path not in repr(report) for path in private_paths)


def test_feedback_and_diagnostic_source_keys_are_business_stable_not_positional(tmp_path) -> None:
    module = _copy_test_module()
    result = module._analyze(tmp_path, module._notebook(omit_marker="# Méthode statistique"))
    first = build_teacher_copy_report(result)
    reordered_result = replace(
        result,
        feedback=tuple(reversed(result.feedback)),
        diagnostics=tuple(reversed(result.diagnostics)),
    )
    second = build_teacher_copy_report(reordered_result)
    assert {item.source_key for item in first.feedback} == {item.source_key for item in second.feedback}
    assert {item.source_key for item in first.diagnostics} == {item.source_key for item in second.diagnostics}
    assert len({item.source_key for item in first.feedback}) == len(first.feedback)
    assert len({item.source_key for item in first.diagnostics}) == len(first.diagnostics)
    assert all(not item.source_key.startswith("feedback-00") for item in first.feedback)
    assert all(not item.source_key.startswith("diagnostic-00") for item in first.diagnostics)
