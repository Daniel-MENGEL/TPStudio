"""Read-only loading and technical inspection of notebook copies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import nbformat
from nbformat.notebooknode import NotebookNode


def _required_text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} doit être une chaîne.")
    if not value.strip():
        raise ValueError(f"{name} ne peut pas être vide.")


@dataclass(frozen=True, slots=True)
class NotebookCopySource:
    source_id: str
    display_name: str
    path: Path

    def __post_init__(self) -> None:
        _required_text(self.source_id, "source_id")
        _required_text(self.display_name, "display_name")
        if not isinstance(self.path, Path):
            raise TypeError("path doit être un pathlib.Path explicite.")

    def __repr__(self) -> str:
        return (
            f"NotebookCopySource(source_id={self.source_id!r}, "
            f"display_name={self.display_name!r}, path=<private>)"
        )


@dataclass(frozen=True, slots=True)
class NotebookTechnicalInspection:
    notebook_valid: bool
    nbformat_version: str
    cell_count: int
    markdown_cell_count: int
    code_cell_count: int
    raw_cell_count: int
    executed_code_cell_count: int
    unexecuted_code_cell_indices: tuple[int, ...]
    error_output_cell_indices: tuple[int, ...]
    question_mark_code_cell_indices: tuple[int, ...]
    empty_code_cell_indices: tuple[int, ...]
    stored_output_cell_indices: tuple[int, ...]
    kernel_name: str | None
    has_attachments: bool
    referenced_external_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.notebook_valid) is not bool or type(self.has_attachments) is not bool:
            raise TypeError("Les indicateurs techniques doivent être booléens.")
        if not isinstance(self.nbformat_version, str):
            raise TypeError("La version nbformat doit être une chaîne.")
        for name in (
            "cell_count", "markdown_cell_count", "code_cell_count", "raw_cell_count",
            "executed_code_cell_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} doit être un entier positif ou nul.")
        for name in (
            "unexecuted_code_cell_indices", "error_output_cell_indices",
            "question_mark_code_cell_indices", "empty_code_cell_indices",
            "stored_output_cell_indices", "referenced_external_paths",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))


_PATH_PATTERN = re.compile(
    r"(?<![\w])(?:[A-Za-z]:[\\/]|\.?\.?/)[^\s'\"()]+|[^\s'\"()]+\.(?:csv|txt|dat|png|jpg|jpeg)"
)


def load_notebook_copy(source: NotebookCopySource) -> NotebookNode:
    """Load one notebook without execution, normalization, or writing."""

    if type(source) is not NotebookCopySource:
        raise TypeError("La source doit être exactement un NotebookCopySource.")
    try:
        return nbformat.read(source.path, as_version=nbformat.NO_CONVERT)
    except Exception as exc:
        raise ValueError("Le fichier fourni n'est pas un notebook valide.") from exc


def inspect_notebook(notebook: NotebookNode) -> NotebookTechnicalInspection:
    if not isinstance(notebook, NotebookNode):
        raise TypeError("Le notebook doit être chargé en mémoire.")
    cells = tuple(notebook.get("cells", ()))
    unexecuted: list[int] = []
    errors: list[int] = []
    placeholders: list[int] = []
    empty: list[int] = []
    outputs: list[int] = []
    paths: list[str] = []
    executed = 0
    has_attachments = False
    for index, cell in enumerate(cells):
        source = cell.get("source", "")
        if not isinstance(source, str):
            source = "".join(source)
        has_attachments = has_attachments or bool(cell.get("attachments"))
        for match in _PATH_PATTERN.finditer(source):
            value = match.group(0)
            if value not in paths:
                paths.append(value)
        if cell.get("cell_type") != "code":
            continue
        if not source.strip():
            empty.append(index)
        if "?" in source:
            placeholders.append(index)
        execution_count = cell.get("execution_count")
        if execution_count is None:
            unexecuted.append(index)
        else:
            executed += 1
        cell_outputs = tuple(cell.get("outputs", ()))
        if cell_outputs:
            outputs.append(index)
        if any(output.get("output_type") == "error" for output in cell_outputs):
            errors.append(index)
    metadata = notebook.get("metadata", {})
    kernel = metadata.get("kernelspec", {}).get("name")
    major = notebook.get("nbformat", "")
    minor = notebook.get("nbformat_minor", "")
    return NotebookTechnicalInspection(
        True,
        f"{major}.{minor}",
        len(cells),
        sum(cell.get("cell_type") == "markdown" for cell in cells),
        sum(cell.get("cell_type") == "code" for cell in cells),
        sum(cell.get("cell_type") == "raw" for cell in cells),
        executed,
        tuple(unexecuted),
        tuple(errors),
        tuple(placeholders),
        tuple(empty),
        tuple(outputs),
        kernel if isinstance(kernel, str) else None,
        has_attachments,
        tuple(paths),
    )
