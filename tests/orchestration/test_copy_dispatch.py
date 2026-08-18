from dataclasses import replace
from pathlib import Path

import nbformat
from tpstudio.orchestration import (
    CopyAnalysisDispatchResult,
    NotebookCopySource,
    ProjectSelectionProvenance,
    SnellsLawsCopyAnalyzer,
    analyze_copy,
)
from tpstudio.projects import snells_laws_teacher_project, thin_lens_teacher_project

from tests.orchestration.test_copy_analysis import _notebook


def _write_source(tmp_path: Path, notebook, name: str = "copy.ipynb") -> NotebookCopySource:
    path = tmp_path / name
    nbformat.write(notebook, path)
    return NotebookCopySource(name, name, path)


def test_explicit_snell_uses_project_without_resolution(tmp_path: Path) -> None:
    source = _write_source(tmp_path, _notebook())
    project = snells_laws_teacher_project()
    result = analyze_copy(source, project=project)
    assert isinstance(result, CopyAnalysisDispatchResult)
    assert result.provenance is ProjectSelectionProvenance.EXPLICIT
    assert result.analysis is not None
    assert result.analysis.project is project
    assert result.analysis.project_id == "snells-laws-mvp"


def test_historical_snell_wrapper_remains_explicit(tmp_path: Path) -> None:
    source = _write_source(tmp_path, _notebook())
    result = SnellsLawsCopyAnalyzer().analyze(source)
    assert result.project_id == "snells-laws-mvp"


def test_auto_snell_resolves_then_analyzes(tmp_path: Path) -> None:
    notebook = _notebook()
    notebook.cells.insert(0, nbformat.v4.new_markdown_cell("# Lois de Snell-Descartes"))
    result = analyze_copy(_write_source(tmp_path, notebook))
    assert result.provenance is ProjectSelectionProvenance.AUTO_RESOLVED
    assert result.resolution.selected_project_id == "snells-laws-mvp"
    assert result.analysis is not None
    assert result.analysis.project_id == "snells-laws-mvp"
    project = result.analysis.project
    assert project.identity.project_id == "snells-laws-mvp"
    assert project.scientific_production_plan is not None
    assert project.quantity_expectation_set is not None
    assert project.relation_expectation_set is not None
    assert project.graph_expectation_set is not None
    assert project.feedback_catalogs


def test_auto_lens_routes_to_lens_factory_without_scientific_fallback(tmp_path: Path, monkeypatch) -> None:
    base_notebook = _notebook()
    base_source = _write_source(tmp_path, base_notebook, "base.ipynb")
    base_analysis = SnellsLawsCopyAnalyzer().analyze(base_source)
    expected = replace(base_analysis, project=thin_lens_teacher_project())

    def fake_analyze(self, source, project=None, options=None):
        assert project is not None
        return expected

    monkeypatch.setattr(SnellsLawsCopyAnalyzer, "analyze", fake_analyze)
    lens_notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(
            "# Formation d'une image par une lentille mince\n"
            "Relation de conjugaison : 1/OA' - 1/OA = 1/f'."
        )
    ])
    result = analyze_copy(_write_source(tmp_path, lens_notebook, "lens.ipynb"))
    assert result.provenance is ProjectSelectionProvenance.AUTO_RESOLVED
    assert result.resolution.selected_project_id == "thin-lens-image"
    assert result.analysis is not None
    assert result.analysis.project_id == "thin-lens-image"


def test_empty_notebook_is_unresolved_without_snell_fallback(tmp_path: Path) -> None:
    result = analyze_copy(_write_source(tmp_path, nbformat.v4.new_notebook()))
    assert result.provenance is ProjectSelectionProvenance.UNRESOLVED
    assert result.analysis is None
    assert result.resolution.selected_project_id is None
    assert result.resolution.candidates == ()
    assert result.resolution.requires_teacher_choice is False


def test_medium_candidate_is_unresolved_without_analysis(tmp_path: Path) -> None:
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("Tracer sin(i1) en fonction de sin(i2).")
    ])
    result = analyze_copy(_write_source(tmp_path, notebook))
    assert result.provenance is ProjectSelectionProvenance.UNRESOLVED
    assert result.analysis is None
    assert result.resolution.requires_teacher_choice is True


def test_high_high_conflict_is_unresolved_without_analysis(tmp_path: Path) -> None:
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(
            "# Lois de Snell-Descartes\nÉtudier la réfraction et l'indice.\n"
            "# Formation d'une image par une lentille mince\n"
            "Relation de conjugaison : 1/OA' - 1/OA = 1/f'."
        )
    ])
    result = analyze_copy(_write_source(tmp_path, notebook))
    assert result.provenance is ProjectSelectionProvenance.UNRESOLVED
    assert result.analysis is None
    assert result.resolution.requires_teacher_choice is True


def test_explicit_lens_bypasses_heuristics_even_on_snell_like_source(tmp_path: Path) -> None:
    source = _write_source(tmp_path, _notebook())
    result = analyze_copy(source, project=thin_lens_teacher_project())
    assert result.provenance is ProjectSelectionProvenance.EXPLICIT
    assert result.analysis is not None
    assert result.analysis.project_id == "thin-lens-image"


def test_explicit_snell_wins_over_lens_like_content(tmp_path: Path) -> None:
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(
            "# Formation d'une image par une lentille mince\n"
            "Relation de conjugaison : 1/OA' - 1/OA = 1/f'."
        )
    ])
    result = analyze_copy(
        _write_source(tmp_path, notebook, "lens-content.ipynb"),
        project=snells_laws_teacher_project(),
    )
    assert result.provenance is ProjectSelectionProvenance.EXPLICIT
    assert result.analysis is not None
    assert result.analysis.project_id == "snells-laws-mvp"


def test_options_are_forwarded_identically_for_explicit_and_auto_paths(tmp_path: Path, monkeypatch) -> None:
    base_source = _write_source(tmp_path, _notebook(), "base.ipynb")
    base_analysis = SnellsLawsCopyAnalyzer().analyze(base_source)
    options = base_analysis.options
    captured = []

    def fake_analyze(self, source, project=None, options=None):
        captured.append(options)
        return replace(base_analysis, project=project, source=source, options=options)

    monkeypatch.setattr(SnellsLawsCopyAnalyzer, "analyze", fake_analyze)
    explicit = analyze_copy(
        _write_source(tmp_path, _notebook(), "explicit.ipynb"),
        project=snells_laws_teacher_project(),
        options=options,
    )
    lens_notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(
            "# Formation d'une image par une lentille mince\n"
            "Relation de conjugaison : 1/OA' - 1/OA = 1/f'."
        )
    ])
    automatic = analyze_copy(
        _write_source(tmp_path, lens_notebook, "automatic.ipynb"),
        options=options,
    )
    assert explicit.provenance is ProjectSelectionProvenance.EXPLICIT
    assert automatic.provenance is ProjectSelectionProvenance.AUTO_RESOLVED
    assert captured == [options, options]
    assert explicit.analysis is not None and explicit.analysis.options is options
    assert automatic.analysis is not None and automatic.analysis.options is options
