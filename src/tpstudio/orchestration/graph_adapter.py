"""Static observation of saved graph code; no image analysis or execution."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum

from nbformat.notebooknode import NotebookNode

from tpstudio.projects import GraphExpectation
from tpstudio.notebooks import NotebookBindingResolution


class GraphCheckStatus(str, Enum):
    MATCHES = "matches"
    INVERTED = "inverted"
    MISSING = "missing"
    NOT_EVALUABLE = "not_evaluable"


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
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return GraphObservation(
            resolution.production_id, resolution.cell.index, None, None, None, None,
            False, None, None, None, bool(cell.get("outputs")), ("syntaxe_non_reconnue",),
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
        if name in ("plot", "scatter") and len(node.args) >= 2 and x is None:
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
    return GraphObservation(
        resolution.production_id, resolution.cell.index, x, y, x_label, y_label,
        regression, regression_x, regression_y, slope, figure, limitations,
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
