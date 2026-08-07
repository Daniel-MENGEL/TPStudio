"""Validation and naming helpers for exported notebooks."""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.notebooknode import NotebookNode

from tpstudio.annotation import find_tpstudio_annotations


def default_export_names(source_name: str) -> tuple[str, str]:
    if not isinstance(source_name, str) or not source_name.strip():
        raise ValueError("Le nom source ne peut pas être vide.")
    filename = Path(source_name).name
    if filename in (".", "..") or not filename:
        raise ValueError("Le nom source doit être un simple nom de fichier.")
    stem = filename[:-6] if filename.lower().endswith(".ipynb") else filename
    if stem.lower().endswith("-correction"):
        base = stem
    else:
        base = f"{stem}-correction"
    return f"{base}.ipynb", f"{base}.html"


def validate_exported_notebook(path: Path):
    from .model import NotebookExportValidation
    try:
        notebook = nbformat.read(path, as_version=nbformat.NO_CONVERT)
        nbformat.validate(notebook)
        annotations = len(find_tpstudio_annotations(notebook))
        return NotebookExportValidation(
            True, len(notebook.cells), annotations,
            f"{notebook.nbformat}.{notebook.nbformat_minor}", (),
        )
    except Exception as exc:
        return NotebookExportValidation(False, 0, 0, "", (str(exc),))


def validate_notebook_object(notebook: NotebookNode):
    from .model import NotebookExportValidation
    try:
        nbformat.validate(notebook)
        return NotebookExportValidation(
            True, len(notebook.cells), len(find_tpstudio_annotations(notebook)),
            f"{notebook.nbformat}.{notebook.nbformat_minor}", (),
        )
    except Exception as exc:
        return NotebookExportValidation(False, 0, 0, "", (str(exc),))
