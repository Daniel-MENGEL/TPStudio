from dataclasses import FrozenInstanceError
from pathlib import Path

import nbformat
import pytest

from tpstudio.orchestration import (
    NotebookCopySource,
    inspect_notebook,
    load_notebook_copy,
    load_and_normalize_notebook,
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


def test_load_repairs_duplicate_or_empty_cell_ids_in_memory_only(tmp_path: Path) -> None:
    import json
    path = tmp_path / "notebook.ipynb"
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("a"), nbformat.v4.new_markdown_cell("b")])
    payload = json.loads(nbformat.writes(notebook))
    payload["cells"][0]["id"] = ""
    payload["cells"][1]["id"] = ""
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()
    loaded = load_notebook_copy(NotebookCopySource("copy", "Copie", path))
    ids = [cell.id for cell in loaded.cells]
    assert len(set(ids)) == 2 and all(identifier.startswith("tpstudio-cell-") for identifier in ids)
    assert path.read_bytes() == before


def test_common_loader_parity_with_web_and_source_list(tmp_path: Path) -> None:
    import json
    from tpstudio.web.model import SelectedCopy
    from tpstudio.web.planning import validate_selected_notebook
    path = tmp_path / "problematic.ipynb"
    payload = {
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "id": "", "source": ["ligne 1\n", "ligne 2"]},
            {"cell_type": "markdown", "metadata": {}, "id": "", "source": ["suite"]},
        ], "metadata": {}, "nbformat": 4, "nbformat_minor": 5,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()
    validate_selected_notebook(SelectedCopy("copy-001", path.name, path, "a" * 64))
    web_loaded = load_and_normalize_notebook(path)
    a71_loaded = load_notebook_copy(NotebookCopySource("copy-001", path.name, path))
    assert [cell.id for cell in web_loaded.cells] == [cell.id for cell in a71_loaded.cells]
    assert [cell.source for cell in web_loaded.cells] == ["ligne 1\nligne 2", "suite"]
    assert [cell.source for cell in web_loaded.cells] == [cell.source for cell in a71_loaded.cells]
    assert path.read_bytes() == before


def test_common_loader_ids_are_deterministic_and_preserve_valid_ids(tmp_path: Path) -> None:
    import json
    path = tmp_path / "ids.ipynb"
    payload = {"cells": [
        {"cell_type": "markdown", "metadata": {}, "id": "kept", "source": "a"},
        {"cell_type": "markdown", "metadata": {}, "id": "", "source": "b"},
        {"cell_type": "markdown", "metadata": {}, "id": "tpstudio-cell-0001", "source": "c"},
    ], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    path.write_text(json.dumps(payload), encoding="utf-8")
    first = load_and_normalize_notebook(path)
    second = load_and_normalize_notebook(path)
    assert [cell.id for cell in first.cells] == ["kept", "tpstudio-cell-0001-1", "tpstudio-cell-0001"]
    assert [cell.id for cell in first.cells] == [cell.id for cell in second.cells]


def test_common_loader_removes_ids_from_legacy_v44_notebook(tmp_path: Path) -> None:
    import json
    path = tmp_path / "legacy-v44.ipynb"
    payload = {"cells": [{"cell_type": "markdown", "metadata": {}, "id": "old", "source": "a"}], "metadata": {}, "nbformat": 4, "nbformat_minor": 4}
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()
    loaded = load_and_normalize_notebook(path)
    assert "id" not in loaded.cells[0]
    assert path.read_bytes() == before


def test_common_loader_joins_multiline_stream_text_only_when_all_parts_are_strings(tmp_path: Path) -> None:
    import json
    path = tmp_path / "stream-list.ipynb"
    payload = {"cells": [{"cell_type": "code", "execution_count": 1, "metadata": {}, "outputs": [{
        "output_type": "stream", "name": "stdout", "text": ["première ligne\n", "deuxième ligne\n"]
    }], "source": "print('x')"}], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    loaded = load_and_normalize_notebook(path)
    assert loaded.cells[0].outputs[0].text == "première ligne\ndeuxième ligne\n"
    assert path.read_bytes() == before

    invalid = dict(payload)
    invalid["cells"] = [dict(payload["cells"][0], outputs=[{
        "output_type": "stream", "name": "stdout", "text": ["ok\n", 3]
    }])]
    bad = tmp_path / "invalid-stream-list.ipynb"
    bad.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError):
        load_and_normalize_notebook(bad)


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
    assert result.attachment_cell_indices == (0,)
    assert "./mesures.csv" in result.referenced_external_paths


def test_import_without_output_is_not_an_error() -> None:
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_code_cell("import math", execution_count=1),
    ])
    result = inspect_notebook(notebook)
    assert result.error_output_cell_indices == ()
    assert result.stored_output_cell_indices == ()
