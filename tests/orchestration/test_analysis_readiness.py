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
    ExpectedQuantity,
    EvaluationBasis,
    PresenceRequirement,
    QuantityExpectationSet,
    QuantityComparisonExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
    ExpectationSet,
    StudentNormalizedErrorExpectationSet,
    ComparisonInterpretationExpectationSet,
    ComparisonJustificationExpectationSet,
)
from tpstudio.projects import (
    first_order_transient_teacher_project,
    snells_laws_teacher_project,
    thin_lens_teacher_project,
    torsion_pendulum_teacher_project,
)
from tests.orchestration.test_copy_analysis import (
    _RecordingSemanticProvider,
    _first_order_notebook,
)
from tpstudio.projects.model import (
    NotebookReference,
    NotebookReferenceRole,
    TeacherProjectConfiguration,
    TeacherProjectIdentity,
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


def test_symbol_only_expectation_is_not_ready_even_with_valid_binding():
    plan = ScientificProductionPlan(
        "synthetic", "Synthetic", (
            ScientificProductionSpec(
                "q", "Quantity q", ScientificProductionKind.QUANTITY,
                (EvaluationBasis.STRUCTURAL,),
            ),
        ),
    )
    binding_plan = NotebookBindingPlan(
        "synthetic-bindings", "Synthetic bindings", plan,
        (CellProductionBinding(
            "q-binding", "q",
            NotebookCellSelector(NotebookCellSelectorKind.SOURCE_MARKER, "q = ?"),
            CellTextScope.full_source(),
        ),),
    )
    quantities = QuantityExpectationSet(
        plan, (ExpectedQuantity(
            "q", "q",
            unit_requirement=PresenceRequirement.OPTIONAL,
            uncertainty_requirement=PresenceRequirement.IGNORE,
        ),),
    )
    comparisons = QuantityComparisonExpectationSet(plan, quantities, ())
    project = TeacherProjectConfiguration(
        TeacherProjectIdentity("synthetic", "Synthetic", "Physique", "Lycée", "test"),
        (NotebookReference("statement", NotebookReferenceRole.STATEMENT, "statement.tex"),),
        plan, binding_plan, quantities, ExpectationSet("relations", "Relations"),
        None, None, comparisons,
        StudentNormalizedErrorExpectationSet(comparisons, ()),
        ComparisonInterpretationExpectationSet(comparisons, ()),
        ComparisonJustificationExpectationSet(comparisons, ()), (),
    )
    assert assess_analysis_readiness(project) is AnalysisReadiness.NOT_READY


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


def test_not_ready_first_order_exposes_ordered_semantic_preview(tmp_path: Path):
    notebook = _first_order_notebook()
    source = _source(tmp_path, notebook, "first-order.ipynb")
    provider = _RecordingSemanticProvider()
    before = source.path.read_bytes()
    result = analyze_copy(
        source,
        project=first_order_transient_teacher_project(),
        semantic_provider=provider,
    )
    assert result.analysis is None
    assert result.readiness is AnalysisReadiness.NOT_READY
    assert [item.contract.production_id for item in result.semantic_response_analyses] == [
        "charge_objective", "energy_objective", "leakage_protocol",
    ]
    assert len(provider.calls) == 3
    assert source.path.read_bytes() == before


def test_auto_high_first_order_preview_is_not_a_complete_analysis(tmp_path: Path):
    notebook = _first_order_notebook()
    notebook.cells.insert(
        0,
        nbformat.v4.new_markdown_cell(
            "# Système du premier ordre en régime transitoire\n"
            "Étude de uC(t) et du régime transitoire."
        ),
    )
    source = _source(
        tmp_path,
        notebook,
        "Systeme-du-premier-ordre-en-regime-transitoire-TPStudio-v2.1.ipynb",
    )
    provider = _RecordingSemanticProvider()
    result = analyze_copy(source, semantic_provider=provider)
    assert result.provenance is ProjectSelectionProvenance.AUTO_RESOLVED
    assert result.resolution.requires_teacher_choice is False
    assert result.resolution.selected_project_id == "first-order-transient"
    assert result.readiness is AnalysisReadiness.NOT_READY
    assert result.analysis is None
    assert [item.contract.production_id for item in result.semantic_response_analyses] == [
        "charge_objective", "energy_objective", "leakage_protocol",
    ]
    assert len(provider.calls) == 3


def test_preview_uses_explicit_replaced_project_configuration(tmp_path: Path):
    base = first_order_transient_teacher_project()
    adapted = replace(base, semantic_response_expectations=(base.semantic_response_expectations[0],))
    result = analyze_copy(
        _source(tmp_path, _first_order_notebook(), "first-order.ipynb"),
        project=adapted,
        semantic_provider=_RecordingSemanticProvider(),
    )
    assert result.semantic_project is adapted
    assert tuple(item.contract for item in result.semantic_response_analyses) == (
        adapted.semantic_response_expectations[0],
    )


def test_preview_rejects_configuration_contract_divergence(tmp_path: Path):
    base = first_order_transient_teacher_project()
    adapted = replace(base, semantic_response_expectations=(base.semantic_response_expectations[0],))
    result = analyze_copy(
        _source(tmp_path, _first_order_notebook(), "first-order.ipynb"),
        project=adapted,
        semantic_provider=_RecordingSemanticProvider(),
    )
    with pytest.raises(ValueError, match="configuration exacte"):
        CopyAnalysisDispatchResult(
            result.resolution,
            ProjectSelectionProvenance.EXPLICIT,
            None,
            AnalysisReadiness.NOT_READY,
            result.semantic_response_analyses,
            base,
        )


def test_not_ready_without_provider_has_empty_semantic_preview(tmp_path: Path):
    result = analyze_copy(
        _source(tmp_path, _first_order_notebook(), "first-order.ipynb"),
        project=first_order_transient_teacher_project(),
    )
    assert result.readiness is AnalysisReadiness.NOT_READY
    assert result.analysis is None
    assert result.semantic_response_analyses == ()


def test_unresolved_copy_never_creates_semantic_preview(tmp_path: Path):
    provider = _RecordingSemanticProvider()
    result = analyze_copy(
        _source(tmp_path, nbformat.v4.new_notebook(), "unknown.ipynb"),
        semantic_provider=provider,
    )
    assert result.semantic_response_analyses == ()
    assert provider.calls == []


def test_not_ready_preview_preserves_missing_ambiguous_empty_and_provider_error(tmp_path: Path):
    provider = _RecordingSemanticProvider(raises=True)
    result = analyze_copy(
        _source(
            tmp_path,
            _first_order_notebook(
                omit_marker="energy-objective-response",
                duplicate_marker="leakage-protocol-response",
            ),
            "first-order-invalid-responses.ipynb",
        ),
        project=first_order_transient_teacher_project(),
        semantic_provider=provider,
    )
    assert result.readiness is AnalysisReadiness.NOT_READY
    assert result.analysis is None
    assert len(provider.calls) == 1
    by_id = {item.contract.production_id: item for item in result.semantic_response_analyses}
    assert by_id["energy_objective"].binding_absent
    assert by_id["energy_objective"].result is None
    assert by_id["leakage_protocol"].binding_ambiguous
    assert by_id["leakage_protocol"].result is None
    assert by_id["charge_objective"].result is not None
    assert by_id["charge_objective"].result.diagnostics[0].startswith("SEMANTIC_PROVIDER_ERROR:")


def test_not_ready_preview_empty_response_is_controlled_without_provider_call(tmp_path: Path):
    provider = _RecordingSemanticProvider()
    result = analyze_copy(
        _source(
            tmp_path,
            _first_order_notebook(empty_marker="charge-objective-response"),
            "first-order-empty-response.ipynb",
        ),
        project=first_order_transient_teacher_project(),
        semantic_provider=provider,
    )
    charge = result.semantic_response_analyses[0]
    assert charge.result is not None
    assert "EMPTY_RESPONSE" in charge.result.diagnostics
    assert len(provider.calls) == 2


def test_historical_project_without_contract_keeps_empty_preview(tmp_path: Path):
    project = replace(snells_laws_teacher_project(), semantic_response_expectations=())
    result = analyze_copy(
        _source(tmp_path, _snell_notebook(), "snell.ipynb"),
        project=project,
        semantic_provider=_RecordingSemanticProvider(),
    )
    assert result.semantic_response_analyses == ()


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
