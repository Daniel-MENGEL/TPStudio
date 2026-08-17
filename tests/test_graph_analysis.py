from __future__ import annotations

import math
from dataclasses import replace

import pytest
import tpstudio.graph_analysis as graph_analysis_module

from tpstudio.graph_analysis import (
    GraphAnalysisTechnicalStatus,
    GraphScientificClassification,
    analyze_graph_series,
    analyze_graph_series_collection,
)
from tpstudio.orchestration import (
    GraphSeriesData,
    GraphSeriesRole,
    GraphSeriesSource,
    GraphSeriesStatus,
)


def _series(x, y, *, role=GraphSeriesRole.MEASURED, status=GraphSeriesStatus.EXTRACTED):
    return GraphSeriesData(
        "series-test", "cell-test", 3, role, "x", "y",
        tuple(float(value) for value in x) if x is not None else None,
        tuple(float(value) for value in y) if y is not None else None,
        len(x) if x is not None else 0,
        (min(x), max(x)) if x else None,
        (min(y), max(y)) if y else None,
        status, GraphSeriesSource.STATIC_CODE,
    )


def test_perfect_line_is_compatible_without_r2() -> None:
    result = analyze_graph_series(_series(range(6), [2 * value + 1 for value in range(6)]))
    assert result.scientific_classification is GraphScientificClassification.LINEAR_COMPATIBLE
    assert result.requires_human_review is False
    assert result.residual_rms == pytest.approx(0.0)
    assert not hasattr(result, "r2")


def test_noisy_line_is_compatible_and_scale_invariant() -> None:
    x = (0, 1, 2, 3, 4, 5)
    y = (1.0, 3.1, 4.9, 7.1, 8.9, 11.0)
    first = analyze_graph_series(_series(x, y))
    scaled = analyze_graph_series(_series(x, [value * 1000 for value in y]))
    assert first.scientific_classification is GraphScientificClassification.LINEAR_COMPATIBLE
    assert scaled.scientific_classification is first.scientific_classification


@pytest.mark.parametrize(
    "transform",
    [
        lambda x, y: ([value * 1000 + 1e9 for value in x], [value * 1000 - 7e8 for value in y]),
        lambda x, y: ([value + 1e9 for value in x], [value + 1e9 for value in y]),
        lambda x, y: ([value * 1e-3 for value in x], [value * 1e3 for value in y]),
    ],
)
def test_affine_changes_of_units_and_origin_preserve_classification(transform) -> None:
    x = (0, 1, 2, 3, 4, 5)
    y = (1.0, 3.1, 4.9, 7.1, 8.9, 11.0)
    first = analyze_graph_series(_series(x, y))
    changed_x, changed_y = transform(x, y)
    changed = analyze_graph_series(_series(changed_x, changed_y))
    assert changed.scientific_classification is first.scientific_classification


@pytest.mark.parametrize("scale, offset", [(1e-9, 3e-6), (1e9, -4e12)])
def test_y_scale_and_translation_preserve_curvature_classification(scale, offset) -> None:
    x = tuple(range(6))
    y = tuple(float(value * value) for value in x)
    baseline = analyze_graph_series(_series(x, y))
    transformed = analyze_graph_series(_series(x, [scale * value + offset for value in y]))
    assert transformed.scientific_classification is baseline.scientific_classification
    assert transformed.quadratic_improvement_metric == pytest.approx(baseline.quadratic_improvement_metric)


def test_horizontal_low_amplitude_noise_is_scale_invariant() -> None:
    x = tuple(range(6))
    y = (4.0, 4.01, 3.99, 4.0, 4.01, 3.99)
    baseline = analyze_graph_series(_series(x, y))
    scaled = analyze_graph_series(_series(x, [value * 1e-9 for value in y]))
    assert scaled.scientific_classification is baseline.scientific_classification
    assert scaled.max_leave_one_out_effect == pytest.approx(baseline.max_leave_one_out_effect)


def test_manifest_curvature_is_non_linear() -> None:
    result = analyze_graph_series(_series(range(6), [value * value for value in range(6)]))
    assert result.scientific_classification is GraphScientificClassification.CLEARLY_NONLINEAR
    assert result.curvature_indicator == "manifest"
    assert result.quadratic_improvement_metric == pytest.approx(1.0)
    assert result.residual_pattern == "curvature"


def test_weak_curvature_and_influential_point_are_conservative() -> None:
    weak = analyze_graph_series(_series(range(6), [value * value * 0.01 + value for value in range(6)]))
    assert weak.scientific_classification is GraphScientificClassification.INCONCLUSIVE
    influential = analyze_graph_series(_series(range(6), [1, 3, 5, 7, 9, 30]))
    assert influential.scientific_classification is GraphScientificClassification.INCONCLUSIVE
    assert "point" in " ".join(influential.diagnostics)


@pytest.mark.parametrize("values", [([0, 1], [1, 3]), ([0, 1, 2], [1, 3, 5])])
def test_two_or_three_points_are_inconclusive(values) -> None:
    result = analyze_graph_series(_series(*values))
    assert result.scientific_classification is GraphScientificClassification.INCONCLUSIVE


def test_four_points_can_be_compatible_but_x_constant_is_not_evaluable() -> None:
    four = analyze_graph_series(_series([0, 1, 2, 3], [1, 3, 5, 7]))
    assert four.scientific_classification is GraphScientificClassification.LINEAR_COMPATIBLE
    constant = analyze_graph_series(_series([1, 1, 1, 1], [1, 2, 3, 4]))
    assert constant.technical_status is GraphAnalysisTechnicalStatus.NOT_EVALUABLE
    assert "abscisses" in " ".join(constant.diagnostics)


def test_constant_y_can_be_a_compatible_horizontal_affine_relation() -> None:
    result = analyze_graph_series(_series(range(6), [4, 4, 4, 4, 4, 4]))
    assert result.scientific_classification is GraphScientificClassification.LINEAR_COMPATIBLE
    assert result.slope == pytest.approx(0.0)


def test_oscillating_residuals_are_reported() -> None:
    result = analyze_graph_series(_series(range(6), [1, 3.2, 4.8, 7.2, 8.8, 11.1]))
    assert result.residual_sign_structure in {"alternating", "grouped"}


def test_x_order_does_not_change_geometric_result() -> None:
    x = (0, 1, 2, 3, 4, 5)
    y = (0, 1.1, 3.9, 9.2, 16.1, 24.8)
    ordered = analyze_graph_series(_series(x, y))
    order = (3, 0, 5, 2, 1, 4)
    shuffled = analyze_graph_series(_series([x[i] for i in order], [y[i] for i in order]))
    assert shuffled.scientific_classification is ordered.scientific_classification
    assert shuffled.residual_pattern == ordered.residual_pattern
    assert shuffled.quadratic_improvement_metric == pytest.approx(ordered.quadratic_improvement_metric)
    assert shuffled.residual_sign_structure == ordered.residual_sign_structure
    assert shuffled.curvature_indicator == ordered.curvature_indicator
    assert shuffled.max_leave_one_out_effect == pytest.approx(ordered.max_leave_one_out_effect)


def test_concentrated_abscissas_are_inconclusive() -> None:
    result = analyze_graph_series(_series(
        [0, 0.001, 0.002, 0.003, 0.004, 10],
        [1, 1.002, 1.004, 1.006, 1.008, 21],
    ))
    assert result.scientific_classification is GraphScientificClassification.INCONCLUSIVE
    assert "concentrees" in " ".join(result.diagnostics)


def test_bimodal_abscissas_do_not_create_a_false_curvature_pattern() -> None:
    result = analyze_graph_series(_series(
        [0, 0.1, 0.2, 0.3, 0.4, 9.6, 9.7, 9.8, 9.9, 10],
        [0, 0.2, 0.4, 0.6, 0.8, 19.2, 19.4, 19.6, 19.8, 20],
    ))
    assert result.residual_pattern != "curvature"
    assert result.scientific_classification is not GraphScientificClassification.CLEARLY_NONLINEAR


def test_repeated_abscissas_limit_geometric_confidence() -> None:
    result = analyze_graph_series(_series(
        [0, 0, 0, 0, 1, 1, 1, 1, 2, 2],
        [0, 0.1, -0.1, 0.05, 2, 2.1, 1.9, 2.05, 4, 4.1],
    ))
    assert result.n_unique_x == 3
    assert result.scientific_classification is not GraphScientificClassification.CLEARLY_NONLINEAR


def test_multiple_measured_series_remain_independent_and_ordered() -> None:
    first = replace(_series(range(6), [2 * value + 1 for value in range(6)]), series_id="measured-1")
    second = replace(_series(range(6), [value * value for value in range(6)]), series_id="measured-2")
    analyses = analyze_graph_series_collection((first, second))
    assert tuple(item.series_id for item in analyses) == ("measured-1", "measured-2")
    assert analyses[0].scientific_classification is GraphScientificClassification.LINEAR_COMPATIBLE
    assert analyses[1].scientific_classification is GraphScientificClassification.CLEARLY_NONLINEAR


def test_exponential_geometry_is_not_classified_by_function_family() -> None:
    narrow = analyze_graph_series(_series([0, 0.1, 0.2, 0.3, 0.4, 0.5], [1, 1.1, 1.22, 1.35, 1.49, 1.65]))
    wide = analyze_graph_series(_series(range(6), [math.exp(0.3 * value) for value in range(6)]))
    assert narrow.scientific_classification is not GraphScientificClassification.CLEARLY_NONLINEAR
    assert wide.scientific_classification is GraphScientificClassification.CLEARLY_NONLINEAR


def test_quadratic_four_points_is_not_sufficient_for_non_linearity() -> None:
    result = analyze_graph_series(_series([0, 1, 2, 3], [0, 1, 4, 9]))
    assert result.scientific_classification is not GraphScientificClassification.CLEARLY_NONLINEAR


def test_no_residual_x_correlation_metric_is_used() -> None:
    result = analyze_graph_series(_series(range(6), [value * value for value in range(6)]))
    assert not hasattr(result, "residual_trend_metric")


def test_horizontal_noisy_series_has_bounded_influence() -> None:
    result = analyze_graph_series(_series(range(6), [4.0, 4.01, 3.99, 4.0, 4.01, 3.99]))
    assert result.max_leave_one_out_effect is not None
    assert result.max_leave_one_out_effect < 1.0


@pytest.mark.parametrize("values", [
    [1, 3, 5, 7, 9, 30],
    [1, 3, 20, 7, 9, 11],
    [4, 4.01, 3.99, 4, 4.01, 14],
])
def test_strong_influence_blocks_categorical_curvature(values) -> None:
    result = analyze_graph_series(_series(range(6), values))
    assert result.scientific_classification is GraphScientificClassification.INCONCLUSIVE
    assert result.requires_human_review is True
    assert "point" in " ".join(result.diagnostics)


def test_influence_exactly_at_threshold_is_inconclusive(monkeypatch) -> None:
    monkeypatch.setattr(
        graph_analysis_module,
        "_loo_metrics",
        lambda x, y, slope, intercept, y_scale: (None, None, graph_analysis_module.STRONG_INFLUENCE_EFFECT),
    )
    result = analyze_graph_series(_series(range(6), [value * value for value in range(6)]))
    assert result.scientific_classification is GraphScientificClassification.INCONCLUSIVE
    assert result.requires_human_review is True


def test_non_measured_or_invalid_series_is_not_evaluable() -> None:
    fit = analyze_graph_series(_series(range(5), range(5), role=GraphSeriesRole.FIT))
    assert fit.technical_status is GraphAnalysisTechnicalStatus.NOT_EVALUABLE
    invalid = analyze_graph_series(_series(None, None, status=GraphSeriesStatus.NOT_EVALUABLE))
    assert invalid.scientific_classification is None


def test_analysis_does_not_reparse_or_execute_notebook() -> None:
    result = analyze_graph_series(_series([0, 1, 2, 3, 4], [1, 3, 5, 7, 9]))
    assert result.series_id == "series-test"
    assert result.cell_id == "cell-test"
    assert math.isfinite(result.slope)


def test_residual_diagnostics_for_origin_line_are_centered_when_exact() -> None:
    result = analyze_graph_series(_series(range(6), [2 * value for value in range(6)]), constrained_linear_slope=2.0)
    diagnostics = result.residual_diagnostics
    assert diagnostics is not None
    assert diagnostics.constrained_model_available is True
    assert diagnostics.constrained_residual_rms == pytest.approx(0.0)
    assert diagnostics.constrained_mean_signed_residual == pytest.approx(0.0)
    assert diagnostics.constrained_sign_imbalance == pytest.approx(0.0)
    assert diagnostics.constrained_near_zero_count == 6


@pytest.mark.parametrize("offset, expected_sign", [(1.0, 1), (-1.0, -1)])
def test_residual_diagnostics_capture_origin_offset(offset, expected_sign) -> None:
    result = analyze_graph_series(
        _series(range(6), [2 * value + offset for value in range(6)]),
        constrained_linear_slope=2.0,
    )
    diagnostics = result.residual_diagnostics
    assert diagnostics is not None
    assert diagnostics.constrained_residual_rms == pytest.approx(abs(offset))
    assert diagnostics.constrained_mean_signed_residual == pytest.approx(offset)
    assert diagnostics.constrained_positive_count == (6 if expected_sign > 0 else 0)
    assert diagnostics.constrained_negative_count == (0 if expected_sign > 0 else 6)
    assert diagnostics.constrained_sign_imbalance == pytest.approx(1.0)


def test_residual_diagnostics_separate_dispersion_from_centering() -> None:
    result = analyze_graph_series(
        _series(range(6), [1, -1, 1, -1, -2, 2]),
        constrained_linear_slope=0.0,
    )
    diagnostics = result.residual_diagnostics
    assert diagnostics is not None
    assert diagnostics.constrained_residual_rms > 0.0
    assert diagnostics.constrained_mean_signed_residual == pytest.approx(0.0)
    assert diagnostics.constrained_sign_imbalance == pytest.approx(0.0)


def test_residual_diagnostics_absent_for_non_evaluable_series() -> None:
    result = analyze_graph_series(_series(None, None, status=GraphSeriesStatus.NOT_EVALUABLE))
    assert result.residual_diagnostics is None


def test_residual_diagnostics_are_not_invented_without_associated_model() -> None:
    result = analyze_graph_series(_series(range(6), [2 * value + 1 for value in range(6)]))
    assert result.scientific_classification is GraphScientificClassification.LINEAR_COMPATIBLE
    assert result.residual_diagnostics is None


def test_zero_vertical_scale_keeps_absolute_metrics_but_not_normalized_ones() -> None:
    result = analyze_graph_series(
        _series(range(4), [4.0, 4.0, 4.0, 4.0]),
        constrained_linear_slope=1.0,
    )
    diagnostics = result.residual_diagnostics
    assert diagnostics is not None
    assert diagnostics.vertical_scale == pytest.approx(0.0)
    assert diagnostics.constrained_residual_rms is not None
    assert diagnostics.constrained_residual_max_abs is not None
    assert diagnostics.constrained_residual_max_normalized is None
    assert diagnostics.constrained_mean_signed_residual_normalized is None
