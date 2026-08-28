"""Safe matching of extracted regressions to measured graph series.

This module compares provenance and already-reconstructible values only.  It
never executes a notebook or a regression routine.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
import math
from typing import TYPE_CHECKING

from nbformat.notebooknode import NotebookNode

from tpstudio.regression import RegressionObservation, RegressionTechnicalStatus

if TYPE_CHECKING:
    from tpstudio.orchestration.graph_adapter import GraphSeriesData


class RegressionSeriesMatchStatus(str, Enum):
    EXACT = "exact"
    NUMERIC_EQUIVALENT = "numeric_equivalent"
    REVERSED = "reversed"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"
    NOT_EVALUABLE = "not_evaluable"


@dataclass(frozen=True, slots=True)
class RegressionSeriesMatch:
    regression_id: str
    matched_series_id: str | None
    status: RegressionSeriesMatchStatus
    evidence: str
    candidate_series_ids: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()
    requires_human_review: bool = True


def _canonical(expression: str | None) -> str | None:
    if expression is None:
        return None
    try:
        return ast.dump(ast.parse(expression, mode="eval").body, annotate_fields=True, include_attributes=False)
    except SyntaxError:
        return "".join(expression.split()).lower().replace("np.", "")


def _names(expression: str | None) -> tuple[str, ...]:
    if not expression:
        return ()
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return ()
    return tuple(sorted({node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id != "np"}))


def _binding_signature(
    notebook: NotebookNode,
    cell_index: int,
    position: tuple[int, int] | None,
    expression: str | None,
) -> tuple[tuple[str, str], ...] | None:
    """Return source identities of names, without storing full environments."""
    if position is None:
        return None
    signatures: dict[str, str] = {}
    for index, cell in enumerate(notebook.cells[:cell_index + 1]):
        if cell.cell_type != "code":
            continue
        try:
            tree = ast.parse(cell.source)
        except SyntaxError:
            continue
        for statement in tree.body:
            if index == cell_index and (getattr(statement, "lineno", 0), getattr(statement, "col_offset", 0)) >= position:
                break
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                signatures[target.id] = f"{index}:{getattr(statement, 'lineno', 0)}:{ast.dump(statement.value, include_attributes=False)}"
    return tuple((name, signatures.get(name, "<unbound>")) for name in _names(expression))


def _compatible_bindings(
    notebook: NotebookNode,
    regression: RegressionObservation,
    series: GraphSeriesData,
    series_position: tuple[int, int] | None,
    reversed_match: bool = False,
) -> bool:
    regression_x = _binding_signature(notebook, regression.cell_index_snapshot, regression.source_location, regression.x_expression)
    regression_y = _binding_signature(notebook, regression.cell_index_snapshot, regression.source_location, regression.y_expression)
    series_x = _binding_signature(notebook, series.cell_index_snapshot, series_position, series.x_expression)
    series_y = _binding_signature(notebook, series.cell_index_snapshot, series_position, series.y_expression)
    if reversed_match:
        series_x, series_y = series_y, series_x
    return (
        regression_x is not None and series_x is not None
        and regression_y is not None and series_y is not None
        and regression_x == series_x and regression_y == series_y
    )


def _close(left: tuple[float, ...] | None, right: tuple[float, ...] | None) -> bool:
    if left is None or right is None or len(left) != len(right):
        return False
    scale = max((abs(value) for value in (*left, *right)), default=0.0)
    tolerance = 8.0 * math.ulp(scale if scale else 1.0)
    return all(abs(a - b) <= tolerance for a, b in zip(left, right))


def _values(
    notebook: NotebookNode,
    cell_index: int,
    position: tuple[int, int] | None,
    x_expression: str | None,
    y_expression: str | None,
) -> tuple[tuple[tuple[float, ...], tuple[float, ...]] | None, tuple[str, ...]]:
    from tpstudio.orchestration.graph_adapter import resolve_expression_at_position_with_details
    if position is None or x_expression is None or y_expression is None:
        return None, ("<position_inconnue>",)
    x, x_tainted = resolve_expression_at_position_with_details(notebook, cell_index, position, x_expression)
    y, y_tainted = resolve_expression_at_position_with_details(notebook, cell_index, position, y_expression)
    return ((x, y) if x is not None and y is not None else None), tuple(sorted(set(x_tainted) | set(y_tainted)))


def _candidate_evidence(
    notebook: NotebookNode,
    regression: RegressionObservation,
    series: GraphSeriesData,
) -> tuple[tuple[str, bool], ...]:
    from tpstudio.orchestration.graph_adapter import series_source_position
    series_position = series_source_position(notebook, series)
    direct_expression = (
        _canonical(regression.x_expression) == _canonical(series.x_expression)
        and _canonical(regression.y_expression) == _canonical(series.y_expression)
    )
    reversed_expression = (
        _canonical(regression.x_expression) == _canonical(series.y_expression)
        and _canonical(regression.y_expression) == _canonical(series.x_expression)
    )
    regression_values, regression_tainted = _values(
        notebook, regression.cell_index_snapshot, regression.source_location,
        regression.x_expression, regression.y_expression,
    )
    series_values, series_tainted = _values(
        notebook, series.cell_index_snapshot, series_position,
        series.x_expression, series.y_expression,
    )
    if regression_tainted or series_tainted:
        return ()
    compatible = _compatible_bindings(notebook, regression, series, series_position)
    reversed_compatible = _compatible_bindings(notebook, regression, series, series_position, True)
    evidence: list[tuple[str, bool]] = []
    if direct_expression and compatible and (
        regression_values is None or series_values is None or (
            _close(regression_values[0], series_values[0]) and _close(regression_values[1], series_values[1])
        )
    ):
        evidence.append(("expressions_et_bindings_identiques", False))
    if reversed_expression and reversed_compatible and (
        regression_values is None or series_values is None or (
            _close(regression_values[0], series_values[1]) and _close(regression_values[1], series_values[0])
        )
    ):
        evidence.append(("expressions_inversees", True))
    if regression_values is not None and series_values is not None:
        if _close(regression_values[0], series_values[0]) and _close(regression_values[1], series_values[1]):
            evidence.append(("valeurs_numeriques_equivalentes", False))
        if _close(regression_values[0], series_values[1]) and _close(regression_values[1], series_values[0]):
            evidence.append(("valeurs_numeriques_inversees", True))
    return tuple(evidence)


def match_regression_to_series(
    notebook: NotebookNode,
    regression: RegressionObservation,
    series: tuple[GraphSeriesData, ...],
) -> RegressionSeriesMatch:
    from tpstudio.orchestration.graph_adapter import GraphSeriesRole, series_source_position
    candidates = tuple(item for item in series if item.role is GraphSeriesRole.MEASURED)
    candidate_ids = tuple(item.series_id for item in candidates)
    if regression.technical_status is not RegressionTechnicalStatus.EXTRACTED:
        return RegressionSeriesMatch(
            regression.regression_id, None, RegressionSeriesMatchStatus.NOT_EVALUABLE,
            "regression_non_evaluable", candidate_ids, ("regression_non_evaluable",), True,
        )
    matches: list[tuple[GraphSeriesData, str, bool, int]] = []
    tainted_names: set[str] = set()
    for item in candidates:
        evidence = _candidate_evidence(notebook, regression, item)
        if not evidence:
            regression_values, regression_tainted = _values(
                notebook, regression.cell_index_snapshot, regression.source_location,
                regression.x_expression, regression.y_expression,
            )
            series_values, series_tainted = _values(
                notebook, item.cell_index_snapshot, series_source_position(notebook, item),
                item.x_expression, item.y_expression,
            )
            tainted_names.update(regression_tainted)
            tainted_names.update(series_tainted)
            continue
        for kind, reversed_match in evidence:
            matches.append((item, kind, reversed_match, 2 if kind.startswith("expressions") else 1))
    if matches:
        best_rank = max(item[3] for item in matches)
        best = [item for item in matches if item[3] == best_rank]
        unique_interpretations = {(item[0].series_id, item[1], item[2]) for item in best}
        if len(unique_interpretations) != 1:
            # The same measured variables may legitimately be plotted again
            # later for another pedagogical purpose.  Prefer a uniquely nearest
            # cell, but preserve ambiguity for duplicate plots at equal
            # distance or for direct/reversed alternatives within one series.
            distances = {
                item[0].series_id: abs(
                    item[0].cell_index_snapshot - regression.cell_index_snapshot
                )
                for item in best
            }
            nearest_distance = min(distances.values())
            nearest_ids = {
                series_id
                for series_id, distance in distances.items()
                if distance == nearest_distance
            }
            nearest = [item for item in best if item[0].series_id in nearest_ids]
            nearest_interpretations = {
                (item[0].series_id, item[2]) for item in nearest
            }
            if len(nearest_ids) == 1 and len(nearest_interpretations) == 1:
                best = nearest
                unique_interpretations = {
                    (item[0].series_id, item[1], item[2]) for item in best
                }
            else:
                return RegressionSeriesMatch(
                    regression.regression_id, None, RegressionSeriesMatchStatus.AMBIGUOUS,
                    "plusieurs_interpretations_directes_ou_inversees",
                    tuple(sorted({item[0].series_id for item in best})),
                    ("plusieurs_interpretations_possibles",), True,
                )
        if len(unique_interpretations) != 1:
            return RegressionSeriesMatch(
                regression.regression_id, None, RegressionSeriesMatchStatus.AMBIGUOUS,
                "plusieurs_interpretations_directes_ou_inversees",
                tuple(sorted({item[0].series_id for item in best})),
                ("plusieurs_interpretations_possibles",), True,
            )
        item, kind, reversed_match, _ = best[0]
        status = RegressionSeriesMatchStatus.REVERSED if reversed_match else (
            RegressionSeriesMatchStatus.EXACT if kind.startswith("expressions") else RegressionSeriesMatchStatus.NUMERIC_EQUIVALENT
        )
        return RegressionSeriesMatch(regression.regression_id, item.series_id, status, kind, candidate_ids, (), False)
    regression_values, regression_tainted = _values(
        notebook, regression.cell_index_snapshot, regression.source_location,
        regression.x_expression, regression.y_expression,
    )
    all_candidate_values_known = bool(candidates)
    for item in candidates:
        candidate_values, candidate_tainted = _values(
            notebook, item.cell_index_snapshot, series_source_position(notebook, item),
            item.x_expression, item.y_expression,
        )
        if candidate_values is None or candidate_tainted:
            all_candidate_values_known = False
    no_candidate_is_certain = not candidates and regression_values is not None and not regression_tainted
    status = (
        RegressionSeriesMatchStatus.UNMATCHED
        if no_candidate_is_certain or (regression_values is not None and not regression_tainted and all_candidate_values_known)
        else RegressionSeriesMatchStatus.NOT_EVALUABLE
    )
    diagnostics = (
        ("variable_modifiee_par_operation_non_resoluble:" + ",".join(sorted(tainted_names)),)
        if tainted_names else ()
    )
    evidence = "etat_temporel_incertain" if tainted_names else "aucune_serie_compatible"
    return RegressionSeriesMatch(regression.regression_id, None, status, evidence, candidate_ids, diagnostics, True)


def match_regressions_to_series(
    notebook: NotebookNode,
    regressions: tuple[RegressionObservation, ...],
    series: tuple[GraphSeriesData, ...],
) -> tuple[RegressionSeriesMatch, ...]:
    return tuple(match_regression_to_series(notebook, item, series) for item in regressions)
