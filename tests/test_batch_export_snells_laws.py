import importlib.util
from pathlib import Path
import nbformat

def test_script_exports_explicit_multiple_sources(tmp_path):
    spec = importlib.util.spec_from_file_location("fixture", Path("tests/orchestration/test_copy_analysis.py")); fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
    spec = importlib.util.spec_from_file_location("batch_script", Path("scripts/batch_export_snells_laws.py")); script = importlib.util.module_from_spec(spec); spec.loader.exec_module(script)
    first = tmp_path / "one.ipynb"; second = tmp_path / "two.ipynb"; nbformat.write(fixture._notebook(), first); nbformat.write(fixture._notebook(), second)
    assert script.main(["--output-dir", str(tmp_path / "out"), str(first), str(second)]) == 0
    assert (tmp_path / "out" / "one-correction.ipynb").exists() and (tmp_path / "out" / "two-correction.html").exists()


def test_script_skipped_destination_returns_failure_and_overwrite_succeeds(tmp_path):
    spec = importlib.util.spec_from_file_location("fixture", Path("tests/orchestration/test_copy_analysis.py")); fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
    spec = importlib.util.spec_from_file_location("batch_script_skip", Path("scripts/batch_export_snells_laws.py")); script = importlib.util.module_from_spec(spec); spec.loader.exec_module(script)
    source = tmp_path / "one.ipynb"; output = tmp_path / "out"; nbformat.write(fixture._notebook(), source)
    args = ["--output-dir", str(output), str(source)]
    assert script.main(args) == 0
    assert script.main(args) == 1
    assert script.main(["--overwrite", *args]) == 0
