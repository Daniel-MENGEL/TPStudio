import importlib.util
from pathlib import Path

import nbformat
import pytest


def _module():
    path = Path("scripts/annotate_snells_laws_copy.py")
    spec = importlib.util.spec_from_file_location("annotate_script", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def _source(path):
    nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("Synthétique")]), path)
    return path.read_bytes()


def test_without_output_writes_nothing(tmp_path, capsys) -> None:
    source = tmp_path / "copy"; before = _source(source)
    assert _module().main([str(source)]) == 0
    assert "Student annotations:" in capsys.readouterr().out
    assert source.read_bytes() == before and tuple(tmp_path.iterdir()) == (source,)


@pytest.mark.parametrize("option", ((), ("--teacher-copy",), ("--include-diagnostics",), ("--keep-existing",)))
def test_explicit_output_creates_only_derived_notebook(tmp_path, option) -> None:
    source = tmp_path / "copy"; before = _source(source); output = tmp_path / "derived.ipynb"
    assert _module().main([str(source), "--output", str(output), *option]) == 0
    nbformat.read(output, as_version=nbformat.NO_CONVERT)
    assert source.read_bytes() == before


def test_overwrite_is_explicit_and_invalid_file_fails(tmp_path) -> None:
    source = tmp_path / "copy"; _source(source); output = tmp_path / "derived.ipynb"; output.write_text("keep")
    with pytest.raises(FileExistsError): _module().main([str(source), "--output", str(output)])
    assert _module().main([str(source), "--output", str(output), "--overwrite"]) == 0
    invalid = tmp_path / "bad"; invalid.write_text("bad")
    with pytest.raises(ValueError): _module().main([str(invalid)])


@pytest.mark.parametrize("overwrite", (False, True))
def test_source_can_never_be_output(tmp_path, overwrite) -> None:
    source = tmp_path / "copy.ipynb"; before = _source(source)
    arguments = [str(source), "--output", str(source)]
    if overwrite:
        arguments.append("--overwrite")
    with pytest.raises(ValueError, match="source"):
        _module().main(arguments)
    assert source.read_bytes() == before


def test_equivalent_source_output_is_rejected_and_distinct_overwrite_works(tmp_path) -> None:
    source = tmp_path / "copy.ipynb"; before = _source(source)
    equivalent = tmp_path / "child" / ".." / "copy.ipynb"
    with pytest.raises(ValueError, match="source"):
        _module().main([str(source), "--output", str(equivalent), "--overwrite"])
    assert source.read_bytes() == before
    output = tmp_path / "derived.ipynb"; output.write_text("old")
    assert _module().main([str(source), "--output", str(output), "--overwrite"]) == 0
    assert source.read_bytes() == before


def test_script_has_no_execution_or_html_option() -> None:
    help_text = _module()._parser().format_help()
    assert "--execute" not in help_text and "--html" not in help_text
