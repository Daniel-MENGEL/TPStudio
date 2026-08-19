from dataclasses import replace
import os
from pathlib import Path
import importlib.util

import nbformat
import pytest

import tpstudio.export.pipeline as pipeline
from tpstudio.export import CopyExportOptions, export_analyzed_copy, render_annotated_notebook_html
from tpstudio.orchestration import NotebookCopySource, analyze_copy
from tpstudio.projects import snells_laws_teacher_project, thin_lens_teacher_project


def _fixture():
    path = Path("tests/orchestration/test_copy_analysis.py")
    spec = importlib.util.spec_from_file_location("generic_export_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _analyzed(tmp_path):
    module = _fixture()
    source_path = tmp_path / "copy.ipynb"
    nbformat.write(module._notebook(), source_path)
    source = NotebookCopySource("copy", source_path.name, source_path)
    analysis = analyze_copy(source, project=thin_lens_teacher_project()).analysis
    assert analysis is not None
    return source, analysis


def test_export_analyzed_copy_exports_lens_without_reanalysis(tmp_path, monkeypatch):
    source, analysis = _analyzed(tmp_path)
    monkeypatch.setattr(pipeline, "analyze_copy", lambda *args, **kwargs: pytest.fail("réanalyse interdite"), raising=False)
    monkeypatch.setattr(pipeline, "analyze_snells_laws_copy", lambda *args, **kwargs: pytest.fail("réanalyse Snell interdite"))
    result = export_analyzed_copy(source, analysis, tmp_path / "out", output_stem="lens")
    assert result.project_id == "thin-lens-image"
    assert result.success
    assert result.teacher_report is not None
    assert result.teacher_report.project_id == "thin-lens-image"
    html = result.html_artifact.path.read_text(encoding="utf-8")
    assert "<title>TPStudio — Formation d&#x27;une image par une lentille mince — Correction</title>" in html
    assert "Attendu Snell-Descartes" not in html


def test_export_analyzed_copy_rejects_mismatched_source(tmp_path):
    source, analysis = _analyzed(tmp_path)
    other_path = tmp_path / "other.ipynb"
    other_path.write_bytes(source.path.read_bytes())
    other = NotebookCopySource("other", other_path.name, other_path)
    with pytest.raises(ValueError, match="même copie"):
        export_analyzed_copy(other, analysis, tmp_path / "out")


def test_export_analyzed_copy_accepts_equivalent_relative_and_absolute_paths(tmp_path):
    source, analysis = _analyzed(tmp_path)
    relative_path = Path(os.path.relpath(source.path, Path.cwd()))
    equivalent = NotebookCopySource(source.source_id, source.display_name, relative_path)
    result = export_analyzed_copy(equivalent, analysis, tmp_path / "out", output_stem="relative")
    assert result.success


def test_export_analyzed_copy_rejects_different_file_with_same_source_id(tmp_path):
    source, analysis = _analyzed(tmp_path)
    other_path = tmp_path / "other.ipynb"
    other_path.write_bytes(source.path.read_bytes())
    other = NotebookCopySource(source.source_id, other_path.name, other_path)
    with pytest.raises(ValueError, match="même copie"):
        export_analyzed_copy(other, analysis, tmp_path / "out")


def test_export_analyzed_copy_rejects_different_source_id_for_same_file(tmp_path):
    source, analysis = _analyzed(tmp_path)
    different_id = NotebookCopySource("other-id", source.display_name, source.path)
    with pytest.raises(ValueError, match="même copie"):
        export_analyzed_copy(different_id, analysis, tmp_path / "out")


def test_export_uses_explicit_analysis_project_over_source_content(tmp_path):
    module = _fixture()
    source_path = tmp_path / "lentille-looking-copy.ipynb"
    nbformat.write(module._notebook(), source_path)
    source = NotebookCopySource("copy", source_path.name, source_path)
    analysis = analyze_copy(source, project=snells_laws_teacher_project()).analysis
    assert analysis is not None
    result = export_analyzed_copy(source, analysis, tmp_path / "out")
    assert result.project_id == "snells-laws-mvp"
    html = result.html_artifact.path.read_text(encoding="utf-8")
    assert "<title>TPStudio — Lois de Snell-Descartes — Correction</title>" in html


def test_html_title_is_escaped(tmp_path):
    module = _fixture()
    notebook = module._notebook()
    html = render_annotated_notebook_html(
        notebook,
        options=CopyExportOptions(),
        title="TPStudio — <Projet & test> — Correction",
    )
    assert "<title>TPStudio — &lt;Projet &amp; test&gt; — Correction</title>" in html
