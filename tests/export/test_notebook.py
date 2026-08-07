from pathlib import Path

import nbformat
import pytest

from tpstudio.annotation import AnnotatedNotebookResult, AnnotationOptions, AnnotationPlan
from tpstudio.export import validate_exported_notebook, validate_notebook_object


def _notebook():
    code = nbformat.v4.new_code_cell("x = 1", execution_count=1)
    code.outputs = [nbformat.v4.new_output("stream", name="stdout", text="1")]
    return nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("Texte $x$"), code])


def test_validate_notebook_object_and_file(tmp_path):
    notebook = _notebook(); assert validate_notebook_object(notebook).valid
    path = tmp_path / "copy.ipynb"; nbformat.write(notebook, path)
    validation = validate_exported_notebook(path)
    assert validation.valid and validation.cell_count == 2


def test_invalid_exported_notebook_is_reported(tmp_path):
    path = tmp_path / "bad.ipynb"; path.write_text("not notebook")
    assert not validate_exported_notebook(path).valid
