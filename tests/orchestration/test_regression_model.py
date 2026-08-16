from __future__ import annotations

import numpy as np

from tpstudio.orchestration.graph_adapter import (
    GraphSeriesData,
    GraphSeriesRole,
    GraphSeriesSource,
    GraphSeriesStatus,
)
from tpstudio.regression import (
    RegressionMethod,
    RegressionObservation,
    RegressionTargetKind,
    RegressionTechnicalStatus,
)
from tpstudio.regression_matching import RegressionSeriesMatch, RegressionSeriesMatchStatus
from tpstudio.regression_model import (
    RegressionModelTechnicalStatus,
    _convert_coefficients,
    analyze_regression_model,
    analyze_regression_models,
)
from tpstudio.graph_analysis import analyze_graph_series


def _series(x, y, series_id="s1", *, values=True):
    xv, yv = tuple(map(float, x)), tuple(map(float, y))
    return GraphSeriesData(
        series_id, "cell", 0, GraphSeriesRole.MEASURED, "x", "y",
        xv if values else None, yv if values else None, len(xv),
        (min(xv), max(xv)) if values else None,
        (min(yv), max(yv)) if values else None,
        GraphSeriesStatus.EXTRACTED if values else GraphSeriesStatus.NOT_EVALUABLE,
        GraphSeriesSource.STATIC_CODE,
    )


def _regression(degree=1, method=RegressionMethod.NUMPY_POLYFIT, regression_id="r1"):
    return RegressionObservation(
        regression_id, "cell", 0, method, degree, "x", "y",
        RegressionTargetKind.SINGLE, ("p",), (1, 0), RegressionTechnicalStatus.EXTRACTED,
    )


def _match(status=RegressionSeriesMatchStatus.EXACT, series_id="s1"):
    return RegressionSeriesMatch("r1", series_id, status, "test", (series_id,), (), status not in {
        RegressionSeriesMatchStatus.EXACT, RegressionSeriesMatchStatus.NUMERIC_EQUIVALENT,
    })


def test_affine_reconstruction_matches_numpy_oracle():
    series = _series([0, 1, 2, 3], [1, 3, 5, 7])
    result = analyze_regression_model(_regression(), _match(), series)
    assert result.technical_status is RegressionModelTechnicalStatus.EVALUABLE
    assert np.allclose(result.coefficients, np.polyfit(series.x_values, series.y_values, 1))
    assert result.predicted_y_values == (1.0, 3.0, 5.0, 7.0)
    assert result.requires_human_review is False


def test_noisy_affine_remains_technically_evaluable():
    series = _series([0, 1, 2, 3, 4], [1.1, 2.9, 5.2, 6.8, 9.1])
    result = analyze_regression_model(_regression(), _match(), series)
    assert result.technical_status is RegressionModelTechnicalStatus.EVALUABLE
    assert result.predicted_y_values is not None


def test_quadratic_reconstruction_is_stable_and_in_original_basis():
    series = _series([-2, -1, 0, 1, 2], [5, 2, 1, 2, 5])
    result = analyze_regression_model(_regression(2), _match(), series)
    assert result.technical_status is RegressionModelTechnicalStatus.EVALUABLE
    assert np.allclose(result.coefficients, (1.0, 0.0, 1.0))
    assert np.allclose(result.coefficients, np.polyfit(series.x_values, series.y_values, 2))


def test_noisy_quadratic_remains_technically_evaluable():
    series = _series([-2, -1, 0, 1, 2, 3], [5.1, 2.0, 1.2, 2.1, 4.9, 9.2])
    result = analyze_regression_model(_regression(2), _match(), series)
    assert result.technical_status is RegressionModelTechnicalStatus.EVALUABLE
    assert len(result.coefficients) == 3


def test_linregress_is_reconstructed_as_affine():
    series = _series([0, 1, 2], [2, 4, 6])
    result = analyze_regression_model(
        _regression(method=RegressionMethod.SCIPY_LINREGRESS), _match(), series
    )
    assert result.technical_status is RegressionModelTechnicalStatus.EVALUABLE
    assert np.allclose(result.coefficients, (2.0, 2.0))


def test_linregress_quadratic_degree_is_rejected():
    result = analyze_regression_model(
        _regression(2, method=RegressionMethod.SCIPY_LINREGRESS),
        _match(), _series([0, 1, 2], [0, 1, 4]),
    )
    assert result.technical_status is RegressionModelTechnicalStatus.NOT_EVALUABLE
    assert result.coefficients is None
    assert result.predicted_y_values is None
    assert "methode_et_degre_incompatibles" in result.diagnostics


def test_linregress_missing_degree_is_rejected():
    result = analyze_regression_model(
        _regression(None, method=RegressionMethod.SCIPY_LINREGRESS),
        _match(), _series([0, 1, 2], [0, 1, 4]),
    )
    assert result.technical_status is RegressionModelTechnicalStatus.NOT_EVALUABLE
    assert "methode_et_degre_incompatibles" in result.diagnostics


def test_translation_and_unit_change_preserve_predictions():
    x = np.asarray([0., 1., 2., 3.])
    y = 2 * x * x - 3 * x + 4
    translated = _series(x + 1000, y, "translated")
    scaled = _series(1000 * x, 1000 * y, "scaled")
    first = analyze_regression_model(_regression(2), _match(series_id="translated"), translated)
    second = analyze_regression_model(_regression(2), _match(series_id="scaled"), scaled)
    assert first.technical_status is RegressionModelTechnicalStatus.EVALUABLE
    assert second.technical_status is RegressionModelTechnicalStatus.EVALUABLE
    assert np.allclose(first.predicted_y_values, y)
    assert np.allclose(second.predicted_y_values, 1000 * y)


def test_rank_insufficient_for_constant_abscissas():
    result = analyze_regression_model(_regression(2), _match(), _series([1, 1, 1], [1, 2, 3]))
    assert result.technical_status is RegressionModelTechnicalStatus.INSUFFICIENT_RANK
    assert result.requires_human_review


def test_non_exploitable_matches_do_not_reconstruct():
    series = _series([0, 1, 2], [0, 1, 2])
    for status in (RegressionSeriesMatchStatus.REVERSED, RegressionSeriesMatchStatus.AMBIGUOUS,
                   RegressionSeriesMatchStatus.UNMATCHED, RegressionSeriesMatchStatus.NOT_EVALUABLE):
        result = analyze_regression_model(_regression(), _match(status), series)
        assert result.coefficients is None
        assert result.predicted_y_values is None
        assert result.requires_human_review


def test_exact_match_without_numeric_values_is_not_evaluable():
    result = analyze_regression_model(_regression(), _match(), _series([0, 1], [0, 1], values=False))
    assert result.technical_status is RegressionModelTechnicalStatus.NOT_EVALUABLE
    assert "serie_numerique_non_exploitable" in result.diagnostics
    assert result.coefficients is None


def test_non_extracted_series_with_accidental_values_is_rejected():
    series = GraphSeriesData(
        "s1", "cell", 0, GraphSeriesRole.MEASURED, "x", "y",
        (0.0, 1.0, 2.0), (1.0, 2.0, 3.0), 3, (0.0, 2.0), (1.0, 3.0),
        GraphSeriesStatus.NOT_EVALUABLE, GraphSeriesSource.STATIC_CODE,
    )
    result = analyze_regression_model(_regression(), _match(), series)
    assert result.technical_status is RegressionModelTechnicalStatus.NOT_EVALUABLE
    assert result.coefficients is None
    assert result.predicted_y_values is None


def test_large_offset_x_remains_finite_and_evaluable():
    x = [1e9, 1e9 + 10.0, 1e9 + 20.0, 1e9 + 30.0]
    result = analyze_regression_model(_regression(), _match(), _series(x, [1, 3, 5, 7]))
    assert result.technical_status is RegressionModelTechnicalStatus.EVALUABLE
    assert np.isfinite(result.x_center)
    assert np.isfinite(result.x_scale)
    assert np.allclose(result.predicted_y_values, (1.0, 3.0, 5.0, 7.0))


def test_coefficient_reconversion_overflow_is_controlled():
    assert _convert_coefficients(np.asarray([1.0, 1.0]), 1, 1e308, 0.1) is None
    assert _convert_coefficients(np.asarray([1.0, 1.0, 1.0]), 2, 1e308, 1.0) is None


def test_public_analysis_keeps_predictions_when_original_coefficients_fail(monkeypatch):
    monkeypatch.setattr("tpstudio.regression_model._convert_coefficients", lambda *args: None)
    result = analyze_regression_model(_regression(), _match(), _series([0, 1, 2], [1, 3, 5]))
    assert result.coefficients is None
    assert result.predicted_y_values is not None
    assert result.technical_status is RegressionModelTechnicalStatus.NONFINITE_DATA
    assert result.requires_human_review is True
    assert "coefficients_originaux_non_representables_de_facon_finie" in result.diagnostics


def test_affine_model_matches_graph_analysis_reference():
    series = _series([0, 1, 2, 3], [1, 3, 5, 7])
    graph_analysis = analyze_graph_series(series)
    model = analyze_regression_model(_regression(), _match(), series)
    assert model.technical_status is RegressionModelTechnicalStatus.EVALUABLE
    assert np.allclose(model.coefficients, (graph_analysis.slope, graph_analysis.intercept))


def test_noisy_affine_model_matches_graph_analysis_reference():
    series = _series([0, 1, 2, 3, 4], [1.1, 2.9, 5.2, 6.8, 9.1])
    graph_analysis = analyze_graph_series(series)
    model = analyze_regression_model(_regression(), _match(), series)
    assert model.technical_status is RegressionModelTechnicalStatus.EVALUABLE
    assert np.allclose(model.coefficients, (graph_analysis.slope, graph_analysis.intercept))


def test_nonfinite_x_center_is_controlled():
    result = analyze_regression_model(_regression(), _match(), _series([1e308, 1e308, 1e308], [1, 2, 3]))
    assert result.technical_status is RegressionModelTechnicalStatus.NONFINITE_DATA
    assert result.coefficients is None
    assert result.predicted_y_values is None
    assert result.requires_human_review is True
    assert "centre_x_non_fini" in result.diagnostics


def test_nonfinite_x_scale_is_controlled(monkeypatch):
    monkeypatch.setattr("tpstudio.regression_model._center_and_scale", lambda values: (0.0, float("inf")))
    result = analyze_regression_model(_regression(), _match(), _series([0, 1, 2], [1, 2, 3]))
    assert result.technical_status is RegressionModelTechnicalStatus.NONFINITE_DATA
    assert result.coefficients is None
    assert result.predicted_y_values is None
    assert result.requires_human_review is True
    assert "echelle_x_non_finie" in result.diagnostics


def test_constant_x_remains_rank_insufficient():
    result = analyze_regression_model(_regression(), _match(), _series([2, 2, 2], [1, 2, 3]))
    assert result.technical_status is RegressionModelTechnicalStatus.INSUFFICIENT_RANK
    assert "etendue_des_abscisses_insuffisante" in result.diagnostics


def test_collection_preserves_regression_order_and_series_identity():
    regressions = (_regression(1, regression_id="r1"), _regression(2, regression_id="r2"))
    matches = (_match(series_id="s1"), RegressionSeriesMatch("r2", "s2", RegressionSeriesMatchStatus.EXACT, "test", ("s2",), (), False))
    analyses = analyze_regression_models(regressions, matches, (_series([0, 1, 2], [0, 1, 2], "s1"), _series([0, 1, 2], [1, 2, 5], "s2")))
    assert tuple(item.regression_id for item in analyses) == ("r1", "r2")
    assert tuple(item.series_id for item in analyses) == ("s1", "s2")


def test_inconsistent_regression_observation_is_not_an_exception():
    invalid = _regression(3)
    result = analyze_regression_model(invalid, _match(), _series([0, 1, 2], [0, 1, 2]))
    assert result.technical_status is RegressionModelTechnicalStatus.NOT_EVALUABLE
