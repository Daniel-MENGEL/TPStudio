"""A76e2a structural tests for the torsion-pendulum project contract."""

from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace

import nbformat

from tpstudio.expectations import (
    DerivedQuantityExpectationSet,
    DerivedSourceResolutionStatus,
    ExpectedDerivedQuantity,
    OperandRef,
    ScientificProductionKind,
    TeacherConstant,
    assess_expectation_sufficiency,
)
from tpstudio.graph_analysis import GraphAnalysis, GraphAnalysisTechnicalStatus
from tpstudio.orchestration.observed_values import ObservedScalarValue, ObservedValueSource
from tpstudio.notebooks.binding_resolution import resolve_notebook_bindings
from tpstudio.projects import (
    known_project_ids,
    project_descriptor,
    resolve_project_for_copy,
    snells_laws_teacher_project,
    thin_lens_teacher_project,
    torsion_pendulum_teacher_project,
)
from tpstudio.orchestration import (
    AnalysisReadiness,
    assess_analysis_readiness,
    assess_analysis_readiness_diagnostics,
    evaluate_configured_derived_quantities,
)


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
    assert len(project.derived_quantity_expectation_set) == 1
    assert project.derived_quantity_expectation_set.get("bar_inertia") is not None
    assert len(project.relation_expectation_set.relations) == 0
    assert len(project.quantity_comparison_expectation_set) == 0
    assert len(project.student_normalized_error_expectation_set) == 0
    assert len(project.comparison_interpretation_expectation_set) == 0
    assert len(project.comparison_justification_expectation_set) == 0
    assert project.feedback_catalogs == ()
    assert assess_analysis_readiness(project) is AnalysisReadiness.NOT_READY
    diagnostics = assess_analysis_readiness_diagnostics(project)
    assert not any("bar_inertia: aucune attente quantitative" in item for item in diagnostics)
    assert not any("bar_inertia" in item for item in diagnostics)


def test_bar_inertia_derived_expectation_is_valid_analyzable_and_non_competing():
    project = torsion_pendulum_teacher_project()
    expectation = project.derived_quantity_expectation_set.get("bar_inertia")
    assert expectation is not None
    assert project.derived_quantity_expectation_set.get("dynamic_torsion_constant") is None
    assert project.quantity_expectation_set.get("bar_inertia") is None
    assert assess_expectation_sufficiency(expectation).is_analyzable
    assert project.derived_quantity_expectation_set.get("bar_inertia") is expectation


def test_configured_bar_inertia_runs_isolated_without_analyze_copy_activation():
    project = torsion_pendulum_teacher_project()
    expectation = project.derived_quantity_expectation_set.get("bar_inertia")
    assert expectation is not None
    graph = GraphAnalysis(
        "dynamic-graph-series", None, 0, 4, "AFFINE", 2.0, 1.2,
        0.0, 0.0, 0.0, "none", "none", 1.0, 4, None, None, 0.0,
        0.0, "unavailable", "none", GraphAnalysisTechnicalStatus.EVALUABLE, None, (), False,
    )
    quantity = ObservedScalarValue(
        "dynamic_torsion_constant", ObservedValueSource.CODE_LITERAL,
        Decimal("10"), None, 0, "C = 10",
    )
    copy_result = SimpleNamespace(
        quantity_evaluations=(SimpleNamespace(
            production_id="dynamic_torsion_constant",
            assessment=SimpleNamespace(selected_observation=quantity),
        ),),
        graph_analyses=(graph,),
        regression_model_analyses=(),
        graph_evaluations=(SimpleNamespace(
            expectation=SimpleNamespace(production_id="dynamic_graph"),
            observation=SimpleNamespace(series_data=(SimpleNamespace(series_id="dynamic-graph-series"),)),
        ),),
    )
    results = evaluate_configured_derived_quantities(project, copy_result)
    assert len(results) == 1
    runtime = next(result for result in results if result.production_id == "bar_inertia")
    expectation = project.derived_quantity_expectation_set.get("bar_inertia")
    assert runtime.expectation is expectation
    assert runtime.production_id == "bar_inertia"
    assert runtime.resolution.status is DerivedSourceResolutionStatus.RESOLVED
    assert runtime.evaluation is not None
    assert runtime.evaluation.value == Decimal("0.3039635509270133143316383896")
    assert assess_analysis_readiness(project) is AnalysisReadiness.NOT_READY


def test_multiple_derived_expectations_share_context_and_fail_independently():
    from dataclasses import replace

    project = torsion_pendulum_teacher_project()
    bar = project.derived_quantity_expectation_set.get("bar_inertia")
    constant = TeacherConstant("synthetic-mass", Decimal("2"))
    mass = ExpectedDerivedQuantity("dynamic_mass", "m", (constant,), OperandRef(constant))
    configured = replace(
        project,
        derived_quantity_expectation_set=DerivedQuantityExpectationSet((bar, mass)),
    )
    graph = GraphAnalysis(
        "dynamic-graph-series", None, 0, 4, "AFFINE", 2.0, 1.2,
        0.0, 0.0, 0.0, "none", "none", 1.0, 4, None, None, 0.0,
        0.0, "unavailable", "none", GraphAnalysisTechnicalStatus.EVALUABLE, None, (), False,
    )
    copy_result = SimpleNamespace(
        quantity_evaluations=(),
        graph_analyses=(graph,),
        regression_model_analyses=(),
        graph_evaluations=(SimpleNamespace(
            expectation=SimpleNamespace(production_id="dynamic_graph"),
            observation=SimpleNamespace(series_data=(SimpleNamespace(series_id="dynamic-graph-series"),)),
        ),),
    )
    results = evaluate_configured_derived_quantities(configured, copy_result)
    assert len(results) == 2
    by_production = {item.production_id: item for item in results}
    assert set(by_production) == {"bar_inertia", "dynamic_mass"}
    reordered = {item.production_id: item for item in reversed(results)}
    assert reordered["bar_inertia"] is by_production["bar_inertia"]
    assert reordered["dynamic_mass"] is by_production["dynamic_mass"]
    assert by_production["bar_inertia"].resolution.status is DerivedSourceResolutionStatus.MISSING_PRODUCTION
    assert by_production["dynamic_mass"].evaluation is not None
    assert by_production["dynamic_mass"].evaluation.value == Decimal("2")


def test_all_derived_quantities_do_not_create_false_ready_without_runtime_dispatch():
    from dataclasses import replace

    project = torsion_pendulum_teacher_project()
    derived = []
    for production in project.scientific_production_plan:
        if production.kind is not ScientificProductionKind.QUANTITY:
            continue
        constant = TeacherConstant(f"constant-{production.id}", Decimal("1"))
        derived.append(ExpectedDerivedQuantity(
            production.id, production.id, (constant,), OperandRef(constant)
        ))
    covered = replace(
        project,
        derived_quantity_expectation_set=DerivedQuantityExpectationSet(tuple(derived)),
    )
    diagnostics = assess_analysis_readiness_diagnostics(covered)
    assert assess_analysis_readiness(covered) is AnalysisReadiness.NOT_READY
    assert not any("exécution runtime non raccordée" in item for item in diagnostics)
    assert not any("bar_inertia: aucune attente quantitative" in item for item in diagnostics)


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
