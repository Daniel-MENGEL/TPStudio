from dataclasses import FrozenInstanceError
from pathlib import Path

import nbformat
import pytest

from tpstudio.orchestration import (
    NotebookCopySource,
    inspect_notebook,
    load_notebook_copy,
)


def _write(path: Path, notebook) -> bytes:
    nbformat.write(notebook, path)
    return path.read_bytes()


def test_source_is_immutable_and_hides_path_from_repr(tmp_path: Path) -> None:
    source = NotebookCopySource("copy", "Copie", tmp_path / "copy.ipynb")
    assert str(tmp_path) not in repr(source)
    with pytest.raises(FrozenInstanceError):
        source.source_id = "other"  # type: ignore[misc]


@pytest.mark.parametrize("field", ("source_id", "display_name"))
def test_source_rejects_empty_identifiers(tmp_path: Path, field: str) -> None:
    values = {"source_id": "copy", "display_name": "Copie", "path": tmp_path / "n"}
    values[field] = " "
    with pytest.raises(ValueError):
        NotebookCopySource(**values)


def test_load_valid_notebook_without_extension_and_preserve_bytes(tmp_path: Path) -> None:
    path = tmp_path / "notebook"
    before = _write(path, nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("Texte")]))
    loaded = load_notebook_copy(NotebookCopySource("copy", "Copie", path))
    assert len(loaded.cells) == 1
    assert path.read_bytes() == before


def test_invalid_notebook_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_notebook_copy(NotebookCopySource("copy", "Copie", path))


def test_technical_inspection_distinguishes_code_markers_outputs_and_questions() -> None:
    question = nbformat.v4.new_markdown_cell("Quelle relation vérifier ?")
    question.attachments = {"figure.png": {"image/png": "AA=="}}
    code_import = nbformat.v4.new_code_cell("import numpy as np", execution_count=1)
    code_placeholder = nbformat.v4.new_code_cell("n = ?\ndata = './mesures.csv'", execution_count=None)
    code_error = nbformat.v4.new_code_cell("raise ValueError", execution_count=2)
    code_error.outputs = [nbformat.v4.new_output("error", ename="ValueError", evalue="x", traceback=[])]
    empty = nbformat.v4.new_code_cell("", execution_count=None)
    raw = nbformat.v4.new_raw_cell("raw ?")
    notebook = nbformat.v4.new_notebook(
        cells=[question, code_import, code_placeholder, code_error, empty, raw],
        metadata={"kernelspec": {"name": "python3", "display_name": "Python", "language": "python"}},
    )
    result = inspect_notebook(notebook)
    assert result.cell_count == 6
    assert (result.markdown_cell_count, result.code_cell_count, result.raw_cell_count) == (1, 4, 1)
    assert result.executed_code_cell_count == 2
    assert result.unexecuted_code_cell_indices == (2, 4)
    assert result.question_mark_code_cell_indices == (2,)
    assert result.error_output_cell_indices == (3,)
    assert result.stored_output_cell_indices == (3,)
    assert result.empty_code_cell_indices == (4,)
    assert result.kernel_name == "python3" and result.has_attachments
    assert "./mesures.csv" in result.referenced_external_paths


def test_import_without_output_is_not_an_error() -> None:
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_code_cell("import math", execution_count=1),
    ])
    result = inspect_notebook(notebook)
    assert result.error_output_cell_indices == ()
    assert result.stored_output_cell_indices == ()
