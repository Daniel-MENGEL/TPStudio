import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import nbformat
import pytest

from tpstudio.export import CopyExportOptions, export_snells_laws_copy
import tpstudio.export.pipeline as pipeline
from tpstudio.interpretation import InterpretationClassification
from tpstudio.orchestration import NotebookCopySource, analyze_snells_laws_copy
from tpstudio.review_store import append_interpretation_review, review_store_path


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


def test_pipeline_renders_multiline_stream_output_as_text(tmp_path):
    module = _fixture()
    payload = json.loads(nbformat.writes(module._notebook()))
    code = next(cell for cell in payload["cells"] if cell["cell_type"] == "code")
    code["outputs"].append({
        "output_type": "stream",
        "name": "stdout",
        "text": [
            "Ecart normalisé avec la valeur précédente : 0.1236...\n",
            "Les mesures sont cohérentes\n",
        ],
    })
    source = tmp_path / "multiline-stream.ipynb"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    before = source.read_bytes()
    result = export_snells_laws_copy(source, tmp_path / "out")
    html = result.html_artifact.path.read_text(encoding="utf-8")
    assert "Ecart normalisé avec la valeur précédente : 0.1236..." in html
    assert "Les mesures sont cohérentes" in html
    assert "['Ecart normalisé" not in html
    assert source.read_bytes() == before


def test_pipeline_applies_compatible_teacher_interpretation_review(tmp_path):
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("Le graphe est correct.", metadata={
            "tpstudio": {"role": "interpretation_response", "expectation_id": "interp-1"}
        })
    ])
    source = tmp_path / "copy.ipynb"
    nbformat.write(notebook, source)
    analysis = analyze_snells_laws_copy(NotebookCopySource("local-copy", source.name, source))
    trace = analysis.interpretation_review_traces[0]
    reviewed = __import__("dataclasses").replace(
        trace,
        teacher_decision=InterpretationClassification.CLEARLY_SUFFICIENT,
        teacher_feedback="Retour enseignant prioritaire.",
        reviewed_at="2026-08-15T12:00:00+00:00",
    )
    append_interpretation_review(review_store_path(tmp_path / "out"), reviewed)
    result = export_snells_laws_copy(
        source,
        tmp_path / "out",
        options=CopyExportOptions(include_teacher_feedback=True, include_diagnostics=True),
    )
    exported = nbformat.read(result.notebook_artifact.path, as_version=nbformat.NO_CONVERT)
    text = "\n".join(cell.source for cell in exported.cells if cell.cell_type == "markdown")
    html = result.html_artifact.path.read_text(encoding="utf-8")
    assert "Retour enseignant prioritaire." in text
    assert "Retour enseignant prioritaire." in html
    assert "L'interprétation nécessite une revue humaine." not in text
    assert "L'interprétation nécessite une revue humaine." not in html
    for private_value in ("email", "copy_sha256", "interpretation_reviews.jsonl"):
        assert private_value not in text
        assert private_value not in html


@pytest.mark.parametrize(
    ("decision", "expected_text"),
    [
        (InterpretationClassification.CLEARLY_SUFFICIENT, "Retour enseignant prioritaire."),
        (InterpretationClassification.CLEARLY_INSUFFICIENT, "Retour enseignant prioritaire."),
        (InterpretationClassification.AMBIGUOUS, "L'interprétation nécessite une revue humaine."),
    ],
)
def test_pipeline_notebook_and_html_share_effective_interpretation_state(tmp_path, decision, expected_text):
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("Le graphe est correct.", metadata={
            "tpstudio": {"role": "interpretation_response", "expectation_id": "interp-1"}
        })
    ])
    source = tmp_path / "copy.ipynb"
    nbformat.write(notebook, source)
    analysis = analyze_snells_laws_copy(NotebookCopySource("local-copy", source.name, source))
    trace = analysis.interpretation_review_traces[0]
    reviewed = replace(
        trace,
        teacher_decision=decision,
        teacher_feedback="Retour enseignant prioritaire.",
        reviewed_at="2026-08-15T12:00:00+00:00",
    )
    append_interpretation_review(review_store_path(tmp_path / "out"), reviewed)
    result = export_snells_laws_copy(
        source,
        tmp_path / "out",
        options=CopyExportOptions(include_teacher_feedback=True, include_diagnostics=True),
    )
    exported = nbformat.read(result.notebook_artifact.path, as_version=nbformat.NO_CONVERT)
    notebook_text = "\n".join(cell.source for cell in exported.cells if cell.cell_type == "markdown")
    html_text = result.html_artifact.path.read_text(encoding="utf-8")
    if decision is InterpretationClassification.AMBIGUOUS:
        assert expected_text not in notebook_text
        assert expected_text not in html_text
    else:
        assert expected_text in notebook_text
        assert expected_text in html_text


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


def test_explicit_destinations_must_remain_inside_output_dir(tmp_path):
    module = _fixture(); source = tmp_path / "copy.ipynb"; nbformat.write(module._notebook(), source)
    out = tmp_path / "out"; out.mkdir()
    (out / "nested").mkdir()
    accepted_nb = out / "nested" / ".." / "copy.ipynb"
    accepted_html = out / "nested" / ".." / "copy.html"
    result = export_snells_laws_copy(source, out, notebook_output_path=accepted_nb, html_output_path=accepted_html)
    assert result.notebook_artifact.path == accepted_nb and result.html_artifact.path == accepted_html
    with pytest.raises(ValueError, match="output_dir"):
        export_snells_laws_copy(source, out, notebook_output_path=tmp_path / "outside.ipynb", html_output_path=out / "copy.html")
    with pytest.raises(ValueError, match="output_dir"):
        export_snells_laws_copy(source, out, notebook_output_path=out / "other.ipynb", html_output_path=tmp_path / "outside.html")
