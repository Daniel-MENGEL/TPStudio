import importlib.util
from pathlib import Path

import nbformat
import pytest


def _module():
    path = Path("scripts/export_snells_laws_copy.py")
    spec = importlib.util.spec_from_file_location("export_script", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_output_dir_is_required():
    with pytest.raises(SystemExit): _module().main(["copy.ipynb"])


def test_script_exports_without_execution(tmp_path):
    spec = importlib.util.spec_from_file_location("copy_fixture", Path("tests/orchestration/test_copy_analysis.py"))
    fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
    source = tmp_path / "copy.ipynb"; nbformat.write(fixture._notebook(), source); before = source.read_bytes()
    assert _module().main([str(source), "--output-dir", str(tmp_path / "out")]) == 0
    assert source.read_bytes() == before
