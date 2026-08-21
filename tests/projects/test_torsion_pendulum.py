"""A76e2a structural tests for the torsion-pendulum project contract."""

from pathlib import Path

import nbformat

from tpstudio.expectations import ScientificProductionKind
from tpstudio.notebooks.binding_resolution import resolve_notebook_bindings
from tpstudio.projects import (
    known_project_ids,
    project_descriptor,
    resolve_project_for_copy,
    snells_laws_teacher_project,
    thin_lens_teacher_project,
    torsion_pendulum_teacher_project,
)
from tpstudio.orchestration import AnalysisReadiness, assess_analysis_readiness


NOTEBOOK = Path(
    "/Users/daniel/Downloads/TPStudio-prototypes/"
    "Pendule-de-torsion-TPStudio-A76d2-prototype.ipynb"
)


def _notebook():
    return nbformat.read(NOTEBOOK, as_version=4)


def test_torsion_factory_declares_structural_plan_and_bindings():
    project = torsion_pendulum_teacher_project()

    assert project.identity.project_id == "torsion-pendulum"
    assert len(project.scientific_production_plan.productions) == 16
    assert len(project.notebook_binding_plan.bindings) == 17
    assert project.graph_expectation_set is None
    assert project.uncertainty_expectation_set is None
    assert {item.stable_id for item in project.experimental_manipulations} == {
        "dynamic-study", "static-study"
    }
    assert len(project.quantity_expectation_set) == 0
    assert len(project.relation_expectation_set.relations) == 0
    assert len(project.quantity_comparison_expectation_set) == 0
    assert len(project.student_normalized_error_expectation_set) == 0
    assert len(project.comparison_interpretation_expectation_set) == 0
    assert len(project.comparison_justification_expectation_set) == 0
    assert project.feedback_catalogs == ()
    assert assess_analysis_readiness(project) is AnalysisReadiness.NOT_READY


def test_torsion_project_is_registered_and_resolves_confidently():
    notebook = _notebook()
    result = resolve_project_for_copy(
        notebook,
        filename="Pendule-de-torsion-TPStudio-v2-ajuste-v2.ipynb",
    )

    assert result.selected_project_id == "torsion-pendulum"
    assert not result.requires_teacher_choice
    assert project_descriptor("torsion-pendulum") is not None
    assert "torsion-pendulum" in known_project_ids()


def test_torsion_signature_does_not_match_unrelated_notebook():
    notebook = nbformat.v4.new_notebook(
        cells=[nbformat.v4.new_markdown_cell("# Pendule simple\nÉtude de période.")]
    )
    result = resolve_project_for_copy(notebook, filename="pendule-simple.ipynb")
    assert result.selected_project_id is None
    assert not result.candidates


def test_torsion_bindings_are_unique_and_resolve():
    project = torsion_pendulum_teacher_project()
    result = resolve_notebook_bindings(_notebook(), project.notebook_binding_plan)

    assert len(result) == len(project.notebook_binding_plan.bindings)
    assert result.all_resolved
    assert len({item.binding_id for item in result}) == len(result)
    assert {item.production_id for item in result} >= {
        "dynamic_mass", "dynamic_thickness", "dynamic_periods",
        "dynamic_graph", "dynamic_torsion_constant", "bar_inertia",
        "dynamic_interpretation", "static_mass", "static_reference_angle",
        "static_distances", "static_equilibrium_angles", "static_torsion_constant",
        "static_interpretation", "dynamic_static_comparison",
        "normalized_error", "general_conclusion",
    }
    assert "dynamic_model_relation" not in {
        item.production_id for item in result
    }
    assert "static_model_relation" not in {
        item.production_id for item in result
    }
    assert project.scientific_production_plan.get("normalized_error").kind is ScientificProductionKind.QUANTITY
    assert all(
        production.kind is not ScientificProductionKind.RELATION
        for production in project.scientific_production_plan
    )
    assert {
        binding.production_id
        for binding in project.notebook_binding_plan
        if binding.selector.value == "np.polyfit"
    } == {"dynamic_graph"}
    assert {
        binding.production_id
        for binding in project.notebook_binding_plan
        if binding.selector.value == "E_n = ?"
    } == {"normalized_error"}


def test_torsion_reuses_existing_roles_without_changing_other_projects():
    project = torsion_pendulum_teacher_project()
    notebook = _notebook()
    roles = {
        cell.get("metadata", {}).get("tpstudio", {}).get("role")
        for cell in notebook.cells
        if cell.get("metadata", {}).get("tpstudio", {}).get("role")
    }

    assert {"protocol_response", "interpretation_response", "conclusion_response"} <= roles
    assert thin_lens_teacher_project().identity.project_id == "thin-lens-image"
    assert snells_laws_teacher_project().identity.project_id == "snells-laws-mvp"
    assert project.identity.project_id not in {"thin-lens-image", "snells-laws-mvp"}


def test_torsion_plan_uses_existing_production_kinds_only():
    project = torsion_pendulum_teacher_project()
    assert all(isinstance(item.kind, ScientificProductionKind) for item in project.scientific_production_plan)
    assert "dynamic_graph" in {item.id for item in project.scientific_production_plan}
