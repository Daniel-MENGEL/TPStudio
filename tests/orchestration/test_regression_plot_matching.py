from __future__ import annotations

import nbformat
import numpy as np

from tpstudio.orchestration.graph_adapter import extract_all_graph_series_data
from tpstudio.regression import extract_regression_observations
from tpstudio.regression_matching import RegressionSeriesMatch, RegressionSeriesMatchStatus
from tpstudio.regression_model import analyze_regression_model, evaluate_regression_model
from tpstudio.regression_plot_matching import (
    RegressionPlotMatchStatus,
    match_regressions_to_plots,
)
from tpstudio.orchestration.graph_adapter import (
    GraphSeriesData,
    GraphSeriesRole,
    GraphSeriesSource,
    GraphSeriesStatus,
)


def _notebook(source: str):
    return nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source)])


def _measured(series_id="cell-0-series-1"):
    return GraphSeriesData(
        series_id, "cell-0", 0, GraphSeriesRole.MEASURED, "x", "y",
        (0.0, 1.0, 2.0), (1.0, 3.0, 5.0), 3, (0.0, 2.0), (1.0, 5.0),
        GraphSeriesStatus.EXTRACTED, GraphSeriesSource.STATIC_CODE,
    )


def _model(notebook, regression, measured):
    match = RegressionSeriesMatch(
        regression.regression_id, measured.series_id, RegressionSeriesMatchStatus.EXACT,
        "test", (measured.series_id,), (), False,
    )
    return analyze_regression_model(regression, match, measured)


def test_global_collection_and_affine_tuple_structural_match():
    source = """x = [0, 1, 2]\ny = [1, 3, 5]\na, b = np.polyfit(x, y, 1)\nplt.plot(x, y, label='data')\nplt.plot(x, a*x+b, label='fit')\n"""
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    measured = _measured()
    model = _model(notebook, regressions[0], measured)
    plotted = extract_all_graph_series_data(notebook)
    assert len(plotted) == 2
    result = match_regressions_to_plots(notebook, regressions, (model,), plotted)
    assert result[0].status is RegressionPlotMatchStatus.STRUCTURAL_MATCH
    assert result[0].plotted_series_id == "cell-0-series-2"


def test_quadratic_subscripts_and_polyval_are_structural_matches():
    source = """t = [0, 1, 2]\nz = [1, 2, 5]\np = np.polyfit(t, z, 2)\nplt.plot(t, z, label='data')\nplt.plot(t, p[0]*t**2+p[1]*t+p[2], label='fit')\n"""
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    measured = GraphSeriesData(
        "cell-0-series-1", "cell-0", 0, GraphSeriesRole.MEASURED, "t", "z",
        (0.0, 1.0, 2.0), (1.0, 2.0, 5.0), 3, (0.0, 2.0), (1.0, 5.0),
        GraphSeriesStatus.EXTRACTED, GraphSeriesSource.STATIC_CODE,
    )
    model = _model(notebook, regressions[0], measured)
    plotted = extract_all_graph_series_data(notebook)
    result = match_regressions_to_plots(notebook, regressions, (model,), plotted)
    assert result[0].status is RegressionPlotMatchStatus.STRUCTURAL_MATCH

    source_polyval = source.replace("p[0]*t**2+p[1]*t+p[2]", "np.polyval(p, t)")
    notebook_polyval = _notebook(source_polyval)
    regressions_polyval = extract_regression_observations(source_polyval, 0, notebook_polyval.cells[0].id)
    model_polyval = _model(notebook_polyval, regressions_polyval[0], measured)
    result_polyval = match_regressions_to_plots(
        notebook_polyval, regressions_polyval, (model_polyval,), extract_all_graph_series_data(notebook_polyval)
    )
    assert result_polyval[0].status is RegressionPlotMatchStatus.STRUCTURAL_MATCH


def test_intermediate_expression_and_dense_domain_are_supported_structurally():
    source = """t = [0, 1, 2]\nz = [1, 2, 5]\np = np.polyfit(t, z, 2)\ntt = [0, 0.5, 1, 1.5, 2]\nzfit = p[0]*tt**2+p[1]*tt+p[2]\nplt.plot(t, z, label='data')\nplt.plot(tt, zfit)\n"""
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    measured = GraphSeriesData(
        "cell-0-series-1", "cell-0", 0, GraphSeriesRole.MEASURED, "t", "z",
        (0.0, 1.0, 2.0), (1.0, 2.0, 5.0), 3, (0.0, 2.0), (1.0, 5.0),
        GraphSeriesStatus.EXTRACTED, GraphSeriesSource.STATIC_CODE,
    )
    model = _model(notebook, regressions[0], measured)
    result = match_regressions_to_plots(notebook, regressions, (model,), extract_all_graph_series_data(notebook))
    assert result[0].status is RegressionPlotMatchStatus.STRUCTURAL_MATCH


def test_reassigned_coefficient_and_mutated_p_are_not_structural_matches():
    source = """x = [0, 1, 2]\ny = [1, 3, 5]\na, b = np.polyfit(x, y, 1)\na = 0\nplt.plot(x, y, label='data')\nplt.plot(x, a*x+b, label='fit')\n"""
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    model = _model(notebook, regressions[0], _measured())
    result = match_regressions_to_plots(notebook, regressions, (model,), extract_all_graph_series_data(notebook))
    assert result[0].status is not RegressionPlotMatchStatus.STRUCTURAL_MATCH


def test_theory_is_excluded_and_multiple_candidates_are_ambiguous():
    source = """x = [0, 1, 2]\ny = [1, 3, 5]\np = np.polyfit(x, y, 1)\nplt.plot(x, y, label='data')\nplt.plot(x, p[0]*x+p[1], label='fit')\nplt.plot(x, p[0]*x+p[1], label='fit copy')\nplt.plot(x, p[0]*x+p[1], label='theory')\n"""
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    model = _model(notebook, regressions[0], _measured())
    result = match_regressions_to_plots(notebook, regressions, (model,), extract_all_graph_series_data(notebook))
    assert result[0].status is RegressionPlotMatchStatus.AMBIGUOUS
    assert len(result[0].candidate_series_ids) == 2


def test_evaluate_normalized_model_reproduces_observed_predictions():
    source = "p = np.polyfit(x, y, 2)\n"
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    measured = GraphSeriesData(
        "s", "cell", 0, GraphSeriesRole.MEASURED, "x", "y",
        (0.0, 1.0, 2.0, 3.0), (1.0, 2.0, 5.0, 10.0), 4, (0.0, 3.0), (1.0, 10.0),
        GraphSeriesStatus.EXTRACTED, GraphSeriesSource.STATIC_CODE,
    )
    model = _model(notebook, regressions[0], measured)
    evaluated = evaluate_regression_model(model, measured.x_values)
    assert evaluated is not None
    assert np.allclose(evaluated, model.predicted_y_values)


def test_nonfinite_original_coefficients_keep_normalized_evaluator(monkeypatch):
    source = "p = np.polyfit(x, y, 1)\n"
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    measured = _measured()
    monkeypatch.setattr("tpstudio.regression_model._convert_coefficients", lambda *args: None)
    model = _model(notebook, regressions[0], measured)
    assert model.coefficients is None
    evaluated = evaluate_regression_model(model, measured.x_values)
    assert evaluated is not None
    assert np.allclose(evaluated, model.predicted_y_values)


def test_plot_before_fit_is_not_structural():
    source = """x = [0, 1, 2]\ny = [1, 3, 5]\nplt.plot(x, a*x+b, label='fit')\na, b = np.polyfit(x, y, 1)\n"""
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    model = _model(notebook, regressions[0], _measured())
    result = match_regressions_to_plots(notebook, regressions, (model,), extract_all_graph_series_data(notebook))
    assert result[0].status is not RegressionPlotMatchStatus.STRUCTURAL_MATCH


def test_reused_p_matches_only_the_temporally_valid_curve():
    source = """x = [0, 1, 2]\ny = [1, 3, 5]\np = np.polyfit(x, y, 1)\nplt.plot(x, np.polyval(p, x), label='fit')\np = np.polyfit(x, y, 2)\nplt.plot(x, np.polyval(p, x), label='fit')\n"""
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    measured = _measured()
    models = tuple(_model(notebook, regression, measured) for regression in regressions)
    matches = match_regressions_to_plots(notebook, regressions, models, extract_all_graph_series_data(notebook))
    assert all(item.status is RegressionPlotMatchStatus.STRUCTURAL_MATCH for item in matches)
    assert matches[0].plotted_series_id != matches[1].plotted_series_id


def test_reused_tuple_targets_remain_temporally_distinct():
    source = """x=[0,1,2]\ny=[1,3,5]\nu=[0,1,2]\nv=[2,4,6]\na,b=np.polyfit(x,y,1)\nplt.plot(x,a*x+b,label='fit')\na,b=np.polyfit(u,v,1)\nplt.plot(u,a*u+b,label='fit')\n"""
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    models = tuple(_model(notebook, regression, _measured()) for regression in regressions)
    matches = match_regressions_to_plots(notebook, regressions, models, extract_all_graph_series_data(notebook))
    assert all(item.status is RegressionPlotMatchStatus.STRUCTURAL_MATCH for item in matches)
    assert matches[0].plotted_series_id != matches[1].plotted_series_id


def test_plot_domain_must_match_model_input():
    source = """x = [0, 1, 2]\ny = [1, 3, 5]\nu = [10, 11, 12]\np = np.polyfit(x, y, 1)\nplt.plot(x, p[0]*u+p[1], label='fit')\n"""
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    model = _model(notebook, regressions[0], _measured())
    result = match_regressions_to_plots(notebook, regressions, (model,), extract_all_graph_series_data(notebook))
    assert result[0].status is not RegressionPlotMatchStatus.STRUCTURAL_MATCH


def test_new_dense_domain_is_allowed_when_used_consistently():
    source = """x = [0, 1, 2]\ny = [1, 3, 5]\ntt = [0, 0.5, 1, 1.5, 2]\np = np.polyfit(x, y, 1)\nplt.plot(tt, p[0]*tt+p[1], label='fit')\n"""
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    model = _model(notebook, regressions[0], _measured())
    result = match_regressions_to_plots(notebook, regressions, (model,), extract_all_graph_series_data(notebook))
    assert result[0].status is RegressionPlotMatchStatus.STRUCTURAL_MATCH


def test_algebraic_extras_and_wrong_quadratic_orders_are_rejected():
    cases = (
        "a*x-b", "a*x+(-b)", "a*x+b-b", "a*x+b+b", "a*x-b+b",
        "-a*x+b", "2*a*x+b", "a*x+b+1",
        "p[0]*x**2+p[1]*x-p[2]", "-p[0]*x**2+p[1]*x+p[2]",
        "p[0]*x**2-p[1]*x+p[2]", "p[0]*x**2+p[1]*x+p[2]-p[2]",
        "p[0]*x**2+p[1]*x+p[2]+p[2]", "p[0]*x+p[1]*x**2+p[2]",
        "p[2]*x**2+p[1]*x+p[0]", "p[0]*x**2+p[2]",
    )
    for expression in cases:
        if expression.startswith("p["):
            source = f"x=[0,1,2]\ny=[1,3,5]\np=np.polyfit(x,y,2)\nplt.plot(x,{expression},label='fit')\n"
            degree = 2
        else:
            source = f"x=[0,1,2]\ny=[1,3,5]\na,b=np.polyfit(x,y,1)\nplt.plot(x,{expression},label='fit')\n"
            degree = 1
        notebook = _notebook(source)
        regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
        model = _model(notebook, regressions[0], _measured())
        result = match_regressions_to_plots(notebook, regressions, (model,), extract_all_graph_series_data(notebook))
        assert result[0].status is not RegressionPlotMatchStatus.STRUCTURAL_MATCH, (degree, expression)


def test_mutation_after_plot_does_not_retroactively_invalidate_match():
    source = """x=[0,1,2]\ny=[1,3,5]\np=np.polyfit(x,y,1)\nplt.plot(x,np.polyval(p,x),label='fit')\np[0]=0\n"""
    notebook = _notebook(source)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    model = _model(notebook, regressions[0], _measured())
    result = match_regressions_to_plots(notebook, regressions, (model,), extract_all_graph_series_data(notebook))
    assert result[0].status is RegressionPlotMatchStatus.STRUCTURAL_MATCH


def test_valid_additive_reordering_keeps_structural_match():
    cases = (
        ("a,b=np.polyfit(x,y,1)\nplt.plot(x,b+a*x,label='fit')\n", 1),
        ("p=np.polyfit(x,y,2)\nplt.plot(x,p[2]+p[1]*x+p[0]*x**2,label='fit')\n", 2),
    )
    for source, degree in cases:
        full_source = "x=[0,1,2]\ny=[1,3,5]\n" + source
        notebook = _notebook(full_source)
        regressions = extract_regression_observations(full_source, 0, notebook.cells[0].id)
        assert regressions[0].degree == degree
        model = _model(notebook, regressions[0], _measured())
        result = match_regressions_to_plots(
            notebook, regressions, (model,), extract_all_graph_series_data(notebook)
        )
        assert result[0].status is RegressionPlotMatchStatus.STRUCTURAL_MATCH
