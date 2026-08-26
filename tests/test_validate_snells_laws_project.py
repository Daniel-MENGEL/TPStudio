from pathlib import Path

import nbformat
import pytest

from scripts.validate_snells_laws_project import (
    format_snells_laws_validation_report,
    validate_snells_laws_notebooks,
)
from tpstudio.projects import snells_laws_teacher_project


def _synthetic_statement(path: Path, *, omit: str | None = None, duplicate: str | None = None) -> None:
    project = snells_laws_teacher_project()
    markers = tuple(dict.fromkeys(binding.selector.value for binding in project.notebook_binding_plan.bindings))
    cells = []
    for marker in markers:
        if marker == omit:
            continue
        cell = nbformat.v4.new_code_cell(marker)
        cells.append(cell)
        if marker == duplicate:
            cells.append(nbformat.v4.new_code_cell(marker))
    nbformat.write(nbformat.v4.new_notebook(cells=cells), path)


def test_conforming_synthetic_statement_resolves_all_bindings(tmp_path: Path) -> None:
    path = tmp_path / "statement.ipynb"
    _synthetic_statement(path)
    result = validate_snells_laws_notebooks(path)
    assert result.all_resolved
    assert len(result.resolved_binding_ids) == 24
    assert len(result.covered_production_ids) == 24


def test_missing_section_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "statement.ipynb"
    marker = "### Conclusion / bilan"
    _synthetic_statement(path, omit=marker)
    result = validate_snells_laws_notebooks(path)
    assert set(result.missing_binding_ids) == {"final-conclusion-response", "method-limitations-response"}


def test_ambiguous_binding_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "statement.ipynb"
    _synthetic_statement(path, duplicate="# Vérification graphique")
    result = validate_snells_laws_notebooks(path)
    assert result.ambiguous_binding_ids == ("regression-graph-cell",)


def test_moved_cells_keep_textual_association(tmp_path: Path) -> None:
    path = tmp_path / "statement.ipynb"
    _synthetic_statement(path)
    notebook = nbformat.read(path, as_version=4)
    notebook.cells = tuple(reversed(notebook.cells))
    nbformat.write(notebook, path)
    assert validate_snells_laws_notebooks(path).all_resolved


def test_file_without_extension_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "statement"
    _synthetic_statement(path)
    assert validate_snells_laws_notebooks(path).all_resolved


def test_invalid_notebook_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "invalid.ipynb"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(Exception):
        validate_snells_laws_notebooks(path)


def test_validation_neither_executes_code_nor_modifies_file(tmp_path: Path) -> None:
    path = tmp_path / "statement.ipynb"
    _synthetic_statement(path)
    notebook = nbformat.read(path, as_version=4)
    notebook.cells.insert(0, nbformat.v4.new_code_cell("raise RuntimeError('must not run')"))
    nbformat.write(notebook, path)
    before = path.read_bytes()
    result = validate_snells_laws_notebooks(path)
    assert result.all_resolved
    assert path.read_bytes() == before


def test_report_is_deterministic_and_contains_counts_only(tmp_path: Path) -> None:
    path = tmp_path / "statement.ipynb"
    _synthetic_statement(path)
    result = validate_snells_laws_notebooks(path)
    assert format_snells_laws_validation_report(result) == format_snells_laws_validation_report(result)
    assert "Bindings résolus : 24" in format_snells_laws_validation_report(result)
