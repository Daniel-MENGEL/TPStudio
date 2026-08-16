"""Numerical comparison of a reconstructed model with a plotted series."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
import math

import numpy as np

from tpstudio.regression_model import RegressionModelAnalysis, evaluate_regression_model
from tpstudio.regression import RegressionObservation
from tpstudio.regression_plot_matching import RegressionPlotMatch, RegressionPlotMatchStatus


class RegressionPlotConsistencyStatus(str, Enum):
    CONSISTENT = "consistent"
    NUMERICALLY_EQUIVALENT = "numerically_equivalent"
    PLOTTED_MODEL_MISMATCH = "plotted_model_mismatch"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"
    NOT_EVALUABLE = "not_evaluable"


class RegressionPlotConsistencyTechnicalStatus(str, Enum):
    EVALUABLE = "evaluable"
    NOT_EVALUABLE = "not_evaluable"


class RegressionPlotComparisonSource(str, Enum):
    EXTRACTED_PLOT_VALUES = "extracted_plot_values"
    RECONSTRUCTED_STRUCTURAL_PLOT = "reconstructed_structural_plot"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class RegressionPlotConsistencyAnalysis:
    regression_id: str
    model_series_id: str | None
    plotted_series_id: str | None
    plot_match_status: RegressionPlotMatchStatus
    technical_status: RegressionPlotConsistencyTechnicalStatus
    consistency_status: RegressionPlotConsistencyStatus
    rms_difference: float | None
    max_difference: float | None
    normalized_rms_difference: float | None
    normalized_max_difference: float | None
    n_compared_points: int
    comparison_source: RegressionPlotComparisonSource
    diagnostics: tuple[str, ...]
    requires_human_review: bool


_RTOL = 64.0 * np.finfo(float).eps


def _empty(
    match: RegressionPlotMatch,
    status: RegressionPlotConsistencyStatus,
    diagnostic: str,
) -> RegressionPlotConsistencyAnalysis:
    return RegressionPlotConsistencyAnalysis(
        match.regression_id, match.model_series_id, match.plotted_series_id,
        match.status, RegressionPlotConsistencyTechnicalStatus.NOT_EVALUABLE,
        status, None, None, None, None, 0, RegressionPlotComparisonSource.NONE,
        (diagnostic,), True,
    )


def _plot_environment(notebook, cell_index: int, position: tuple[int, int]) -> dict[str, ast.AST]:
    environment: dict[str, ast.AST] = {}
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue
        if index > cell_index:
            break
        try:
            tree = ast.parse(cell.source)
        except SyntaxError:
            continue
        for statement in tree.body:
            current = (getattr(statement, "lineno", 0), getattr(statement, "col_offset", 0))
            if index == cell_index and current >= position:
                break
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                environment[statement.targets[0].id] = statement.value
            elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value is not None:
                environment[statement.target.id] = statement.value
            elif isinstance(statement, (ast.AugAssign, ast.Assign)):
                for target in (statement.targets if isinstance(statement, ast.Assign) else (statement.target,)):
                    if isinstance(target, ast.Name):
                        environment.pop(target.id, None)
    return environment


def _materialize_expression(
    expression: str,
    model: RegressionModelAnalysis,
    regression: RegressionObservation,
    x_expression: str,
    x_values: tuple[float, ...],
    environment: dict[str, ast.AST],
):
    if model.coefficients is None or not all(math.isfinite(value) for value in model.coefficients):
        return None
    try:
        root = ast.parse(expression, mode="eval").body
        x_root = ast.parse(x_expression, mode="eval").body
    except SyntaxError:
        return None
    x_canonical = ast.dump(x_root, annotate_fields=True, include_attributes=False)
    values = np.asarray(x_values, dtype=float)
    coefficients = tuple(float(value) for value in model.coefficients)
    seen: set[str] = set()

    def evaluate(node: ast.AST):
        if isinstance(node, ast.Name):
            if node.id in seen:
                return None
            if ast.dump(node, annotate_fields=True, include_attributes=False) == x_canonical:
                return values
            if len(regression.target_names) == 2 and node.id in regression.target_names:
                try:
                    return coefficients[regression.target_names.index(node.id)]
                except (ValueError, IndexError):
                    return None
            if node.id in regression.target_names:
                return None
            if node.id in environment:
                seen.add(node.id)
                result = evaluate(environment[node.id])
                seen.remove(node.id)
                return result
            return None
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.Subscript) and len(regression.target_names) == 1:
            if isinstance(node.value, ast.Name) and node.value.id == regression.target_names[0] and isinstance(node.slice, ast.Constant) and type(node.slice.value) is int:
                index = node.slice.value
                return coefficients[index] if 0 <= index < len(coefficients) else None
            return None
        if isinstance(node, ast.BinOp):
            left, right = evaluate(node.left), evaluate(node.right)
            if left is None or right is None:
                return None
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                if isinstance(node.op, ast.Add): result = left + right
                elif isinstance(node.op, ast.Sub): result = left - right
                elif isinstance(node.op, ast.Mult): result = left * right
                elif isinstance(node.op, ast.Div): result = left / right
                elif isinstance(node.op, ast.Pow): result = left ** right
                else: return None
            return result
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "np" and node.func.attr == "polyval" and len(node.args) == 2 and len(regression.target_names) == 1):
                return None
            if not (isinstance(node.args[0], ast.Name) and node.args[0].id == regression.target_names[0]):
                return None
            domain = evaluate(node.args[1])
            if domain is None:
                return None
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                result = np.zeros_like(domain, dtype=float)
                for coefficient in coefficients:
                    result = result * domain + coefficient
            return result
        return None

    result = evaluate(root)
    if result is None:
        return None
    array = np.asarray(result, dtype=float)
    if array.ndim == 0:
        array = np.full(len(values), float(array))
    if array.shape != values.shape or not np.all(np.isfinite(array)):
        return None
    return tuple(float(value) for value in array)


def _metrics(expected: tuple[float, ...], observed: tuple[float, ...]):
    if len(expected) != len(observed) or len(expected) < 2:
        return None
    expected_array = np.asarray(expected, dtype=float)
    observed_array = np.asarray(observed, dtype=float)
    if not np.all(np.isfinite(expected_array)) or not np.all(np.isfinite(observed_array)):
        return None
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        difference = observed_array - expected_array
        absolute_difference = np.abs(difference)
        maximum = float(np.max(absolute_difference))
        if math.isfinite(maximum) and maximum != 0.0:
            normalized_difference = difference / maximum
            rms = float(maximum * np.sqrt(np.mean(normalized_difference * normalized_difference)))
        elif maximum == 0.0:
            rms = 0.0
        else:
            rms = math.inf
    if not math.isfinite(rms) or not math.isfinite(maximum):
        return None
    scale = float(np.max(np.abs(expected_array - np.mean(expected_array))))
    if not math.isfinite(scale) or scale == 0.0:
        scale = float(np.max(np.abs(expected_array)))
    if not math.isfinite(scale) or scale == 0.0:
        scale = float(np.finfo(float).eps)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        normalized_rms = rms / scale
        normalized_maximum = maximum / scale
    if not math.isfinite(normalized_rms) or not math.isfinite(normalized_maximum):
        return None
    magnitude = float(np.max(np.abs(expected_array)))
    atol = _RTOL * (magnitude if magnitude > 0.0 else float(np.finfo(float).eps))
    equivalent = bool(np.allclose(observed_array, expected_array, rtol=_RTOL, atol=atol))
    return rms, maximum, normalized_rms, normalized_maximum, equivalent


def compare_regression_plot(
    model: RegressionModelAnalysis,
    match: RegressionPlotMatch,
    plotted_series: "object | None",
    regression: RegressionObservation | None = None,
    notebook=None,
) -> RegressionPlotConsistencyAnalysis:
    """Compare an already matched model and plotted series without refitting."""
    if match.status is RegressionPlotMatchStatus.AMBIGUOUS:
        return _empty(match, RegressionPlotConsistencyStatus.AMBIGUOUS, "plusieurs_courbes_candidates")
    if match.status is RegressionPlotMatchStatus.UNMATCHED:
        return _empty(match, RegressionPlotConsistencyStatus.UNMATCHED, "aucune_courbe_candidate")
    if match.status is RegressionPlotMatchStatus.NOT_EVALUABLE:
        return _empty(match, RegressionPlotConsistencyStatus.NOT_EVALUABLE, "association_non_evaluable")
    if plotted_series is None:
        return _empty(match, RegressionPlotConsistencyStatus.NOT_EVALUABLE, "courbe_tracee_absente")

    from tpstudio.orchestration.graph_adapter import GraphSeriesStatus
    structural_materialization = (
        match.status is RegressionPlotMatchStatus.STRUCTURAL_MATCH
        and plotted_series.x_values is not None
        and plotted_series.y_values is None
    )
    if plotted_series.technical_status is not GraphSeriesStatus.EXTRACTED and not structural_materialization:
        return _empty(match, RegressionPlotConsistencyStatus.NOT_EVALUABLE, "courbe_tracee_non_exploitable")
    x_values, y_values = plotted_series.x_values, plotted_series.y_values
    if x_values is None or (y_values is not None and len(x_values) != len(y_values)):
        return _empty(match, RegressionPlotConsistencyStatus.NOT_EVALUABLE, "donnees_tracees_absentes_ou_incompatibles")
    if not x_values or any(not math.isfinite(value) for value in x_values) or (y_values is not None and any(not math.isfinite(value) for value in y_values)):
        return _empty(match, RegressionPlotConsistencyStatus.NOT_EVALUABLE, "donnees_tracees_non_finies")
    comparison_source = RegressionPlotComparisonSource.EXTRACTED_PLOT_VALUES
    if y_values is None:
        if match.status is not RegressionPlotMatchStatus.STRUCTURAL_MATCH or regression is None or notebook is None:
            return _empty(match, RegressionPlotConsistencyStatus.NOT_EVALUABLE, "courbe_tracee_non_exploitable")
        from tpstudio.orchestration.graph_adapter import series_source_position
        position = series_source_position(notebook, plotted_series)
        if position is None:
            return _empty(match, RegressionPlotConsistencyStatus.NOT_EVALUABLE, "provenance_courbe_absente")
        environment = _plot_environment(notebook, plotted_series.cell_index_snapshot, position)
        y_values = _materialize_expression(
            plotted_series.y_expression, model, regression, plotted_series.x_expression,
            x_values, environment,
        )
        if y_values is None:
            return _empty(match, RegressionPlotConsistencyStatus.NOT_EVALUABLE, "materialisation_courbe_impossible")
        comparison_source = RegressionPlotComparisonSource.RECONSTRUCTED_STRUCTURAL_PLOT
    expected = evaluate_regression_model(model, x_values)
    if expected is None:
        return _empty(match, RegressionPlotConsistencyStatus.NOT_EVALUABLE, "modele_non_reevaluable")
    metrics = _metrics(expected, y_values)
    if metrics is None:
        return _empty(match, RegressionPlotConsistencyStatus.NOT_EVALUABLE, "comparaison_numerique_impossible")
    rms, maximum, normalized_rms, normalized_maximum, equivalent = metrics
    if equivalent:
        status = (
            RegressionPlotConsistencyStatus.CONSISTENT
            if match.status is RegressionPlotMatchStatus.STRUCTURAL_MATCH
            else RegressionPlotConsistencyStatus.NUMERICALLY_EQUIVALENT
        )
        diagnostic = "courbe_structurelle_et_numeriquement_coherente" if status is RegressionPlotConsistencyStatus.CONSISTENT else "courbe_numeriquement_equivalente"
        review = False
    elif match.status is RegressionPlotMatchStatus.STRUCTURAL_MATCH or plotted_series.role.value == "fit":
        status = RegressionPlotConsistencyStatus.PLOTTED_MODEL_MISMATCH
        diagnostic = "ecart_numerique_superieur_a_la_tolerance"
        review = False
    else:
        status = RegressionPlotConsistencyStatus.NOT_EVALUABLE
        diagnostic = "courbe_unknown_numeriquement_differente"
        review = True
    return RegressionPlotConsistencyAnalysis(
        match.regression_id, match.model_series_id, match.plotted_series_id,
        match.status, RegressionPlotConsistencyTechnicalStatus.EVALUABLE,
        status, rms, maximum, normalized_rms, normalized_maximum, len(expected),
        comparison_source, (diagnostic,), review,
    )


def compare_regression_plots(
    models: tuple[RegressionModelAnalysis, ...],
    matches: tuple[RegressionPlotMatch, ...],
    plotted_series: tuple[object, ...],
    regressions: tuple[RegressionObservation, ...] = (),
    notebook=None,
) -> tuple[RegressionPlotConsistencyAnalysis, ...]:
    models_by_id = {item.regression_id: item for item in models}
    regressions_by_id = {item.regression_id: item for item in regressions}
    series_by_id = {item.series_id: item for item in plotted_series}
    results = []
    for match in matches:
        model = models_by_id.get(match.regression_id)
        if model is None:
            results.append(_empty(match, RegressionPlotConsistencyStatus.NOT_EVALUABLE, "modele_reconstruit_absent"))
        else:
            results.append(compare_regression_plot(
                model, match, series_by_id.get(match.plotted_series_id),
                regressions_by_id.get(match.regression_id), notebook,
            ))
    return tuple(results)
