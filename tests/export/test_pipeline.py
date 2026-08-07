import importlib.util
from pathlib import Path

import nbformat
import pytest

from tpstudio.export import CopyExportOptions, export_snells_laws_copy
import tpstudio.export.pipeline as pipeline


def _fixture():
    spec = importlib.util.spec_from_file_location("copy_fixture", Path("tests/orchestration/test_copy_analysis.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_pipeline_creates_two_derived_artifacts_and_preserves_source(tmp_path):
    module = _fixture(); source = tmp_path / "copy.ipynb"; nbformat.write(module._notebook(), source)
    before = source.read_bytes(); result = export_snells_laws_copy(source, tmp_path / "out")
    assert result.success and result.source_preserved and source.read_bytes() == before
    assert result.notebook_artifact.path.exists() and result.html_artifact.path.exists()
    exported = nbformat.read(result.notebook_artifact.path, as_version=nbformat.NO_CONVERT)
    assert "Retour TPStudio" in "\n".join(cell.source for cell in exported.cells if cell.cell_type == "markdown")


def test_pipeline_refuses_existing_destination_transactionally(tmp_path):
    module = _fixture(); source = tmp_path / "copy.ipynb"; nbformat.write(module._notebook(), source)
    out = tmp_path / "out"; out.mkdir(); html = out / "copy-correction.html"; html.write_text("keep")
    with pytest.raises(FileExistsError): export_snells_laws_copy(source, out)
    assert not (out / "copy-correction.ipynb").exists() and html.read_text() == "keep"


def test_pipeline_overwrite_replaces_derived_files_only(tmp_path):
    module = _fixture(); source = tmp_path / "copy.ipynb"; nbformat.write(module._notebook(), source)
    out = tmp_path / "out"; first = export_snells_laws_copy(source, out)
    before = source.read_bytes(); second = export_snells_laws_copy(source, out, options=CopyExportOptions(overwrite=True))
    assert second.success and source.read_bytes() == before


def test_overwritten_is_recorded_per_artifact(tmp_path):
    module = _fixture(); source = tmp_path / "copy.ipynb"; nbformat.write(module._notebook(), source)
    out = tmp_path / "out"; first = export_snells_laws_copy(source, out)
    assert not first.notebook_artifact.overwritten and not first.html_artifact.overwritten
    first.notebook_artifact.path.unlink()
    second = export_snells_laws_copy(source, out, options=CopyExportOptions(overwrite=True))
    assert not second.notebook_artifact.overwritten and second.html_artifact.overwritten


def test_second_install_failure_rolls_back_new_files(tmp_path, monkeypatch):
    notebook = tmp_path / "a.ipynb"; html = tmp_path / "a.html"
    temp_nb = tmp_path / "temp.ipynb"; temp_html = tmp_path / "temp.html"
    temp_nb.write_bytes(b"nb"); temp_html.write_bytes(b"html")
    original = pipeline.os.replace
    def fail_second(source, destination):
        if destination == html:
            raise OSError("simulated second replacement failure")
        return original(source, destination)
    monkeypatch.setattr(pipeline.os, "replace", fail_second)
    with pytest.raises(OSError):
        pipeline._commit_artifact_pair(temp_nb, notebook, temp_html, html, overwrite=False)
    assert not notebook.exists() and not html.exists()
    assert temp_nb.exists() is False and temp_html.exists() is False


def test_overwrite_failure_restores_both_old_artifacts(tmp_path, monkeypatch):
    notebook = tmp_path / "a.ipynb"; html = tmp_path / "a.html"
    notebook.write_bytes(b"OLD NB"); html.write_bytes(b"OLD HTML")
    temp_nb = tmp_path / "temp.ipynb"; temp_html = tmp_path / "temp.html"
    temp_nb.write_bytes(b"NEW NB"); temp_html.write_bytes(b"NEW HTML")
    original = pipeline.os.replace
    def fail_install(source, destination):
        if destination == html and source == temp_html:
            raise OSError("simulated install failure")
        return original(source, destination)
    monkeypatch.setattr(pipeline.os, "replace", fail_install)
    with pytest.raises(OSError):
        pipeline._commit_artifact_pair(temp_nb, notebook, temp_html, html, overwrite=True)
    assert notebook.read_bytes() == b"OLD NB" and html.read_bytes() == b"OLD HTML"
    assert not list(tmp_path.glob(".tpstudio-*"))


def test_invalid_temporary_notebook_writes_no_destination(tmp_path, monkeypatch):
    module = _fixture(); source = tmp_path / "copy.ipynb"; nbformat.write(module._notebook(), source)
    monkeypatch.setattr(pipeline, "validate_exported_notebook", lambda path: type("V", (), {"valid": False})())
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="temporaire"):
        export_snells_laws_copy(source, out)
    assert not out.exists() or not tuple(out.iterdir())
