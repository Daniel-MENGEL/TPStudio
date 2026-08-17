"""Prudent numerical diagnostics for already extracted graph series.

This module intentionally receives :class:`GraphSeriesData` only.  It never
parses notebooks, executes student code, or uses R² as a classification rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from tpstudio.orchestration.graph_adapter import GraphSeriesData


class GraphAnalysisTechnicalStatus(str, Enum):
    EVALUABLE = "evaluable"
    NOT_EVALUABLE = "not_evaluable"


class GraphScientificClassification(str, Enum):
    LINEAR_COMPATIBLE = "linear_compatible"
    CLEARLY_NONLINEAR = "clearly_nonlinear"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class GraphResidualDiagnostics:
    """Descriptive residual facts for the origin-constrained affine model.

    This structure deliberately contains no classification or threshold.  The
    existing :class:`GraphAnalysis` fields remain the diagnostics for the
    freely fitted affine line; these values describe the additional reference
    ``y = a*x`` using the same fitted slope ``a``.
    """

    n_points: int
    vertical_scale: float | None
    constrained_model_available: bool
    constrained_residual_rms: float | None
    constrained_residual_max_abs: float | None
    constrained_residual_max_normalized: float | None
    constrained_mean_signed_residual: float | None
    constrained_mean_signed_residual_normalized: float | None
    constrained_positive_count: int | None
    constrained_negative_count: int | None
    constrained_near_zero_count: int | None
    constrained_sign_imbalance: float | None


@dataclass(frozen=True, slots=True)
class GraphAnalysis:
    series_id: str
    cell_id: str | None
    cell_index_snapshot: int
    n_points: int
    model_type: str
    slope: float | None
    intercept: float | None
    residual_rms: float | None
    max_abs_residual: float | None
    residual_range_normalized: float | None
    residual_sign_structure: str
    residual_pattern: str
    x_coverage_metric: float | None
    n_unique_x: int | None
    leave_one_out_slope_range: tuple[float, float] | None
    leave_one_out_intercept_range: tuple[float, float] | None
    max_leave_one_out_effect: float | None
    quadratic_improvement_metric: float | None
    quadratic_fit_status: str
    curvature_indicator: str
    technical_status: GraphAnalysisTechnicalStatus
    scientific_classification: GraphScientificClassification | None
    diagnostics: tuple[str, ...]
    requires_human_review: bool
    residual_diagnostics: GraphResidualDiagnostics | None = None


# These are deliberately centralized provisional calibration parameters.  They
# describe compatibility over the observed range; they are not physical laws.
MAX_RELATIVE_RESIDUAL_FOR_LINEAR = 0.05
POSSIBLE_CURVATURE_IMPROVEMENT = 0.20
MANIFEST_CURVATURE_IMPROVEMENT = 0.50
STRONG_RESIDUAL_AMPLITUDE = 0.05
STRONG_INFLUENCE_EFFECT = 0.30
VERY_STRONG_INFLUENCE_EFFECT = 0.80
MIN_X_COVERAGE_FOR_CLASSIFICATION = 0.25
X_RELATIVE_SPREAD_EPSILON = 1e-12
SIGN_EPSILON = 1e-10
MAX_QUADRATIC_CONDITION = 1e10


def _finite(values: tuple[float, ...] | None) -> bool:
    return bool(values) and all(math.isfinite(value) for value in values)


def _fit_affine(x: tuple[float, ...], y: tuple[float, ...]) -> tuple[float, float] | None:
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    denominator = sum((value - mean_x) ** 2 for value in x)
    if denominator <= 0.0:
        return None
    slope = sum((x_value - mean_x) * (y_value - mean_y) for x_value, y_value in zip(x, y)) / denominator
    return slope, mean_y - slope * mean_x


def _fit_quadratic(
    x: tuple[float, ...], y: tuple[float, ...]
) -> tuple[tuple[float, float, float], float, float] | None:
    """Fit in centered/scaled coordinates, never on raw x powers."""
    mean_x = sum(x) / len(x)
    scale_x = max(abs(value - mean_x) for value in x)
    if scale_x <= 0.0:
        return None
    z = np.asarray([(value - mean_x) / scale_x for value in x], dtype=float)
    design = np.column_stack((z * z, z, np.ones(len(z))))
    try:
        if np.linalg.matrix_rank(design) < 3 or np.linalg.cond(design) > MAX_QUADRATIC_CONDITION:
            return None
        coefficients, _, _, _ = np.linalg.lstsq(design, np.asarray(y, dtype=float), rcond=None)
    except (FloatingPointError, ValueError, np.linalg.LinAlgError):
        return None
    if not np.all(np.isfinite(coefficients)):
        return None
    return (float(coefficients[0]), float(coefficients[1]), float(coefficients[2])), mean_x, scale_x


def _quadratic_predictions(
    x: tuple[float, ...], fit: tuple[tuple[float, float, float], float, float]
) -> tuple[float, ...] | None:
    coefficients, mean_x, scale_x = fit
    try:
        values = tuple(
            coefficients[0] * ((value - mean_x) / scale_x) ** 2
            + coefficients[1] * ((value - mean_x) / scale_x)
            + coefficients[2]
            for value in x
        )
    except (ArithmeticError, OverflowError):
        return None
    return values if all(math.isfinite(value) for value in values) else None


def _sse(y: tuple[float, ...], predictions: tuple[float, ...] | None) -> float | None:
    if predictions is None:
        return None
    try:
        value = sum((observed - predicted) ** 2 for observed, predicted in zip(y, predictions))
    except (ArithmeticError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _sign_structure(residuals: tuple[float, ...]) -> str:
    scale = max((abs(value) for value in residuals), default=0.0)
    signs = [1 if value > scale * SIGN_EPSILON else -1 if value < -scale * SIGN_EPSILON else 0 for value in residuals]
    signs = [sign for sign in signs if sign]
    if len(signs) < 3:
        return "none"
    runs = 1 + sum(left != right for left, right in zip(signs, signs[1:]))
    alternating = all(left != right for left, right in zip(signs, signs[1:]))
    if alternating and len(signs) >= 4:
        return "alternating"
    if runs == 2 and len(signs) >= 4:
        return "grouped"
    return "none"


def _residual_pattern(
    x: tuple[float, ...], residuals: tuple[float, ...], y_scale: float
) -> str:
    """Describe geometry after sorting by x; alternating noise is not enough."""
    ordered = sorted(zip(x, residuals), key=lambda pair: pair[0])
    if len(ordered) < 5 or y_scale <= 0.0:
        return "none"
    x_min, x_max = ordered[0][0], ordered[-1][0]
    x_range = x_max - x_min
    if x_range <= 0.0:
        return "insufficient_zones"
    zones = [[], [], []]
    for value_x, value_r in ordered:
        position = (value_x - x_min) / x_range
        zones[min(2, int(position * 3))].append(value_r)
    if any(len(zone) < 2 for zone in zones):
        return "insufficient_zones"
    means = [sum(zone) / len(zone) for zone in zones]
    amplitude = STRONG_RESIDUAL_AMPLITUDE * y_scale
    if all(abs(mean) >= amplitude for mean in means):
        if means[0] * means[2] > 0 and means[0] * means[1] < 0:
            return "curvature"
    signs = [1 if value > 0 else -1 if value < 0 else 0 for _, value in ordered]
    signs = [sign for sign in signs if sign]
    runs = 1 + sum(left != right for left, right in zip(signs, signs[1:])) if signs else 0
    if len(signs) >= 4 and all(left != right for left, right in zip(signs, signs[1:])):
        return "alternating"
    if len(signs) >= 4 and runs == 2:
        return "grouped"
    return "none"


def _loo_metrics(
    x: tuple[float, ...], y: tuple[float, ...], slope: float, intercept: float, y_scale: float
) -> tuple[tuple[float, float] | None, tuple[float, float] | None, float | None]:
    fits = [fit for index in range(len(x)) if (fit := _fit_affine(x[:index] + x[index + 1 :], y[:index] + y[index + 1 :])) is not None]
    if not fits:
        return None, None, None
    slopes = tuple(fit[0] for fit in fits)
    intercepts = tuple(fit[1] for fit in fits)
    if y_scale <= 0.0:
        effect = 0.0
    else:
        reference = tuple(slope * value + intercept for value in x)
        prediction_effects = []
        for loo_slope, loo_intercept in fits:
            prediction_effects.append(
                max(abs((loo_slope * value + loo_intercept) - expected) for value, expected in zip(x, reference))
                / y_scale
            )
        effect = max(prediction_effects, default=0.0)
    return (min(slopes), max(slopes)), (min(intercepts), max(intercepts)), effect


def _constrained_residual_diagnostics(
    x: tuple[float, ...],
    y: tuple[float, ...],
    slope: float,
    vertical_scale: float,
) -> GraphResidualDiagnostics:
    """Measure residuals around ``y = slope*x`` without classifying them."""

    n = len(x)
    unavailable = dict(
        n_points=n,
        vertical_scale=vertical_scale if math.isfinite(vertical_scale) else None,
        constrained_model_available=False,
        constrained_residual_rms=None,
        constrained_residual_max_abs=None,
        constrained_residual_max_normalized=None,
        constrained_mean_signed_residual=None,
        constrained_mean_signed_residual_normalized=None,
        constrained_positive_count=None,
        constrained_negative_count=None,
        constrained_near_zero_count=None,
        constrained_sign_imbalance=None,
    )
    try:
        residuals = tuple(y_value - slope * x_value for x_value, y_value in zip(x, y))
    except (ArithmeticError, OverflowError):
        return GraphResidualDiagnostics(**unavailable)
    if len(residuals) != n or not all(math.isfinite(value) for value in residuals):
        return GraphResidualDiagnostics(**unavailable)
    max_abs = max((abs(value) for value in residuals), default=0.0)
    if not math.isfinite(max_abs):
        return GraphResidualDiagnostics(**unavailable)
    near_zero_scale = max_abs * SIGN_EPSILON
    positive = sum(value > near_zero_scale for value in residuals)
    negative = sum(value < -near_zero_scale for value in residuals)
    near_zero = n - positive - negative
    rms = math.sqrt(sum(value * value for value in residuals) / n) if n else 0.0
    mean_signed = sum(residuals) / n if n else 0.0
    if not all(math.isfinite(value) for value in (rms, mean_signed)):
        return GraphResidualDiagnostics(**unavailable)
    normalized_max = max_abs / vertical_scale if vertical_scale > 0.0 else None
    normalized_mean = mean_signed / vertical_scale if vertical_scale > 0.0 else None
    if any(value is not None and not math.isfinite(value) for value in (normalized_max, normalized_mean)):
        return GraphResidualDiagnostics(**unavailable)
    return GraphResidualDiagnostics(
        n_points=n,
        vertical_scale=vertical_scale if math.isfinite(vertical_scale) else None,
        constrained_model_available=True,
        constrained_residual_rms=rms,
        constrained_residual_max_abs=max_abs,
        constrained_residual_max_normalized=normalized_max,
        constrained_mean_signed_residual=mean_signed,
        constrained_mean_signed_residual_normalized=normalized_mean,
        constrained_positive_count=positive,
        constrained_negative_count=negative,
        constrained_near_zero_count=near_zero,
        constrained_sign_imbalance=abs(positive - negative) / n if n else 0.0,
    )


def analyze_graph_series(
    series: "GraphSeriesData",
    *,
    constrained_linear_slope: float | None = None,
) -> GraphAnalysis:
    """Analyze one measured series without reparsing its notebook."""

    # Local import avoids a package-initialization cycle: orchestration imports
    # this pure layer while exposing GraphSeriesData.
    from tpstudio.orchestration.graph_adapter import GraphSeriesRole, GraphSeriesStatus

    required_fields = (
        "series_id", "cell_id", "cell_index_snapshot", "role", "x_values",
        "y_values", "n_points", "technical_status",
    )
    if any(not hasattr(series, field) for field in required_fields):
        raise TypeError("L'analyse exige une GraphSeriesData.")
    base = dict(
        series_id=series.series_id,
        cell_id=series.cell_id,
        cell_index_snapshot=series.cell_index_snapshot,
        n_points=series.n_points,
        model_type="AFFINE",
        slope=None,
        intercept=None,
        residual_rms=None,
        max_abs_residual=None,
        residual_range_normalized=None,
        residual_sign_structure="none",
        residual_pattern="none",
        x_coverage_metric=None,
        n_unique_x=None,
        leave_one_out_slope_range=None,
        leave_one_out_intercept_range=None,
        max_leave_one_out_effect=None,
        quadratic_improvement_metric=None,
        quadratic_fit_status="unavailable",
        curvature_indicator="unknown",
        technical_status=GraphAnalysisTechnicalStatus.NOT_EVALUABLE,
        scientific_classification=None,
        residual_diagnostics=None,
        diagnostics=(),
        requires_human_review=True,
    )
    if series.role is not GraphSeriesRole.MEASURED:
        base["diagnostics"] = ("serie_non_mesuree",)
        return GraphAnalysis(**base)
    if series.technical_status is not GraphSeriesStatus.EXTRACTED or not _finite(series.x_values) or not _finite(series.y_values):
        base["diagnostics"] = ("donnees_non_evaluables",)
        return GraphAnalysis(**base)
    x, y = series.x_values, series.y_values
    assert x is not None and y is not None
    n = len(x)
    base["n_points"] = n
    if n < 2:
        base["diagnostics"] = ("trop_peu_de_points",)
        return GraphAnalysis(**base)
    x_range = max(x) - min(x)
    centered_x = tuple(value - sum(x) / n for value in x)
    scale_x = max(abs(value) for value in centered_x)
    if scale_x <= 0.0 or x_range <= scale_x * X_RELATIVE_SPREAD_EPSILON:
        base["diagnostics"] = ("etendue_des_abscisses_insuffisante",)
        return GraphAnalysis(**base)
    fit = _fit_affine(x, y)
    if fit is None:
        base["diagnostics"] = ("ajustement_affine_impossible",)
        return GraphAnalysis(**base)
    slope, intercept = fit
    residuals = tuple(y_value - (slope * x_value + intercept) for x_value, y_value in zip(x, y))
    mean_y = sum(y) / n
    centered_y = tuple(value - mean_y for value in y)
    y_scale = max(abs(value) for value in centered_y)
    rms = math.sqrt(sum(value * value for value in residuals) / n)
    max_abs = max(abs(value) for value in residuals)
    normalized = max_abs / y_scale if y_scale > 0.0 else 0.0
    residual_range_normalized = (
        (max(residuals) - min(residuals)) / y_scale
        if y_scale > 0.0 else 0.0
    )
    ordered_residuals = tuple(value for _, value in sorted(zip(x, residuals), key=lambda pair: pair[0]))
    signs = _sign_structure(ordered_residuals)
    pattern = _residual_pattern(x, residuals, y_scale)
    loo_slopes, loo_intercepts, loo_effect = _loo_metrics(x, y, slope, intercept, y_scale)
    quadratic = _fit_quadratic(x, y) if n >= 4 else None
    affine_sse = sum(value * value for value in residuals)
    quadratic_predictions = _quadratic_predictions(x, quadratic) if quadratic is not None else None
    quadratic_sse = _sse(y, quadratic_predictions)
    relative_sse_epsilon = np.finfo(float).eps * max(1, n) * (y_scale ** 2)
    improvement = (
        0.0 if affine_sse <= relative_sse_epsilon
        else (affine_sse - quadratic_sse) / affine_sse
        if quadratic_sse is not None else None
    )
    curvature = "manifest" if improvement is not None and improvement >= MANIFEST_CURVATURE_IMPROVEMENT and normalized > STRONG_RESIDUAL_AMPLITUDE else "possible" if improvement is not None and improvement >= POSSIBLE_CURVATURE_IMPROVEMENT else "none"
    n_unique_x = len(set(x))
    max_gap = max((right - left for left, right in zip(sorted(x), sorted(x)[1:])), default=0.0)
    coverage = 1.0 - max_gap / x_range if x_range > 0 else 0.0
    coverage_insufficient = n_unique_x < 3 or coverage < MIN_X_COVERAGE_FOR_CLASSIFICATION
    strong_structure = pattern == "curvature" or (normalized > STRONG_RESIDUAL_AMPLITUDE and signs == "grouped")
    diagnostics: list[str] = []
    if n <= 3:
        classification = GraphScientificClassification.INCONCLUSIVE
        diagnostics.append("trop_peu_de_points_pour_conclure")
    elif coverage_insufficient:
        classification = GraphScientificClassification.INCONCLUSIVE
        diagnostics.append("les_abscisses_sont_trop_concentrees")
    elif loo_effect is not None and loo_effect >= VERY_STRONG_INFLUENCE_EFFECT:
        classification = GraphScientificClassification.INCONCLUSIVE
        diagnostics.append("la_conclusion_depend_sensiblement_d_un_point")
    elif loo_effect is not None and loo_effect >= STRONG_INFLUENCE_EFFECT:
        classification = GraphScientificClassification.INCONCLUSIVE
        diagnostics.append("la_conclusion_depend_sensiblement_d_un_point")
    elif curvature == "manifest" and n >= 5 and pattern == "curvature":
        classification = GraphScientificClassification.CLEARLY_NONLINEAR
        diagnostics.append("les_ecarts_a_la_droite_presentent_une_structure_systematique")
    elif normalized <= MAX_RELATIVE_RESIDUAL_FOR_LINEAR and not strong_structure and (improvement is None or improvement < POSSIBLE_CURVATURE_IMPROVEMENT):
        classification = GraphScientificClassification.LINEAR_COMPATIBLE
        diagnostics.append("les_points_restent_proches_d_une_droite_sur_l_etendue_observee")
    elif pattern == "insufficient_zones" and curvature != "none":
        classification = GraphScientificClassification.INCONCLUSIVE
        diagnostics.append("la_repartition_des_abscisses_ne_permet_pas_d_evaluer_solidement_la_courbure")
    else:
        classification = GraphScientificClassification.INCONCLUSIVE
        diagnostics.append("les_indicateurs_ne_permettent_pas_de_conclure_avec_surete")
    base.update(
        slope=slope, intercept=intercept, residual_rms=rms,
        max_abs_residual=max_abs, residual_range_normalized=residual_range_normalized,
        residual_sign_structure=signs, residual_pattern=pattern,
        x_coverage_metric=coverage, n_unique_x=n_unique_x,
        leave_one_out_slope_range=loo_slopes,
        leave_one_out_intercept_range=loo_intercepts,
        max_leave_one_out_effect=loo_effect,
        quadratic_improvement_metric=improvement,
        quadratic_fit_status="evaluable" if quadratic_sse is not None else "unavailable",
        curvature_indicator=curvature,
        technical_status=GraphAnalysisTechnicalStatus.EVALUABLE,
        scientific_classification=classification,
        residual_diagnostics=(
            _constrained_residual_diagnostics(x, y, constrained_linear_slope, y_scale)
            if constrained_linear_slope is not None and math.isfinite(constrained_linear_slope)
            else None
        ),
        diagnostics=tuple(diagnostics),
        requires_human_review=classification is GraphScientificClassification.INCONCLUSIVE,
    )
    return GraphAnalysis(**base)


def analyze_graph_series_collection(
    series: tuple[GraphSeriesData, ...],
    *,
    constrained_linear_slopes: dict[str, float] | None = None,
) -> tuple[GraphAnalysis, ...]:
    slopes = constrained_linear_slopes or {}
    return tuple(
        analyze_graph_series(item, constrained_linear_slope=slopes.get(item.series_id))
        for item in series
    )
