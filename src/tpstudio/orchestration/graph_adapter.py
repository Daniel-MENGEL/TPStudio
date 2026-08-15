"""Static observation of saved graph code; no image analysis or execution."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
import math
from numbers import Real

from nbformat.notebooknode import NotebookNode

from tpstudio.projects import GraphExpectation
from tpstudio.notebooks import NotebookBindingResolution


MAX_SERIES_POINTS = 10_000
MAX_INTEGER_BITS = 1_024
MAX_EXPONENT = 1_000


class GraphCheckStatus(str, Enum):
    MATCHES = "matches"
    INVERTED = "inverted"
    MISSING = "missing"
    NOT_EVALUABLE = "not_evaluable"


class GraphSeriesRole(str, Enum):
    MEASURED = "measured"
    FIT = "fit"
    THEORY = "theory"
    UNKNOWN = "unknown"


class GraphSeriesStatus(str, Enum):
    EXTRACTED = "extracted"
    NOT_EVALUABLE = "not_evaluable"
    INVALID = "invalid"


class GraphSeriesSource(str, Enum):
    STATIC_CODE = "static_code"
    SAVED_OUTPUT = "saved_output"


@dataclass(frozen=True, slots=True)
class GraphObservation:
    production_id: str
    cell_index: int
    x_expression: str | None
    y_expression: str | None
    x_label: str | None
    y_label: str | None
    regression_present: bool
    regression_x_expression: str | None
    regression_y_expression: str | None
    slope_target: str | None
    figure_output_present: bool
    analysis_limitations: tuple[str, ...] = ()
    series_data: tuple["GraphSeriesData", ...] = ()


@dataclass(frozen=True, slots=True)
class GraphSeriesData:
    """Small, safe numeric projection of one plotted series.

    Values are tuples rather than NumPy objects so the projection is immutable,
    deterministic and does not require executing notebook code.
    """

    series_id: str
    cell_id: str | None
    cell_index_snapshot: int
    role: GraphSeriesRole
    x_expression: str
    y_expression: str
    x_values: tuple[float, ...] | None
    y_values: tuple[float, ...] | None
    n_points: int
    x_range: tuple[float, float] | None
    y_range: tuple[float, float] | None
    technical_status: GraphSeriesStatus
    source_kind: GraphSeriesSource
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphEvaluation:
    expectation: GraphExpectation
    observation: GraphObservation | None
    orientation_status: GraphCheckStatus
    label_status: GraphCheckStatus
    regression_status: GraphCheckStatus
    slope_relation_status: GraphCheckStatus
    evaluable: bool
    reasons: tuple[str, ...] = ()

    @property
    def has_issues(self) -> bool:
        return not self.evaluable or any(
            status is not GraphCheckStatus.MATCHES
            for status in (self.orientation_status, self.label_status, self.regression_status, self.slope_relation_status)
        )


def _text(node: ast.AST, source: str) -> str:
    return (ast.get_source_segment(source, node) or "").strip()


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def _plot_call_name(node: ast.Call) -> str:
    if not isinstance(node.func, ast.Attribute):
        return ""
    if not isinstance(node.func.value, ast.Name):
        return ""
    if node.func.value.id not in {"plt", "ax", "axes"}:
        return ""
    return node.func.attr if node.func.attr in {"plot", "scatter", "errorbar"} else ""


_SAFE_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sqrt": math.sqrt,
    "fabs": math.fabs,
    "abs": abs,
    "radians": math.radians,
    "deg2rad": math.radians,
}


def _as_array(value: object) -> tuple[float, ...] | None:
    if isinstance(value, tuple) and all(isinstance(item, float) for item in value):
        return value
    return None


def _number(value: object) -> float | None:
    if isinstance(value, Real) and not isinstance(value, bool):
        if isinstance(value, int) and value.bit_length() > MAX_INTEGER_BITS:
            return None
        try:
            result = float(value)
        except (OverflowError, ValueError):
            return None
        return result if math.isfinite(result) else None
    return None


def _apply_binary(left: object, right: object, operator: ast.operator) -> object | None:
    l_number, r_number = _number(left), _number(right)
    l_array, r_array = _as_array(left), _as_array(right)
    if l_array is not None or r_array is not None:
        if l_array is None:
            if l_number is None or r_array is None:
                return None
            l_array = tuple(l_number for _ in r_array)
        if r_array is None:
            if r_number is None:
                return None
            r_array = tuple(r_number for _ in l_array)
        if len(l_array) != len(r_array):
            return None
        values = [_apply_binary(a, b, operator) for a, b in zip(l_array, r_array)]
        return tuple(value for value in values if isinstance(value, float)) if all(isinstance(value, float) for value in values) else None
    if l_number is None or r_number is None:
        return None
    try:
        if isinstance(operator, ast.Add): return l_number + r_number
        if isinstance(operator, ast.Sub): return l_number - r_number
        if isinstance(operator, ast.Mult): return l_number * r_number
        if isinstance(operator, ast.Div): return l_number / r_number
        if isinstance(operator, ast.Pow):
            if abs(r_number) > MAX_EXPONENT:
                return None
            return l_number ** r_number
    except (ArithmeticError, OverflowError):
        return None
    return None


def _safe_value(node: ast.AST, bindings: dict[str, object]) -> object | None:
    if isinstance(node, ast.Constant):
        return _number(node.value)
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if isinstance(node, (ast.List, ast.Tuple)):
        if len(node.elts) > MAX_SERIES_POINTS:
            return None
        values = [_safe_value(item, bindings) for item in node.elts]
        if not values or not all(isinstance(value, float) for value in values):
            return None
        return tuple(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _safe_value(node.operand, bindings)
        if isinstance(value, tuple):
            return tuple(-item if isinstance(node.op, ast.USub) else item for item in value)
        number = _number(value)
        if number is not None:
            return -number if isinstance(node.op, ast.USub) else number
        return None
    if isinstance(node, ast.BinOp):
        return _apply_binary(_safe_value(node.left, bindings), _safe_value(node.right, bindings), node.op)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "np":
        return math.pi if node.attr == "pi" else None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "np":
            return None
        name = node.func.attr
        if name == "array" and len(node.args) == 1 and not node.keywords:
            value = _safe_value(node.args[0], bindings)
            return value if _as_array(value) is not None else None
        function = _SAFE_FUNCTIONS.get(name)
        if function is None or len(node.args) != 1 or node.keywords:
            return None
        value = _safe_value(node.args[0], bindings)
        if isinstance(value, tuple):
            try:
                return tuple(float(function(item)) for item in value)
            except (ArithmeticError, ValueError):
                return None
        number = _number(value)
        if number is None:
            return None
        try:
            return float(function(number))
        except (ArithmeticError, ValueError):
            return None
    return None


def _series_role(label: str | None) -> GraphSeriesRole:
    normalized = (label or "").lower()
    if any(word in normalized for word in ("mesure", "point", "data")):
        return GraphSeriesRole.MEASURED
    if any(word in normalized for word in ("régression", "regression", "fit", "ajustement")):
        return GraphSeriesRole.FIT
    if any(word in normalized for word in ("théorie", "theorie", "theory")):
        return GraphSeriesRole.THEORY
    return GraphSeriesRole.UNKNOWN


def _range(values: tuple[float, ...] | None) -> tuple[float, float] | None:
    return (min(values), max(values)) if values else None


def _extract_series(
    tree: ast.AST,
    source: str,
    bindings: dict[str, object],
    cell_index: int,
    cell_id: str | None,
) -> tuple[GraphSeriesData, ...]:
    result: list[GraphSeriesData] = []
    for statement in tree.body:
        call = statement.value if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call) else None
        if call is None or not _plot_call_name(call) or len(call.args) < 2:
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                value = _safe_value(statement.value, bindings)
                if value is None:
                    bindings.pop(statement.targets[0].id, None)
                else:
                    bindings[statement.targets[0].id] = value
            continue
        x_expression = _text(call.args[0], source)
        y_expression = _text(call.args[1], source)
        x_values = _as_array(_safe_value(call.args[0], bindings))
        y_values = _as_array(_safe_value(call.args[1], bindings))
        label = None
        for keyword in call.keywords:
            if keyword.arg == "label" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                label = keyword.value.value
        diagnostics: list[str] = []
        if x_values is None or y_values is None:
            status = GraphSeriesStatus.NOT_EVALUABLE
            diagnostics.append("expression_numerique_non_supportee")
            n_points = 0
        elif len(x_values) != len(y_values):
            status = GraphSeriesStatus.INVALID
            diagnostics.append("longueurs_x_y_incompatibles")
            n_points = min(len(x_values), len(y_values))
        elif not x_values:
            status = GraphSeriesStatus.INVALID
            diagnostics.append("serie_vide")
            n_points = 0
        else:
            status = GraphSeriesStatus.EXTRACTED
            n_points = len(x_values)
        result.append(GraphSeriesData(
            f"cell-{cell_index}-series-{len(result) + 1}", cell_id, cell_index,
            _series_role(label), x_expression, y_expression,
            x_values, y_values, n_points, _range(x_values), _range(y_values),
            status, GraphSeriesSource.STATIC_CODE, tuple(diagnostics),
        ))
    return tuple(result)


def observe_saved_graph(
    notebook: NotebookNode,
    resolution: NotebookBindingResolution,
) -> GraphObservation | None:
    if not resolution.resolved or resolution.cell is None:
        return None
    cell = notebook.cells[resolution.cell.index]
    if cell.cell_type != "code":
        return None
    source = cell.source
    bindings: dict[str, object] = {}
    # Reconstruct only simple assignments from cells preceding the graph.  The
    # walk is deliberately chronological: a later reassignment cannot affect
    # an earlier graph cell.
    for previous in notebook.cells[: resolution.cell.index]:
        if previous.cell_type != "code":
            continue
        try:
            previous_tree = ast.parse(previous.source)
        except SyntaxError:
            continue
        for statement in previous_tree.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            if not isinstance(target, ast.Name):
                continue
            value = _safe_value(statement.value, bindings)
            if value is None:
                bindings.pop(target.id, None)
            else:
                bindings[target.id] = value
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return GraphObservation(
            resolution.production_id, resolution.cell.index, None, None, None, None,
            False, None, None, None, bool(cell.get("outputs")), ("syntaxe_non_reconnue",), (),
        )
    x = y = x_label = y_label = regression_x = regression_y = slope = None
    regression = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if isinstance(node.value, ast.Call) and _call_name(node.value) in ("polyfit", "linregress"):
                slope = node.targets[0].id
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if _plot_call_name(node) and len(node.args) >= 2 and x is None:
            x, y = _text(node.args[0], source), _text(node.args[1], source)
        elif name == "xlabel" and node.args and isinstance(node.args[0], ast.Constant):
            x_label = node.args[0].value if isinstance(node.args[0].value, str) else None
        elif name == "ylabel" and node.args and isinstance(node.args[0], ast.Constant):
            y_label = node.args[0].value if isinstance(node.args[0].value, str) else None
        elif name in ("polyfit", "linregress"):
            regression = True
            if len(node.args) >= 2:
                regression_x, regression_y = _text(node.args[0], source), _text(node.args[1], source)
    figure = any(
        output.get("output_type") in ("display_data", "execute_result")
        and any(key.startswith("image/") for key in output.get("data", {}))
        for output in cell.get("outputs", ())
    )
    limitations = () if x and y else ("expressions_de_trace_non_reconnues",)
    series_data = _extract_series(
        tree, source, bindings, resolution.cell.index, cell.get("id")
    )
    if series_data:
        x, y = series_data[0].x_expression, series_data[0].y_expression
    series_limitations = tuple(
        diagnostic
        for series in series_data
        for diagnostic in series.diagnostics
    )
    limitations = tuple(dict.fromkeys((*limitations, *series_limitations)))
    return GraphObservation(
        resolution.production_id, resolution.cell.index, x, y, x_label, y_label,
        regression, regression_x, regression_y, slope, figure, limitations, series_data,
    )


def _normalized(value: str | None) -> str:
    return "".join((value or "").split()).lower().replace("np.", "")


def evaluate_saved_graph(expectation: GraphExpectation, observation: GraphObservation | None) -> GraphEvaluation:
    if observation is None:
        missing = GraphCheckStatus.MISSING
        return GraphEvaluation(expectation, None, missing, missing, missing, missing, False, ("graphe_absent",))
    expected_x, expected_y = _normalized(expectation.x_expression), _normalized(expectation.y_expression)
    actual_x, actual_y = _normalized(observation.x_expression), _normalized(observation.y_expression)
    if not actual_x or not actual_y:
        orientation = GraphCheckStatus.NOT_EVALUABLE
    elif (actual_x, actual_y) == (expected_x, expected_y):
        orientation = GraphCheckStatus.MATCHES
    elif (actual_x, actual_y) == (expected_y, expected_x):
        orientation = GraphCheckStatus.INVERTED
    else:
        orientation = GraphCheckStatus.NOT_EVALUABLE
    x_labels = {_normalized(item) for item in expectation.accepted_x_labels}
    y_labels = {_normalized(item) for item in expectation.accepted_y_labels}
    actual_labels = (_normalized(observation.x_label), _normalized(observation.y_label))
    if actual_labels[0] in x_labels and actual_labels[1] in y_labels:
        labels = GraphCheckStatus.MATCHES
    elif actual_labels[0] in y_labels and actual_labels[1] in x_labels:
        labels = GraphCheckStatus.INVERTED
    elif not all(actual_labels):
        labels = GraphCheckStatus.NOT_EVALUABLE
    else:
        labels = GraphCheckStatus.NOT_EVALUABLE
    if not observation.regression_present:
        regression = GraphCheckStatus.MISSING
    else:
        rx, ry = _normalized(observation.regression_x_expression), _normalized(observation.regression_y_expression)
        regression = (
            GraphCheckStatus.MATCHES if (rx, ry) == (expected_x, expected_y)
            else GraphCheckStatus.INVERTED if (rx, ry) == (expected_y, expected_x)
            else GraphCheckStatus.NOT_EVALUABLE
        )
    slope_status = GraphCheckStatus.MATCHES if observation.slope_target else GraphCheckStatus.NOT_EVALUABLE
    evaluable = orientation is not GraphCheckStatus.NOT_EVALUABLE
    return GraphEvaluation(
        expectation, observation, orientation, labels, regression, slope_status, evaluable,
        observation.analysis_limitations,
    )
