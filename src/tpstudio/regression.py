"""Static extraction of student regression model calls.

This module records syntax only.  It never calls NumPy/SciPy and deliberately
does not infer whether the requested model is scientifically appropriate.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum


class RegressionMethod(str, Enum):
    NUMPY_POLYFIT = "numpy_polyfit"
    SCIPY_LINREGRESS = "scipy_linregress"


class RegressionTargetKind(str, Enum):
    SINGLE = "single"
    TUPLE = "tuple"
    NONE = "none"


class RegressionTechnicalStatus(str, Enum):
    EXTRACTED = "extracted"
    NOT_EVALUABLE = "not_evaluable"
    UNSUPPORTED_MODEL = "unsupported_model"
    INVALID_TARGETS = "invalid_targets"


@dataclass(frozen=True, slots=True)
class RegressionObservation:
    regression_id: str
    cell_id: str | None
    cell_index_snapshot: int
    method: RegressionMethod
    degree: int | None
    x_expression: str | None
    y_expression: str | None
    target_kind: RegressionTargetKind
    target_names: tuple[str, ...]
    source_location: tuple[int, int]
    technical_status: RegressionTechnicalStatus
    diagnostics: tuple[str, ...] = ()


def _text(node: ast.AST, source: str) -> str:
    return (ast.get_source_segment(source, node) or "").strip()


def _attribute_chain(node: ast.AST) -> tuple[str, ...] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return tuple(reversed(parts))


def _method(node: ast.Call) -> RegressionMethod | None:
    chain = _attribute_chain(node.func)
    if chain == ("np", "polyfit"):
        return RegressionMethod.NUMPY_POLYFIT
    if chain in (("linregress",), ("stats", "linregress"), ("scipy", "stats", "linregress")):
        return RegressionMethod.SCIPY_LINREGRESS
    return None


def _targets(statement: ast.stmt) -> tuple[RegressionTargetKind, tuple[str, ...]]:
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
        return RegressionTargetKind.NONE, ()
    target = statement.targets[0]
    if isinstance(target, ast.Name):
        return RegressionTargetKind.SINGLE, (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)) and all(isinstance(item, ast.Name) for item in target.elts):
        return RegressionTargetKind.TUPLE, tuple(item.id for item in target.elts)
    return RegressionTargetKind.NONE, ()


def _observation(
    statement: ast.stmt,
    call: ast.Call,
    source: str,
    cell_index: int,
    cell_id: str | None,
    ordinal: int,
) -> RegressionObservation:
    method = _method(call)
    assert method is not None
    target_kind, target_names = _targets(statement)
    diagnostics: list[str] = []
    degree: int | None = 1 if method is RegressionMethod.SCIPY_LINREGRESS else None
    status = RegressionTechnicalStatus.EXTRACTED
    if len(call.args) < 2:
        status = RegressionTechnicalStatus.NOT_EVALUABLE
        diagnostics.append("expressions_x_y_absentes")
    x_expression = _text(call.args[0], source) if len(call.args) >= 1 else None
    y_expression = _text(call.args[1], source) if len(call.args) >= 2 else None
    if method is RegressionMethod.NUMPY_POLYFIT:
        if len(call.args) < 3 or not isinstance(call.args[2], ast.Constant) or type(call.args[2].value) is not int:
            status = RegressionTechnicalStatus.NOT_EVALUABLE
            diagnostics.append("degre_polyfit_non_litteral")
        else:
            degree = call.args[2].value
            if degree not in (1, 2):
                status = RegressionTechnicalStatus.UNSUPPORTED_MODEL
                diagnostics.append("degre_polyfit_non_supporte")
    expected_targets = degree + 1 if method is RegressionMethod.NUMPY_POLYFIT and degree in (1, 2) else None
    if target_kind is RegressionTargetKind.TUPLE and expected_targets is not None and len(target_names) != expected_targets:
        status = RegressionTechnicalStatus.INVALID_TARGETS
        diagnostics.append("nombre_de_cibles_incompatible_avec_le_degre")
    if isinstance(statement, ast.Assign) and target_kind is RegressionTargetKind.NONE:
        status = RegressionTechnicalStatus.INVALID_TARGETS
        diagnostics.append("cible_non_supportee")
    return RegressionObservation(
        f"cell-{cell_index}-regression-{ordinal}", cell_id, cell_index, method, degree,
        x_expression, y_expression, target_kind, target_names,
        (getattr(statement, "lineno", 0), getattr(statement, "col_offset", 0)),
        status, tuple(diagnostics),
    )


def extract_regression_observations(
    source: str, cell_index: int, cell_id: str | None = None
) -> tuple[RegressionObservation, ...]:
    """Extract supported regression calls in source order, without execution."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ()
    observations: list[RegressionObservation] = []
    for statement in tree.body:
        call = (
            statement.value
            if isinstance(statement, (ast.Assign, ast.Expr)) and isinstance(statement.value, ast.Call)
            else None
        )
        if call is None:
            continue
        if _method(call) is None:
            continue
        observations.append(_observation(statement, call, source, cell_index, cell_id, len(observations)))
    return tuple(observations)
