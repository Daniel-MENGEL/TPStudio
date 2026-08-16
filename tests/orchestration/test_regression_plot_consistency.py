from __future__ import annotations

import nbformat
import numpy as np

from tpstudio.orchestration.graph_adapter import (
    GraphSeriesData,
    GraphSeriesRole,
    GraphSeriesSource,
    GraphSeriesStatus,
    extract_all_graph_series_data,
)
from tpstudio.regression import extract_regression_observations
from tpstudio.regression_matching import RegressionSeriesMatch, RegressionSeriesMatchStatus
from tpstudio.regression_model import analyze_regression_model, analyze_regression_models
from tpstudio.regression_plot_consistency import (
    RegressionPlotComparisonSource,
    RegressionPlotConsistencyStatus,
    compare_regression_plot,
    compare_regression_plots,
)
from tpstudio.regression_plot_matching import RegressionPlotMatch, RegressionPlotMatchStatus


def _notebook(source: str):
    return nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source)])


def _measured(x, y):
    return GraphSeriesData(
        "measured", "cell", 0, GraphSeriesRole.MEASURED, "x", "y",
        tuple(float(v) for v in x), tuple(float(v) for v in y), len(x),
        (float(min(x)), float(max(x))), (float(min(y)), float(max(y))),
        GraphSeriesStatus.EXTRACTED, GraphSeriesSource.STATIC_CODE,
    )


def _fit(x, y, series_id="fit"):
    return GraphSeriesData(
        series_id, "cell", 0, GraphSeriesRole.FIT, "x", "yfit",
        tuple(float(v) for v in x), tuple(float(v) for v in y), len(x),
        (float(min(x)), float(max(x))), (float(min(y)), float(max(y))),
        GraphSeriesStatus.EXTRACTED, GraphSeriesSource.STATIC_CODE,
    )


def _analysis(degree=1, x=(0, 1, 2), y=(1, 3, 5)):
    source = f"x={list(x)!r}\ny={list(y)!r}\np=np.polyfit(x,y,{degree})\n"
    notebook = _notebook(source)
    regression = extract_regression_observations(source, 0, notebook.cells[0].id)[0]
    measured = _measured(x, y)
    match = RegressionSeriesMatch(
        regression.regression_id, measured.series_id, RegressionSeriesMatchStatus.EXACT,
        "test", (measured.series_id,), (), False,
    )
    return analyze_regression_model(regression, match, measured), regression


def _plot_match(model, status=RegressionPlotMatchStatus.STRUCTURAL_MATCH, plotted="fit"):
    return RegressionPlotMatch(
        model.regression_id, model.series_id, plotted, status, "test", (plotted,),
        "x", "yfit", (), status is not RegressionPlotMatchStatus.STRUCTURAL_MATCH,
    )


def test_affine_structural_match_is_consistent():
    model, _ = _analysis()
    result = compare_regression_plot(model, _plot_match(model), _fit((0, 1, 2), model.predicted_y_values))
    assert result.consistency_status is RegressionPlotConsistencyStatus.CONSISTENT
    assert result.n_compared_points == 3
    assert result.rms_difference == 0.0


def test_quadratic_chute_is_consistent():
    model, _ = _analysis(2, (0, 1, 2, 3), (2, 3, 6, 11))
    result = compare_regression_plot(model, _plot_match(model), _fit((0, 1, 2, 3), model.predicted_y_values))
    assert result.consistency_status is RegressionPlotConsistencyStatus.CONSISTENT


def test_numeric_candidate_equivalent_and_unknown_difference_is_prudent():
    model, _ = _analysis()
    equivalent = compare_regression_plot(
        model, _plot_match(model, RegressionPlotMatchStatus.NUMERIC_CANDIDATE),
        _fit((0, 1, 2), model.predicted_y_values),
    )
    assert equivalent.consistency_status is RegressionPlotConsistencyStatus.NUMERICALLY_EQUIVALENT
    unknown = _fit((0, 1, 2), (0, 0, 0))
    unknown = GraphSeriesData(
        unknown.series_id, unknown.cell_id, unknown.cell_index_snapshot, GraphSeriesRole.UNKNOWN,
        unknown.x_expression, unknown.y_expression, unknown.x_values, unknown.y_values,
        unknown.n_points, unknown.x_range, unknown.y_range, unknown.technical_status,
        unknown.source_kind, unknown.diagnostics,
    )
    different = compare_regression_plot(
        model, _plot_match(model, RegressionPlotMatchStatus.NUMERIC_CANDIDATE), unknown,
    )
    assert different.consistency_status is RegressionPlotConsistencyStatus.NOT_EVALUABLE


def test_fit_numeric_candidate_difference_is_mismatch():
    model, _ = _analysis()
    result = compare_regression_plot(
        model, _plot_match(model, RegressionPlotMatchStatus.NUMERIC_CANDIDATE),
        _fit((0, 1, 2), (0, 0, 0)),
    )
    assert result.consistency_status is RegressionPlotConsistencyStatus.PLOTTED_MODEL_MISMATCH
    assert result.requires_human_review is False


def test_ambiguous_unmatched_and_not_evaluable_are_propagated():
    model, _ = _analysis()
    for match_status, expected in (
        (RegressionPlotMatchStatus.AMBIGUOUS, RegressionPlotConsistencyStatus.AMBIGUOUS),
        (RegressionPlotMatchStatus.UNMATCHED, RegressionPlotConsistencyStatus.UNMATCHED),
        (RegressionPlotMatchStatus.NOT_EVALUABLE, RegressionPlotConsistencyStatus.NOT_EVALUABLE),
    ):
        result = compare_regression_plot(model, _plot_match(model, match_status), None)
        assert result.consistency_status is expected
        assert result.n_compared_points == 0
        assert result.requires_human_review is True


def test_nonfinite_and_mismatched_lengths_are_not_evaluable():
    model, _ = _analysis()
    nonfinite = _fit((0, 1, 2), (1, float("nan"), 5))
    short = GraphSeriesData(
        "fit-short", "cell", 0, GraphSeriesRole.FIT, "x", "yfit",
        (0.0, 1.0), (1.0,), 1, (0.0, 1.0), (1.0, 1.0),
        GraphSeriesStatus.INVALID, GraphSeriesSource.STATIC_CODE,
        ("longueurs_x_y_incompatibles",),
    )
    for series in (nonfinite, short):
        result = compare_regression_plot(model, _plot_match(model), series)
        assert result.consistency_status is RegressionPlotConsistencyStatus.NOT_EVALUABLE


def test_horizontal_model_uses_finite_machine_scale():
    model, _ = _analysis(1, (0, 1, 2), (2, 2, 2))
    identical = compare_regression_plot(model, _plot_match(model), _fit((0, 1, 2), (2, 2, 2)))
    perturbed = compare_regression_plot(model, _plot_match(model), _fit((0, 1, 2), (2, 2, 2.1)))
    assert identical.consistency_status is RegressionPlotConsistencyStatus.CONSISTENT
    assert perturbed.consistency_status is RegressionPlotConsistencyStatus.PLOTTED_MODEL_MISMATCH


def test_large_offset_and_original_coefficients_absent_remain_comparable(monkeypatch):
    monkeypatch.setattr("tpstudio.regression_model._convert_coefficients", lambda *args: None)
    model, _ = _analysis(2, (1e9, 1e9 + 10, 1e9 + 20), (1, 3, 9))
    assert model.coefficients is None
    result = compare_regression_plot(model, _plot_match(model), _fit((1e9, 1e9 + 10, 1e9 + 20), model.predicted_y_values))
    assert result.consistency_status is RegressionPlotConsistencyStatus.CONSISTENT


def test_dense_linspace_is_safely_extracted():
    source = "t=[0,1,2]\nz=[1,2,5]\ntt=np.linspace(min(t),max(t),5)\nplt.plot(tt,tt**2+1,label='fit')\n"
    plotted = extract_all_graph_series_data(_notebook(source))
    assert plotted[0].technical_status is GraphSeriesStatus.EXTRACTED
    assert plotted[0].x_values == (0.0, 0.5, 1.0, 1.5, 2.0)


def test_copy_order_has_one_result_per_match():
    model, _ = _analysis()
    match = _plot_match(model)
    results = compare_regression_plots((model,), (match,), (_fit((0, 1, 2), model.predicted_y_values),))
    assert isinstance(results, tuple)
    assert results[0].regression_id == model.regression_id


def test_public_comparison_controls_rms_overflow(monkeypatch):
    model, _ = _analysis()
    series = _fit((0, 1), (-1e308, -1e308))
    monkeypatch.setattr(
        "tpstudio.regression_plot_consistency.evaluate_regression_model",
        lambda *_args: (1e308, 1e308),
    )
    result = compare_regression_plot(model, _plot_match(model), series)
    assert result.consistency_status is RegressionPlotConsistencyStatus.NOT_EVALUABLE
    assert result.rms_difference is None
    assert result.max_difference is None


def test_shadowed_min_max_are_not_used_as_builtins():
    source = "t=[0,1,2]\nmin=99\ntt=np.linspace(min(t),max(t),3)\nplt.plot(tt,tt)\n"
    plotted = extract_all_graph_series_data(_notebook(source))
    assert plotted[0].technical_status is GraphSeriesStatus.NOT_EVALUABLE

    source = "t=[0,1,2]\ntt=np.linspace(min(t),max(t),3)\nplt.plot(tt,tt)\nmax=99\n"
    plotted = extract_all_graph_series_data(_notebook(source))
    assert plotted[0].technical_status is GraphSeriesStatus.EXTRACTED


def test_linspace_requires_integer_non_boolean_num():
    for expression in ("3.0", "True", "False"):
        source = f"tt=np.linspace(0,1,{expression})\nplt.plot(tt,tt)\n"
        plotted = extract_all_graph_series_data(_notebook(source))
        assert plotted[0].technical_status is GraphSeriesStatus.NOT_EVALUABLE
    source = "n=3\ntt=np.linspace(0,1,n)\nplt.plot(tt,tt)\n"
    plotted = extract_all_graph_series_data(_notebook(source))
    assert plotted[0].technical_status is GraphSeriesStatus.EXTRACTED


def _end_to_end(source: str):
    from tpstudio.regression_matching import match_regressions_to_series
    from tpstudio.regression_plot_matching import match_regressions_to_plots

    notebook = _notebook(source)
    series = extract_all_graph_series_data(notebook)
    regressions = extract_regression_observations(source, 0, notebook.cells[0].id)
    matches = match_regressions_to_series(notebook, regressions, series)
    models = analyze_regression_models(regressions, matches, series)
    plot_matches = match_regressions_to_plots(notebook, regressions, models, series)
    return compare_regression_plots(models, plot_matches, series, regressions, notebook)


def test_dense_chute_expression_is_materialized_and_consistent():
    source = (
        "t=[0,1,2]\nz=[2,3,6]\np=np.polyfit(t,z,2)\n"
        "tt=np.linspace(min(t),max(t),200)\n"
        "zz=p[0]*tt**2+p[1]*tt+p[2]\n"
        "plt.plot(t,z,label='data')\nplt.plot(tt,zz,label='fit')\n"
    )
    result = _end_to_end(source)[0]
    assert result.consistency_status is RegressionPlotConsistencyStatus.CONSISTENT
    assert result.n_compared_points == 200
    assert result.comparison_source is RegressionPlotComparisonSource.RECONSTRUCTED_STRUCTURAL_PLOT


def test_dense_polyval_and_affine_tuple_are_materialized():
    quadratic = (
        "x=[0,1,2]\ny=[1,3,7]\np=np.polyfit(x,y,2)\n"
        "xx=np.linspace(min(x),max(x),100)\n"
        "plt.plot(x,y,label='data')\nplt.plot(xx,np.polyval(p,xx),label='fit')\n"
    )
    affine = (
        "x=[0,1,2]\ny=[1,3,5]\na,b=np.polyfit(x,y,1)\n"
        "xx=np.linspace(min(x),max(x),100)\n"
        "yy=a*xx+b\nplt.plot(x,y,label='data')\nplt.plot(xx,yy,label='fit')\n"
    )
    for source in (quadratic, affine):
        result = _end_to_end(source)[0]
        assert result.consistency_status is RegressionPlotConsistencyStatus.CONSISTENT
        assert result.n_compared_points == 100


def test_original_coefficients_absent_prevent_structural_materialization(monkeypatch):
    source = (
        "x=[0,1,2]\ny=[1,3,5]\np=np.polyfit(x,y,1)\n"
        "xx=np.linspace(min(x),max(x),5)\nplt.plot(x,y,label='data')\n"
        "plt.plot(xx,np.polyval(p,xx),label='fit')\n"
    )
    monkeypatch.setattr("tpstudio.regression_model._convert_coefficients", lambda *args: None)
    result = _end_to_end(source)[0]
    assert result.consistency_status is RegressionPlotConsistencyStatus.NOT_EVALUABLE
