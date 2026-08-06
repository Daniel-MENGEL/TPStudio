"""Conservative observation of scalar values without executing student code."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import re

from nbformat.notebooknode import NotebookNode

from tpstudio.expectations import ExpectedQuantity, ScientificProductionSpec
from tpstudio.notebooks import NotebookBindingResolution
from tpstudio.reasoning import extract_expected_quantity


class ObservedValueSource(str, Enum):
    MARKDOWN_TEXT = "markdown_text"
    CODE_LITERAL = "code_literal"
    TEXT_OUTPUT = "text_output"
    EXECUTE_RESULT = "execute_result"
    DISPLAY_TEXT = "display_text"


@dataclass(frozen=True, slots=True)
class ObservedScalarValue:
    production_id: str
    source: ObservedValueSource
    value: Decimal
    unit: str | None
    cell_index: int
    raw_text: str
    start: int | None = None
    end: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.production_id, str) or not self.production_id.strip():
            raise ValueError("production_id ne peut pas être vide.")
        if type(self.source) is not ObservedValueSource:
            raise TypeError("La provenance est invalide.")
        if type(self.value) is not Decimal:
            raise TypeError("La valeur doit être un Decimal.")
        if type(self.cell_index) is not int or self.cell_index < 0:
            raise ValueError("L'indice de cellule est invalide.")
        if not isinstance(self.raw_text, str):
            raise TypeError("La preuve brute doit être une chaîne.")
        if (self.start is None) != (self.end is None):
            raise ValueError("Les offsets sont simultanément présents ou absents.")


@dataclass(frozen=True, slots=True)
class ObservedValueDetection:
    production: ScientificProductionSpec
    candidates: tuple[ObservedScalarValue, ...]
    selected: ObservedScalarValue | None
    saved_output_may_be_stale: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.production, ScientificProductionSpec):
            raise TypeError("La production est invalide.")
        candidates = tuple(self.candidates)
        if any(item.production_id != self.production.id for item in candidates):
            raise ValueError("Une candidate vise une autre production.")
        object.__setattr__(self, "candidates", candidates)
        canonical = _select_by_priority(candidates)
        if self.selected is not canonical:
            raise ValueError("La sélection doit suivre la politique canonique.")
        if type(self.saved_output_may_be_stale) is not bool:
            raise TypeError("L'indicateur d'obsolescence doit être booléen.")

    @property
    def absent(self) -> bool:
        return not self.candidates

    @property
    def unique(self) -> bool:
        return self.selected is not None

    @property
    def ambiguous(self) -> bool:
        return bool(self.candidates) and self.selected is None

    def __iter__(self) -> Iterator[ObservedScalarValue]:
        return iter(self.candidates)


def _decimal(node: ast.AST) -> Decimal | None:
    sign = Decimal(1)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        sign = Decimal(-1) if isinstance(node.op, ast.USub) else Decimal(1)
        node = node.operand
    if not isinstance(node, ast.Constant) or isinstance(node.value, bool):
        return None
    if not isinstance(node.value, (int, float)):
        return None
    return sign * Decimal(str(node.value))


def code_literal_values(
    source: str,
    production_id: str,
    cell_index: int,
    symbols: tuple[str, ...] | None = None,
) -> tuple[ObservedScalarValue, ...]:
    """Return only simple named assignments to scalar numeric literals."""

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ()
    observed: list[ObservedScalarValue] = []
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name):
            continue
        target = targets[0].id
        if symbols is not None and target not in symbols:
            continue
        value = _decimal(statement.value)
        if value is None:
            continue
        raw = ast.get_source_segment(source, statement) or ""
        observed.append(ObservedScalarValue(
            production_id, ObservedValueSource.CODE_LITERAL, value, None,
            cell_index, raw,
        ))
    return tuple(observed)


_NUMBER = re.compile(r"(?<![\w.])[+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?")


def _text_values(text: str, production_id: str, cell_index: int, source: ObservedValueSource):
    values = []
    for match in _NUMBER.finditer(text):
        try:
            value = Decimal(match.group(0).replace(",", "."))
        except InvalidOperation:
            continue
        values.append(ObservedScalarValue(
            production_id, source, value, None, cell_index, match.group(0),
            match.start(), match.end(),
        ))
    return tuple(values)


_SOURCE_PRIORITY = {
    ObservedValueSource.MARKDOWN_TEXT: 0,
    ObservedValueSource.CODE_LITERAL: 1,
    ObservedValueSource.TEXT_OUTPUT: 2,
    ObservedValueSource.EXECUTE_RESULT: 2,
    ObservedValueSource.DISPLAY_TEXT: 2,
}


def _select_by_priority(
    candidates: tuple[ObservedScalarValue, ...],
) -> ObservedScalarValue | None:
    if not candidates:
        return None
    first_rank = min(_SOURCE_PRIORITY[item.source] for item in candidates)
    prioritized = tuple(
        item for item in candidates if _SOURCE_PRIORITY[item.source] == first_rank
    )
    scientific_identities = {(item.value, item.unit) for item in prioritized}
    return prioritized[0] if len(scientific_identities) == 1 else None


def _quantity_text_values(
    text: str,
    expectation: ExpectedQuantity,
    cell_index: int,
    source: ObservedValueSource,
) -> tuple[ObservedScalarValue, ...]:
    detection = extract_expected_quantity(text, expectation)
    return tuple(
        ObservedScalarValue(
            expectation.production_id,
            source,
            observation.value,
            observation.unit,
            cell_index,
            observation.matched_text,
            observation.start,
            observation.end,
        )
        for observation in detection.observations
    )


def detect_observed_values(
    notebook: NotebookNode,
    resolution: NotebookBindingResolution,
    production: ScientificProductionSpec,
    *,
    expectation: ExpectedQuantity | None = None,
    associated_resolutions: tuple[NotebookBindingResolution, ...] = (),
    saved_output_may_be_stale: bool = False,
    inspect_saved_outputs: bool = True,
) -> ObservedValueDetection:
    if type(inspect_saved_outputs) is not bool:
        raise TypeError("inspect_saved_outputs doit être un booléen exact.")
    if expectation is not None and expectation.production_id != production.id:
        raise ValueError("L'attente quantitative vise une autre production.")
    associated_resolutions = tuple(associated_resolutions)
    if not resolution.resolved or resolution.cell is None:
        return ObservedValueDetection(production, (), None, saved_output_may_be_stale)
    cell = notebook.cells[resolution.cell.index]
    text = resolution.text or ""
    candidates: list[ObservedScalarValue] = []
    code_resolutions = []
    if cell.cell_type == "code":
        code_resolutions.append(resolution)
    else:
        candidates.extend(
            _quantity_text_values(
                text, expectation, resolution.cell.index,
                ObservedValueSource.MARKDOWN_TEXT,
            )
            if expectation is not None
            else _text_values(
                text, production.id, resolution.cell.index,
                ObservedValueSource.MARKDOWN_TEXT,
            )
        )
    for associated in associated_resolutions:
        if associated.resolved and associated.cell is not None:
            associated_cell = notebook.cells[associated.cell.index]
            if associated_cell.cell_type == "code" and associated not in code_resolutions:
                code_resolutions.append(associated)
    symbols = expectation.symbols if expectation is not None else None
    for code_resolution in code_resolutions:
        assert code_resolution.cell is not None
        code_text = code_resolution.text or ""
        candidates.extend(code_literal_values(
            code_text, production.id, code_resolution.cell.index, symbols
        ))
    if inspect_saved_outputs:
        for code_resolution in code_resolutions:
            assert code_resolution.cell is not None
            output_cell = notebook.cells[code_resolution.cell.index]
            for output in output_cell.get("outputs", ()):
                output_type = output.get("output_type")
                if output_type == "stream":
                    output_text = output.get("text", "")
                    source = ObservedValueSource.TEXT_OUTPUT
                elif output_type in ("execute_result", "display_data"):
                    output_text = output.get("data", {}).get("text/plain", "")
                    source = (
                        ObservedValueSource.EXECUTE_RESULT
                        if output_type == "execute_result" else ObservedValueSource.DISPLAY_TEXT
                    )
                else:
                    continue
                if isinstance(output_text, list):
                    output_text = "".join(output_text)
                if isinstance(output_text, str):
                    observed_output = (
                        _quantity_text_values(
                            output_text, expectation, code_resolution.cell.index, source
                        )
                        if expectation is not None
                        else _text_values(
                            output_text, production.id, code_resolution.cell.index, source
                        )
                    )
                    if expectation is not None and not observed_output:
                        observed_output = _text_values(
                            output_text, production.id, code_resolution.cell.index, source
                        )
                    candidates.extend(observed_output)
    values = tuple(candidates)
    return ObservedValueDetection(
        production, values, _select_by_priority(values), saved_output_may_be_stale
    )
