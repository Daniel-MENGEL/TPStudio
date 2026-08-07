import importlib.util
from pathlib import Path

import nbformat
import pytest


def _module():
    path = Path("scripts/report_snells_laws_copy.py")
    spec = importlib.util.spec_from_file_location("report_snells_script", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def _notebook(path):
    nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("Synthétique")]), path)
    return path.read_bytes()


@pytest.mark.parametrize("option", ((), ("--no-feedback",), ("--student-feedback",), ("--teacher-feedback",)))
def test_script_reports_without_writing_or_executing(tmp_path, capsys, option) -> None:
    source = tmp_path / "copy"; before = _notebook(source)
    assert _module().main([str(source), *option]) == 0
    assert "Project: snells-laws-mvp" in capsys.readouterr().out
    assert source.read_bytes() == before and tuple(tmp_path.iterdir()) == (source,)


def test_script_writes_only_explicit_markdown_output(tmp_path) -> None:
    source = tmp_path / "copy"; before = _notebook(source); output = tmp_path / "report.md"
    assert _module().main([str(source), "--output", str(output)]) == 0
    assert output.read_text().startswith("# Rapport TPStudio") and source.read_bytes() == before
    assert "<html" not in output.read_text().lower()


def test_script_refuses_implicit_overwrite(tmp_path) -> None:
    source = tmp_path / "copy"; _notebook(source); output = tmp_path / "report.md"; output.write_text("keep")
    with pytest.raises(FileExistsError): _module().main([str(source), "--output", str(output)])
    assert output.read_text() == "keep"


def test_script_rejects_invalid_notebook_and_has_no_execute_option(tmp_path) -> None:
    path = tmp_path / "bad"; path.write_text("bad")
    with pytest.raises(ValueError): _module().main([str(path)])
    assert "--execute" not in _module()._parser().format_help()
