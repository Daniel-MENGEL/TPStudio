from pathlib import Path

import nbformat
import pytest

from tpstudio.annotation import (
    AnnotatedNotebookResult, default_annotated_notebook_name,
    paths_refer_to_same_location, write_annotated_notebook,
)


def _result():
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("Original")])
    return AnnotatedNotebookResult(notebook, (), (), (), 1, 1, False)


def test_explicit_write_is_valid_and_refuses_overwrite(tmp_path) -> None:
    path = tmp_path / "derived.ipynb"
    assert write_annotated_notebook(_result(), path) == path
    assert nbformat.read(path, as_version=nbformat.NO_CONVERT).cells[0].source == "Original"
    with pytest.raises(FileExistsError): write_annotated_notebook(_result(), path)
    assert write_annotated_notebook(_result(), path, overwrite=True) == path


def test_writer_never_overwrites_source_even_with_equivalent_path(tmp_path) -> None:
    source = tmp_path / "source.ipynb"
    nbformat.write(_result().notebook, source)
    before = source.read_bytes()
    equivalent = tmp_path / "." / "folder" / ".." / "source.ipynb"
    assert paths_refer_to_same_location(source, equivalent)
    with pytest.raises(ValueError, match="source"):
        write_annotated_notebook(
            _result(), equivalent, overwrite=True, source_path=source,
        )
    assert source.read_bytes() == before


def test_writer_detects_symbolic_link_to_source(tmp_path) -> None:
    source = tmp_path / "source.ipynb"
    nbformat.write(_result().notebook, source)
    link = tmp_path / "alias.ipynb"
    link.symlink_to(source)
    with pytest.raises(ValueError, match="source"):
        write_annotated_notebook(_result(), link, overwrite=True, source_path=source)


@pytest.mark.parametrize(("source", "expected"), (("tp.ipynb", "tp-correction.ipynb"), ("tp", "tp-correction.ipynb"), ("foo.bar.ipynb", "foo.bar-correction.ipynb")))
def test_default_name(source, expected) -> None:
    assert default_annotated_notebook_name(source) == expected
