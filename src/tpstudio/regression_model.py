"""Stable reconstruction of already matched student regression models.

Only values extracted safely by A74a1 are used.  This module never executes a
student regression call and does not claim to observe coefficients stored in
the notebook's Python state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import TYPE_CHECKING

import numpy as np

from tpstudio.graph_analysis import MAX_QUADRATIC_CONDITION
from tpstudio.regression import RegressionMethod, RegressionObservation, RegressionTechnicalStatus
from tpstudio.regression_matching import RegressionSeriesMatch, RegressionSeriesMatchStatus

if TYPE_CHECKING:
    from tpstudio.orchestration.graph_adapter import GraphSeriesData


class RegressionModelTechnicalStatus(str, Enum):
    EVALUABLE = "evaluable"
    NOT_EVALUABLE = "not_evaluable"
    INSUFFICIENT_RANK = "insufficient_rank"
    ILL_CONDITIONED = "ill_conditioned"
    NONFINITE_DATA = "nonfinite_data"
    UNSUPPORTED_MATCH = "unsupported_match"


@dataclass(frozen=True, slots=True)
class RegressionModelAnalysis:
    regression_id: str
    series_id: str | None
    method: RegressionMethod
    degree: int | None
    match_status: RegressionSeriesMatchStatus
    coefficients: tuple[float, ...] | None
    predicted_y_values: tuple[float, ...] | None
    x_center: float | None
    x_scale: float | None
    matrix_rank: int | None
    condition_number: float | None
    technical_status: RegressionModelTechnicalStatus
    diagnostics: tuple[str, ...]
    requires_human_review: bool


def _empty(
    regression: RegressionObservation,
    match: RegressionSeriesMatch,
    status: RegressionModelTechnicalStatus,
    diagnostic: str,
    series_id: str | None = None,
) -> RegressionModelAnalysis:
    return RegressionModelAnalysis(
        regression.regression_id, series_id, regression.method, regression.degree,
        match.status, None, None, None, None, None, None, status, (diagnostic,), True,
    )


def _finite(values: tuple[float, ...] | None) -> bool:
    return values is not None and bool(values) and all(math.isfinite(value) for value in values)


def _design(x: tuple[float, ...], degree: int) -> tuple[np.ndarray, float, float] | None:
    values = np.asarray(x, dtype=float)
    with np.errstate(over="ignore", invalid="ignore"):
        center = float(np.mean(values))
        scale = float(np.max(np.abs(values - center)))
    if not math.isfinite(center) or not math.isfinite(scale) or scale == 0.0:
        return None
    z = np.asarray([(value - center) / scale for value in x], dtype=float)
    if degree == 1:
        matrix = np.column_stack((z, np.ones(len(z))))
    else:
        matrix = np.column_stack((z * z, z, np.ones(len(z))))
    return matrix, center, scale


def _center_and_scale(x: tuple[float, ...]) -> tuple[float, float]:
    values = np.asarray(x, dtype=float)
    with np.errstate(over="ignore", invalid="ignore"):
        center = float(np.mean(values))
        scale = float(np.max(np.abs(values - center)))
    return center, scale


def _convert_coefficients(
    normalized: np.ndarray, degree: int, center: float, scale: float
) -> tuple[float, ...] | None:
    try:
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            if degree == 1:
                alpha, beta = (np.float64(value) for value in normalized)
                result = (alpha / np.float64(scale), beta - alpha * np.float64(center) / np.float64(scale))
            else:
                alpha, beta, gamma = (np.float64(value) for value in normalized)
                scale_squared = np.float64(scale) * np.float64(scale)
                center_value = np.float64(center)
                result = (
                    alpha / scale_squared,
                    beta / np.float64(scale) - 2.0 * alpha * center_value / scale_squared,
                    alpha * center_value * center_value / scale_squared
                    - beta * center_value / np.float64(scale)
                    + gamma,
                )
        values = tuple(float(value) for value in result)
    except (FloatingPointError, OverflowError, ValueError):
        return None
    return values if all(math.isfinite(value) for value in values) else None


def _predictions(matrix: np.ndarray, normalized: np.ndarray) -> tuple[float, ...] | None:
    try:
        values = tuple(float(value) for value in matrix @ normalized)
    except (FloatingPointError, ValueError, OverflowError):
        return None
    return values if all(math.isfinite(value) for value in values) else None


def analyze_regression_model(
    regression: RegressionObservation,
    match: RegressionSeriesMatch,
    series: "GraphSeriesData | None",
) -> RegressionModelAnalysis:
    """Reconstruct one model from a safe, oriented measured series."""
    from tpstudio.orchestration.graph_adapter import GraphSeriesStatus

    if not isinstance(regression.method, RegressionMethod) or regression.degree is None:
        return _empty(regression, match, RegressionModelTechnicalStatus.NOT_EVALUABLE, "methode_et_degre_incompatibles")
    if regression.method is RegressionMethod.NUMPY_POLYFIT:
        method_degree_valid = regression.degree in (1, 2)
    else:
        method_degree_valid = regression.method is RegressionMethod.SCIPY_LINREGRESS and regression.degree == 1
    if not method_degree_valid:
        return _empty(regression, match, RegressionModelTechnicalStatus.NOT_EVALUABLE, "methode_et_degre_incompatibles")
    if regression.technical_status is not RegressionTechnicalStatus.EXTRACTED:
        return _empty(regression, match, RegressionModelTechnicalStatus.NOT_EVALUABLE, "regression_non_evaluable")
    if match.status not in (
        RegressionSeriesMatchStatus.EXACT,
        RegressionSeriesMatchStatus.NUMERIC_EQUIVALENT,
    ):
        diagnostic = (
            "orientation_inversee_non_exploitable"
            if match.status is RegressionSeriesMatchStatus.REVERSED
            else "appariement_non_exploitable"
        )
        return _empty(regression, match, RegressionModelTechnicalStatus.UNSUPPORTED_MATCH, diagnostic, match.matched_series_id)
    if series is None or match.matched_series_id != series.series_id:
        return _empty(regression, match, RegressionModelTechnicalStatus.NOT_EVALUABLE, "serie_appariee_absente", match.matched_series_id)
    if series.technical_status is not GraphSeriesStatus.EXTRACTED:
        return _empty(regression, match, RegressionModelTechnicalStatus.NOT_EVALUABLE, "serie_numerique_non_exploitable", series.series_id)
    x, y = series.x_values, series.y_values
    if not _finite(x) or not _finite(y) or len(x) != len(y):
        return _empty(regression, match, RegressionModelTechnicalStatus.NONFINITE_DATA, "donnees_numeriques_absentes_ou_non_finies", series.series_id)
    assert x is not None and y is not None
    minimum_points = regression.degree + 1
    if len(x) < minimum_points:
        return _empty(regression, match, RegressionModelTechnicalStatus.INSUFFICIENT_RANK, "trop_peu_de_points", series.series_id)
    center, scale = _center_and_scale(x)
    if not math.isfinite(center):
        return _empty(regression, match, RegressionModelTechnicalStatus.NONFINITE_DATA, "centre_x_non_fini", series.series_id)
    if not math.isfinite(scale):
        return _empty(regression, match, RegressionModelTechnicalStatus.NONFINITE_DATA, "echelle_x_non_finie", series.series_id)
    if scale == 0.0:
        return _empty(regression, match, RegressionModelTechnicalStatus.INSUFFICIENT_RANK, "etendue_des_abscisses_insuffisante", series.series_id)
    design_data = _design(x, regression.degree)
    if design_data is None:
        return _empty(regression, match, RegressionModelTechnicalStatus.INSUFFICIENT_RANK, "etendue_des_abscisses_insuffisante", series.series_id)
    matrix, center, scale = design_data
    rank = int(np.linalg.matrix_rank(matrix))
    expected_rank = regression.degree + 1
    if rank < expected_rank:
        return RegressionModelAnalysis(
            regression.regression_id, series.series_id, regression.method, regression.degree,
            match.status, None, None, center, scale, rank, None,
            RegressionModelTechnicalStatus.INSUFFICIENT_RANK, ("rang_insuffisant",), True,
        )
    try:
        condition = float(np.linalg.cond(matrix))
    except (FloatingPointError, ValueError, np.linalg.LinAlgError):
        condition = math.inf
    if not math.isfinite(condition) or condition > MAX_QUADRATIC_CONDITION:
        return RegressionModelAnalysis(
            regression.regression_id, series.series_id, regression.method, regression.degree,
            match.status, None, None, center, scale, rank, condition,
            RegressionModelTechnicalStatus.ILL_CONDITIONED, ("conditionnement_insuffisant",), True,
        )
    try:
        normalized, _, _, _ = np.linalg.lstsq(matrix, np.asarray(y, dtype=float), rcond=None)
    except (FloatingPointError, ValueError, np.linalg.LinAlgError):
        return RegressionModelAnalysis(
            regression.regression_id, series.series_id, regression.method, regression.degree,
            match.status, None, None, center, scale, rank, condition,
            RegressionModelTechnicalStatus.NOT_EVALUABLE, ("ajustement_impossible",), True,
        )
    if not np.all(np.isfinite(normalized)):
        return RegressionModelAnalysis(
            regression.regression_id, series.series_id, regression.method, regression.degree,
            match.status, None, None, center, scale, rank, condition,
            RegressionModelTechnicalStatus.NONFINITE_DATA, ("coefficients_non_finies",), True,
        )
    predictions = _predictions(matrix, normalized)
    if predictions is None:
        return RegressionModelAnalysis(
            regression.regression_id, series.series_id, regression.method, regression.degree,
            match.status, None, None, center, scale, rank, condition,
            RegressionModelTechnicalStatus.NONFINITE_DATA, ("modele_non_fini",), True,
        )
    coefficients = _convert_coefficients(normalized, regression.degree, center, scale)
    if coefficients is None:
        return RegressionModelAnalysis(
            regression.regression_id, series.series_id, regression.method, regression.degree,
            match.status, None, predictions, center, scale, rank, condition,
            RegressionModelTechnicalStatus.NONFINITE_DATA,
            ("coefficients_originaux_non_representables_de_facon_finie",), True,
        )
    return RegressionModelAnalysis(
        regression.regression_id, series.series_id, regression.method, regression.degree,
        match.status, tuple(coefficients), predictions, center, scale, rank, condition,
        RegressionModelTechnicalStatus.EVALUABLE,
        ("modele_affine_reconstruit" if regression.degree == 1 else "modele_quadratique_reconstruit",),
        False,
    )


def analyze_regression_models(
    regressions: tuple[RegressionObservation, ...],
    matches: tuple[RegressionSeriesMatch, ...],
    series: tuple["GraphSeriesData", ...],
) -> tuple[RegressionModelAnalysis, ...]:
    by_id = {item.series_id: item for item in series}
    return tuple(
        analyze_regression_model(regression, match, by_id.get(match.matched_series_id))
        for regression, match in zip(regressions, matches)
    )
