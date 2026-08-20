from pathlib import Path
from dataclasses import replace

import nbformat
import pytest

from tpstudio.orchestration import (
    AnalysisReadiness,
    BatchCopyDispatchStatus,
    BatchCopyRequest,
    CopyAnalysisDispatchResult,
    NotebookCopySource,
    ProjectSelectionProvenance,
    assess_analysis_readiness,
    analyze_copy,
    run_batch,
)
from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
)
from tpstudio.projects import (
    snells_laws_teacher_project,
    thin_lens_teacher_project,
    torsion_pendulum_teacher_project,
)


PENDULUM = Path(
    "/Users/daniel/Downloads/TPStudio-prototypes/"
    "Pendule-de-torsion-TPStudio-A76d2-prototype.ipynb"
)


def _source(tmp_path: Path, notebook, name: str) -> NotebookCopySource:
    path = tmp_path / name
    nbformat.write(notebook, path)
    return NotebookCopySource(name, name, path)


def _snell_notebook():
    return nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(
            "# Lois de Snell-Descartes\nÉtudier la réfraction et l'indice."
        )
    ])


def _lens_notebook():
    return nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(
            "# Formation d'une image par une lentille mince\n"
            "Relation de conjugaison : 1/OA' - 1/OA = 1/f'."
        )
    ])


def test_generic_readiness_keeps_lens_and_snell_ready_and_pendulum_not_ready():
    assert assess_analysis_readiness(thin_lens_teacher_project()) is AnalysisReadiness.READY
    assert assess_analysis_readiness(snells_laws_teacher_project()) is AnalysisReadiness.READY
    assert assess_analysis_readiness(torsion_pendulum_teacher_project()) is AnalysisReadiness.NOT_READY


def test_quantity_expectation_without_binding_is_not_ready():
    project = thin_lens_teacher_project()
    bindings = tuple(
        binding
        for binding in project.notebook_binding_plan.bindings
        if binding.production_id != "conjugation_slope"
    )
    plan = NotebookBindingPlan(
        project.notebook_binding_plan.id,
        project.notebook_binding_plan.title,
        project.scientific_production_plan,
        bindings,
    )
    incomplete = replace(project, notebook_binding_plan=plan)
    assert assess_analysis_readiness(incomplete) is AnalysisReadiness.NOT_READY


def test_multiple_bindings_for_unique_quantity_are_not_ready():
    project = thin_lens_teacher_project()
    original = next(
        binding for binding in project.notebook_binding_plan.bindings
        if binding.production_id == "conjugation_slope"
    )
    duplicate = CellProductionBinding(
        "duplicate-conjugation-slope",
        original.production_id,
        NotebookCellSelector(NotebookCellSelectorKind.SOURCE_MARKER, "another marker"),
        CellTextScope.full_source(),
    )
    plan = NotebookBindingPlan(
        project.notebook_binding_plan.id,
        project.notebook_binding_plan.title,
        project.scientific_production_plan,
        (*project.notebook_binding_plan.bindings, duplicate),
    )
    incomplete = replace(project, notebook_binding_plan=plan)
    assert assess_analysis_readiness(incomplete) is AnalysisReadiness.NOT_READY


def test_auto_resolved_pendulum_is_not_ready_without_assertion():
    source = NotebookCopySource("pendulum", PENDULUM.name, PENDULUM)
    result = analyze_copy(source)
    assert result.resolution.selected_project_id == "torsion-pendulum"
    assert result.analysis is None
    assert result.readiness is AnalysisReadiness.NOT_READY


def test_explicit_pendulum_is_not_ready_without_assertion():
    source = NotebookCopySource("pendulum", PENDULUM.name, PENDULUM)
    result = analyze_copy(source, project=torsion_pendulum_teacher_project())
    assert result.provenance.value == "explicit"
    assert result.analysis is None
    assert result.readiness is AnalysisReadiness.NOT_READY


def test_legacy_snell_wrapper_rejects_not_ready_explicit_project():
    from tpstudio.orchestration import analyze_snells_laws_copy

    source = NotebookCopySource("pendulum", PENDULUM.name, PENDULUM)
    try:
        analyze_snells_laws_copy(source, project=torsion_pendulum_teacher_project())
    except ValueError as exc:
        assert "pas prête" in str(exc)
    else:
        raise AssertionError("Le wrapper Snell legacy doit refuser une configuration non prête.")


def test_dispatch_state_invariants_reject_inconsistent_combinations(tmp_path: Path):
    unresolved = analyze_copy(_source(tmp_path, nbformat.v4.new_notebook(), "unknown.ipynb"))
    assert unresolved.readiness is None
    with pytest.raises(ValueError):
        CopyAnalysisDispatchResult(
            unresolved.resolution, ProjectSelectionProvenance.UNRESOLVED,
            None, AnalysisReadiness.READY,
        )
    with pytest.raises(ValueError):
        CopyAnalysisDispatchResult(
            unresolved.resolution, ProjectSelectionProvenance.AUTO_RESOLVED,
            None, None,
        )

    analyzed = analyze_copy(
        _source(tmp_path, _snell_notebook(), "snell.ipynb"),
        project=snells_laws_teacher_project(),
    )
    assert analyzed.analysis is not None
    with pytest.raises(ValueError):
        CopyAnalysisDispatchResult(
            unresolved.resolution, ProjectSelectionProvenance.UNRESOLVED,
            analyzed.analysis, None,
        )
    with pytest.raises(ValueError):
        CopyAnalysisDispatchResult(
            analyzed.resolution, ProjectSelectionProvenance.EXPLICIT,
            analyzed.analysis, AnalysisReadiness.NOT_READY,
        )


def test_mixed_batch_distinguishes_analyzed_not_ready_and_unresolved(tmp_path: Path):
    result = run_batch((
        BatchCopyRequest("lens", _source(tmp_path, _lens_notebook(), "lens.ipynb"), thin_lens_teacher_project()),
        BatchCopyRequest("snell", _source(tmp_path, _snell_notebook(), "snell.ipynb"), snells_laws_teacher_project()),
        BatchCopyRequest("pendulum", NotebookCopySource("pendulum", PENDULUM.name, PENDULUM), torsion_pendulum_teacher_project()),
        BatchCopyRequest("unknown", _source(tmp_path, nbformat.v4.new_notebook(), "unknown.ipynb")),
    ))
    assert [item.status for item in result.copies] == [
        BatchCopyDispatchStatus.ANALYZED,
        BatchCopyDispatchStatus.ANALYZED,
        BatchCopyDispatchStatus.RESOLVED_NOT_READY,
        BatchCopyDispatchStatus.UNRESOLVED,
    ]
    assert result.error_count == 0
    assert result.resolved_not_ready_count == 1
