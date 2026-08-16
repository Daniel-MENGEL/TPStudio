"""Structural association of reconstructed models with plotted curves.

Labels are deliberately not used as categorical tie-breakers: a FIT and an
UNKNOWN curve with equally strong structural evidence remain ambiguous.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from collections import Counter
from enum import Enum
from typing import TYPE_CHECKING

from nbformat.notebooknode import NotebookNode

from tpstudio.regression import RegressionObservation
from tpstudio.regression_model import RegressionModelAnalysis
if TYPE_CHECKING:
    from tpstudio.orchestration.graph_adapter import GraphSeriesData


class RegressionPlotMatchStatus(str, Enum):
    STRUCTURAL_MATCH = "structural_match"
    NUMERIC_CANDIDATE = "numeric_candidate"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"
    NOT_EVALUABLE = "not_evaluable"


@dataclass(frozen=True, slots=True)
class RegressionPlotMatch:
    regression_id: str
    model_series_id: str | None
    plotted_series_id: str | None
    status: RegressionPlotMatchStatus
    evidence: str
    candidate_series_ids: tuple[str, ...]
    plotted_x_expression: str | None = None
    plotted_y_expression: str | None = None
    diagnostics: tuple[str, ...] = ()
    requires_human_review: bool = True


def _canonical(node: ast.AST | str) -> str:
    if isinstance(node, str):
        node = ast.parse(node, mode="eval").body
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def _loaded_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}


def _statements(notebook: NotebookNode):
    for cell_index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue
        try:
            tree = ast.parse(cell.source)
        except SyntaxError:
            continue
        for statement in tree.body:
            yield cell_index, statement


def _target_roots(target: ast.AST) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(name for item in target.elts for name in _target_roots(item))
    if isinstance(target, (ast.Subscript, ast.Attribute)):
        root = target.value
        while isinstance(root, (ast.Subscript, ast.Attribute)):
            root = root.value
        return (root.id,) if isinstance(root, ast.Name) else ()
    return ()


def _plot_tainted_names(
    notebook: NotebookNode, regression: RegressionObservation, plot_position: tuple[int, int]
) -> set[str]:
    tainted: set[str] = set()
    for cell_index, statement in _statements(notebook):
        position = (getattr(statement, "lineno", 0), getattr(statement, "col_offset", 0))
        if cell_index < regression.cell_index_snapshot or (
            cell_index == regression.cell_index_snapshot and position <= regression.source_location
        ):
            continue
        if cell_index > plot_position[0] or (cell_index == plot_position[0] and position >= plot_position[1:]):
            break
        if isinstance(statement, ast.AugAssign):
            tainted.update(_target_roots(statement.target))
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets = statement.targets if isinstance(statement, ast.Assign) else (statement.target,)
            names = {name for target in targets for name in _target_roots(target)}
            if names & set(regression.target_names):
                tainted.update(names & set(regression.target_names))
    return tainted


def _expression_environment(notebook: NotebookNode, plot_position: tuple[int, int]) -> dict[str, ast.AST]:
    environment: dict[str, ast.AST] = {}
    for cell_index, statement in _statements(notebook):
        position = (getattr(statement, "lineno", 0), getattr(statement, "col_offset", 0))
        if cell_index > plot_position[0] or (cell_index == plot_position[0] and position >= plot_position[1:]):
            break
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                environment[target.id] = statement.value
            else:
                for name in _target_roots(target):
                    environment.pop(name, None)
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value is not None:
            environment[statement.target.id] = statement.value
        elif isinstance(statement, ast.AugAssign):
            for name in _target_roots(statement.target):
                environment.pop(name, None)
    return environment


def _resolve_expression(node: ast.AST, environment: dict[str, ast.AST], seen: set[str] | None = None) -> ast.AST:
    seen = set() if seen is None else seen
    if isinstance(node, ast.Name) and node.id in environment and node.id not in seen:
        return _resolve_expression(environment[node.id], environment, seen | {node.id})
    return node


def _coefficient_ref(node: ast.AST, regression: RegressionObservation) -> int | None:
    if len(regression.target_names) == 2 and isinstance(node, ast.Name):
        try:
            return regression.target_names.index(node.id)
        except ValueError:
            return None
    if len(regression.target_names) == 1 and isinstance(node, ast.Subscript):
        if isinstance(node.value, ast.Name) and node.value.id == regression.target_names[0] and isinstance(node.slice, ast.Constant):
            return node.slice.value if type(node.slice.value) is int else None
    return None


def _term_role(node: ast.AST, regression: RegressionObservation, x_canonical: str) -> tuple[int, int] | None:
    coefficient = _coefficient_ref(node, regression)
    if coefficient is not None:
        return coefficient, 0
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mult):
        return None
    factors = (node.left, node.right)
    for index, factor in enumerate(factors):
        coefficient = _coefficient_ref(factor, regression)
        if coefficient is None:
            continue
        other = factors[1 - index]
        exponent = 1
        if isinstance(other, ast.BinOp) and isinstance(other.op, ast.Pow) and _canonical(other.left) == x_canonical:
            if isinstance(other.right, ast.Constant) and type(other.right.value) is int:
                exponent = other.right.value
            else:
                return None
        elif _canonical(other) != x_canonical:
            return None
        return coefficient, exponent
    return None


def _flatten_add(node: ast.AST, sign: int = 1) -> list[tuple[ast.AST, int]]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _flatten_add(node.left, sign) + _flatten_add(node.right, sign)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
        return _flatten_add(node.left, sign) + _flatten_add(node.right, -sign)
    return [(node, sign)]


def _polynomial_structure(node: ast.AST, regression: RegressionObservation, x_canonical: str) -> bool:
    expected = ((0, 1), (1, 0)) if regression.degree == 1 else ((0, 2), (1, 1), (2, 0))
    terms: list[tuple[tuple[int, int], int]] = []
    for term, sign in _flatten_add(node):
        role = _term_role(term, regression, x_canonical)
        if role is None:
            return False
        terms.append((role, sign))
    # Preserve both signs and multiplicities.  A set of coefficient roles would
    # incorrectly accept expressions such as ``a*x-b`` or ``a*x+b-b``.
    return Counter(terms) == Counter((role, 1) for role in expected)


def _structural_evidence(
    notebook: NotebookNode, regression: RegressionObservation, series: "GraphSeriesData"
) -> str | None:
    from tpstudio.orchestration.graph_adapter import series_source_position
    position = series_source_position(notebook, series)
    if position is None:
        return None
    if series.cell_index_snapshot < regression.cell_index_snapshot or (
        series.cell_index_snapshot == regression.cell_index_snapshot
        and position <= regression.source_location
    ):
        return None
    tainted = _plot_tainted_names(notebook, regression, (series.cell_index_snapshot, position[0], position[1]))
    if tainted:
        return None
    try:
        x_node = ast.parse(series.x_expression, mode="eval").body
        y_node = ast.parse(series.y_expression, mode="eval").body
    except SyntaxError:
        return None
    environment = _expression_environment(notebook, (series.cell_index_snapshot, position[0], position[1]))
    y_node = _resolve_expression(y_node, environment)
    x_canonical = _canonical(x_node)
    if isinstance(y_node, ast.Call) and isinstance(y_node.func, ast.Attribute):
        if (
            isinstance(y_node.func.value, ast.Name)
            and y_node.func.value.id == "np"
            and y_node.func.attr == "polyval"
            and len(y_node.args) == 2
            and regression.degree in (1, 2)
            and len(regression.target_names) == 1
            and isinstance(y_node.args[0], ast.Name)
            and y_node.args[0].id == regression.target_names[0]
            and _canonical(y_node.args[1]) == x_canonical
        ):
            return "np_polyval_structurel"
    if _polynomial_structure(y_node, regression, x_canonical):
        return "polynome_cibles_structurel"
    return None


def match_regression_to_plots(
    notebook: NotebookNode,
    regression: RegressionObservation,
    model: RegressionModelAnalysis,
    plotted_series: tuple["GraphSeriesData", ...],
) -> RegressionPlotMatch:
    from tpstudio.orchestration.graph_adapter import GraphSeriesRole
    if model.normalized_coefficients is None:
        return RegressionPlotMatch(regression.regression_id, model.series_id, None, RegressionPlotMatchStatus.NOT_EVALUABLE, "modele_non_evaluable", (), requires_human_review=True)
    candidates = tuple(item for item in plotted_series if item.role in (GraphSeriesRole.FIT, GraphSeriesRole.UNKNOWN))
    structural = tuple(item for item in candidates if _structural_evidence(notebook, regression, item))
    if len(structural) == 1:
        item = structural[0]
        return RegressionPlotMatch(regression.regression_id, model.series_id, item.series_id, RegressionPlotMatchStatus.STRUCTURAL_MATCH, "courbe_dependante_des_cibles_du_modele", (item.series_id,), item.x_expression, item.y_expression, requires_human_review=False)
    if len(structural) > 1:
        return RegressionPlotMatch(regression.regression_id, model.series_id, None, RegressionPlotMatchStatus.AMBIGUOUS, "plusieurs_courbes_structurelles", tuple(item.series_id for item in structural), requires_human_review=True)
    numeric = tuple(item for item in candidates if item.technical_status.value == "extracted")
    if len(numeric) == 1:
        item = numeric[0]
        return RegressionPlotMatch(regression.regression_id, model.series_id, item.series_id, RegressionPlotMatchStatus.NUMERIC_CANDIDATE, "courbe_numerique_candidate", (item.series_id,), item.x_expression, item.y_expression, requires_human_review=True)
    if len(numeric) > 1:
        return RegressionPlotMatch(regression.regression_id, model.series_id, None, RegressionPlotMatchStatus.AMBIGUOUS, "plusieurs_courbes_numeriques", tuple(item.series_id for item in numeric), requires_human_review=True)
    return RegressionPlotMatch(regression.regression_id, model.series_id, None, RegressionPlotMatchStatus.UNMATCHED, "aucune_courbe_modele", (), requires_human_review=True)


def match_regressions_to_plots(
    notebook: NotebookNode,
    regressions: tuple[RegressionObservation, ...],
    models: tuple[RegressionModelAnalysis, ...],
    plotted_series: tuple["GraphSeriesData", ...],
) -> tuple[RegressionPlotMatch, ...]:
    return tuple(match_regression_to_plots(notebook, regression, model, plotted_series) for regression, model in zip(regressions, models))
