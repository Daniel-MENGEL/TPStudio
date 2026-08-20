"""Pure application, discovery, removal, and explicit writing of annotations."""

from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re

import nbformat
from nbformat.notebooknode import NotebookNode

from .model import (
    AnnotatedNotebookResult, AnnotationOptions, AnnotationPlacement,
    AnnotationPlan, ExistingAnnotationMode, ExistingNotebookAnnotation,
    StudentSummaryAnnotation,
)
from .rendering import render_notebook_annotation


_BLOCK = re.compile(
    r"(?P<prefix>\n\n)?<!-- TPSTUDIO:BEGIN annotation_id=(?P<id>[^\s>]+) -->.*?"
    r"<!-- TPSTUDIO:END annotation_id=(?P=id) -->",
    re.DOTALL,
)


def _dedicated_ids(cell: NotebookNode) -> tuple[str, ...]:
    metadata = cell.get("metadata", {}).get("tpstudio", {})
    if metadata.get("annotation") is not True:
        return ()
    values = metadata.get("annotation_ids")
    if isinstance(values, list) and all(isinstance(item, str) and item for item in values):
        return tuple(values)
    value = metadata.get("annotation_id")
    return (value,) if isinstance(value, str) and value else ()


def find_tpstudio_annotations(notebook: NotebookNode) -> tuple[ExistingNotebookAnnotation, ...]:
    if not isinstance(notebook, NotebookNode):
        raise TypeError("Le notebook doit être un NotebookNode.")
    found: list[ExistingNotebookAnnotation] = []
    for index, cell in enumerate(notebook.cells):
        for annotation_id in _dedicated_ids(cell):
            found.append(ExistingNotebookAnnotation(annotation_id, index, ExistingAnnotationMode.DEDICATED_CELL))
        if cell.get("cell_type") != "markdown":
            continue
        source = cell.get("source", "")
        for match in _BLOCK.finditer(source):
            found.append(ExistingNotebookAnnotation(
                match.group("id"), index, ExistingAnnotationMode.APPENDED_BLOCK,
                match.start(), match.end(),
            ))
    return tuple(found)


def remove_tpstudio_annotations(
    notebook: NotebookNode,
    *,
    annotation_ids: tuple[str, ...] | None = None,
) -> NotebookNode:
    if not isinstance(notebook, NotebookNode):
        raise TypeError("Le notebook doit être un NotebookNode.")
    selected = None if annotation_ids is None else set(tuple(annotation_ids))
    result = deepcopy(notebook)
    cells = []
    for cell in result.cells:
        dedicated = _dedicated_ids(cell)
        if dedicated and (selected is None or any(item in selected for item in dedicated)):
            if selected is None or all(item in selected for item in dedicated):
                continue
        if cell.get("cell_type") == "markdown":
            source = cell.get("source", "")
            def replace(match):
                return "" if selected is None or match.group("id") in selected else match.group(0)
            cell.source = _BLOCK.sub(replace, source)
        cells.append(cell)
    result.cells = cells
    return result


def _annotation_cell(annotation, *, include_id: bool = True) -> NotebookNode:
    cell = nbformat.v4.new_markdown_cell(render_notebook_annotation(annotation))
    if include_id:
        cell.id = "tpstudio-" + hashlib.sha256(
            annotation.annotation_id.encode("utf-8")
        ).hexdigest()[:24]
    else:
        cell.pop("id", None)
    cell.metadata["tpstudio"] = {
        "annotation": True,
        "annotation_id": annotation.annotation_id,
        "annotation_ids": [annotation.annotation_id],
        "kind": annotation.kind.value,
        "audience": annotation.audience.value,
    }
    return cell


def _student_summary_cell(items: tuple[StudentSummaryAnnotation, ...]) -> NotebookNode:
    """Render untargeted student feedback as one compact, replaceable cell."""
    labels = {
        "blocking": "Problème",
        "important": "À vérifier",
        "attention": "À vérifier",
        "info": "Remarque",
    }
    lines = ["## Points à compléter ou à revoir", ""]
    for item in items:
        severity = labels[item.severity.value]
        lines.append(f"- **{severity}** — {item.message}")
    cell = nbformat.v4.new_markdown_cell("\n".join(lines) + "\n")
    cell.metadata["tpstudio"] = {
        "annotation": True,
        "kind": "student_summary",
        "summary_id": "tpstudio-student-summary",
        "annotation_ids": [item.annotation_id for item in items],
    }
    cell.id = "tpstudio-student-summary"
    return cell


def apply_annotation_plan(
    notebook: NotebookNode,
    plan: AnnotationPlan,
    options: AnnotationOptions | None = None,
) -> AnnotatedNotebookResult:
    if not isinstance(notebook, NotebookNode):
        raise TypeError("Le notebook doit être un NotebookNode.")
    if type(plan) is not AnnotationPlan:
        raise TypeError("Le plan est invalide.")
    options = AnnotationOptions() if options is None else options
    if type(options) is not AnnotationOptions:
        raise TypeError("Les options sont invalides.")
    original = deepcopy(notebook)
    existing = find_tpstudio_annotations(notebook)
    if options.replace_existing_tpstudio_annotations:
        working = remove_tpstudio_annotations(notebook)
        removed = tuple(item.annotation_id for item in existing)
    else:
        working = deepcopy(notebook)
        removed = ()
    if plan.summary_annotations:
        summary = _student_summary_cell(plan.summary_annotations)
        insert_at = 1 if (
            working.cells
            and working.cells[0].get("cell_type") == "markdown"
            and str(working.cells[0].get("source", "")).lstrip().startswith("#")
        ) else 0
        working.cells.insert(insert_at, summary)
    existing_ids = {item.annotation_id for item in find_tpstudio_annotations(working)}
    pending = tuple(item for item in plan.annotations if item.annotation_id not in existing_ids)
    include_cell_ids = not (
        working.get("nbformat") == 4
        and working.get("nbformat_minor", 0) < 5
    )

    logical_cells = [cell for cell in working.cells if not _dedicated_ids(cell)]
    if len(logical_cells) <= max((item.target_cell_index for item in pending), default=-1):
        invalid = tuple(item.annotation_id for item in pending if item.target_cell_index >= len(logical_cells))
        pending = tuple(item for item in pending if item.annotation_id not in invalid)
    else:
        invalid = ()

    appended = [item for item in pending if item.placement is AnnotationPlacement.APPEND_TO_MARKDOWN]
    for item in appended:
        target = logical_cells[item.target_cell_index]
        target.source = target.source + "\n\n" + render_notebook_annotation(item)

    adjacent = [item for item in pending if item.placement is not AnnotationPlacement.APPEND_TO_MARKDOWN]
    by_target: dict[int, list] = {}
    for item in adjacent:
        by_target.setdefault(item.target_cell_index, []).append(item)
    for target_index in sorted(by_target, reverse=True):
        target_cell = logical_cells[target_index]
        physical = next(index for index, cell in enumerate(working.cells) if cell is target_cell)
        before = [item for item in by_target[target_index] if item.placement is AnnotationPlacement.BEFORE_CELL]
        after = [item for item in by_target[target_index] if item.placement is AnnotationPlacement.AFTER_CELL]
        working.cells[physical:physical] = [
            _annotation_cell(item, include_id=include_cell_ids) for item in before
        ]
        physical += len(before) + 1
        working.cells[physical:physical] = [
            _annotation_cell(item, include_id=include_cell_ids) for item in after
        ]

    applied = tuple(item.annotation_id for item in pending)
    changed = working != original
    return AnnotatedNotebookResult(
        working, applied, invalid, removed, len(original.cells), len(working.cells), changed,
    )


def write_annotated_notebook(
    result: AnnotatedNotebookResult,
    output_path: Path,
    *,
    overwrite: bool = False,
    source_path: Path | None = None,
) -> Path:
    if type(result) is not AnnotatedNotebookResult:
        raise TypeError("Le résultat annoté est invalide.")
    if not isinstance(output_path, Path):
        raise TypeError("Le chemin de sortie doit être un pathlib.Path.")
    if type(overwrite) is not bool:
        raise TypeError("overwrite doit être booléen.")
    if source_path is not None and not isinstance(source_path, Path):
        raise TypeError("Le chemin source doit être un pathlib.Path.")
    if source_path is not None and paths_refer_to_same_location(source_path, output_path):
        raise ValueError("Le notebook source ne peut pas être le chemin de sortie.")
    if output_path.exists() and not overwrite:
        raise FileExistsError("Le notebook de sortie existe déjà.")
    nbformat.validate(result.notebook)
    nbformat.write(result.notebook, output_path)
    return output_path


def paths_refer_to_same_location(first: Path, second: Path) -> bool:
    """Return whether two paths designate the same canonical location."""
    if not isinstance(first, Path) or not isinstance(second, Path):
        raise TypeError("Les chemins doivent être des pathlib.Path.")
    return first.resolve() == second.resolve()


def default_annotated_notebook_name(source_name: str) -> str:
    if not isinstance(source_name, str) or not source_name.strip():
        raise ValueError("Le nom source ne peut pas être vide.")
    stem = source_name[:-6] if source_name.lower().endswith(".ipynb") else source_name
    return f"{stem}-correction.ipynb"
