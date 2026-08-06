import importlib.util
from pathlib import Path

import nbformat
import pytest


def _module():
    path = Path("scripts/analyze_snells_laws_copy.py")
    spec = importlib.util.spec_from_file_location("analyze_snells_laws_copy_script", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _notebook(path: Path) -> bytes:
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("Copie synthétique")])
    nbformat.write(notebook, path)
    return path.read_bytes()


@pytest.mark.parametrize("option", ((), ("--no-feedback",), ("--teacher-only",), ("--student-only",)))
def test_script_accepts_explicit_path_and_feedback_options(tmp_path: Path, capsys, option) -> None:
    path = tmp_path / "copy"
    before = _notebook(path)
    assert _module().main([str(path), *option]) == 0
    output = capsys.readouterr().out
    assert "Projet : snells-laws-mvp" in output
    assert str(tmp_path) not in output
    assert path.read_bytes() == before


def test_script_rejects_invalid_notebook(tmp_path: Path) -> None:
    path = tmp_path / "invalid"
    path.write_text("invalid", encoding="utf-8")
    with pytest.raises(ValueError):
        _module().main([str(path)])


def test_script_has_no_execution_option_or_private_default() -> None:
    parser = _module()._parser()
    help_text = parser.format_help()
    assert "--execute" not in help_text
    assert "/Users/" not in help_text
