import nbformat

from tpstudio.notebooks import resolve_notebook_bindings
from tpstudio.orchestration import (
    GraphCheckStatus,
    assess_analysis_readiness_diagnostics,
    evaluate_saved_graph,
    observe_saved_graph,
)
from tpstudio.projects.first_order_transient import (
    first_order_transient_teacher_project,
)
from tpstudio.projects.project_resolution import resolve_project_for_copy
from tpstudio.semantic_analysis import SemanticRole


def _notebook(source: str):
    return nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source)])


def test_minimal_project_declares_only_charge_graph_and_is_not_ready():
    project = first_order_transient_teacher_project()
    assert project.identity.project_id == "first-order-transient"
    assert "charge_graph" in tuple(item.id for item in project.scientific_production_plan)
    expectation = project.graph_expectation_set.get("charge_graph")
    assert expectation is not None
    assert (expectation.x_expression, expectation.y_expression) == ("t", "uC")
    assert expectation.expected_model is None
    assert any("charge_fit" in item for item in assess_analysis_readiness_diagnostics(project))
    production_ids = {item.id for item in project.scientific_production_plan}
    assert "protocol" not in production_ids
    assert "charge_protocol" not in production_ids
    assert "objective" not in production_ids
    assert {"charge_objective", "energy_objective", "leakage_objective", "leakage_protocol"} <= production_ids


def test_project_attaches_semantic_contracts_in_pedagogical_order():
    project = first_order_transient_teacher_project()
    assert tuple(
        item.production_id for item in project.semantic_response_expectations
    ) == ("charge_objective", "energy_objective", "leakage_protocol")
    assert tuple(item.semantic_role for item in project.semantic_response_expectations) == (
        SemanticRole.OBJECTIVE,
        SemanticRole.OBJECTIVE,
        SemanticRole.PROTOCOL,
    )


def test_binding_resolves_multitrace_charge_cell():
    project = first_order_transient_teacher_project()
    notebook = _notebook("plt.plot(t, uG)\nplt.plot(t, uC)")
    resolved = resolve_notebook_bindings(notebook, project.notebook_binding_plan)
    binding = resolved.get("charge-graph-cell")
    assert binding is not None


def test_text_response_bindings_use_stable_markers():
    project = first_order_transient_teacher_project()
    expected = {
        "charge_objective": "charge-objective-response",
        "energy_objective": "energy-objective-response",
        "leakage_objective": "leakage-objective-response",
        "leakage_protocol": "leakage-protocol-response",
    }
    for production_id, marker in expected.items():
        bindings = project.notebook_binding_plan.for_production(production_id)
        assert len(bindings) == 1
        assert bindings[0].selector.value == marker
        assert bindings[0].selector.kind.value == "source_marker"


def test_charge_graph_selects_uc_with_preloaded_series():
    project = first_order_transient_teacher_project()
    notebook = _notebook("plt.plot(t, uG)\nplt.plot(t, uC)")
    resolution = resolve_notebook_bindings(notebook, project.notebook_binding_plan).get("charge-graph-cell")
    observation = observe_saved_graph(
        notebook,
        resolution,
        {"t": (0.0, 0.1, 0.2), "uG": (0.0, 6.0, 6.0), "uC": (0.0, 2.4, 3.8)},
    )
    assert [item.y_expression for item in observation.series_data] == ["uG", "uC"]
    evaluation = evaluate_saved_graph(project.graph_expectation_set.get("charge_graph"), observation)
    assert evaluation.orientation_status is GraphCheckStatus.MATCHES
    assert evaluation.evaluable


def test_project_resolution_recognizes_first_order_title():
    result = resolve_project_for_copy(_notebook(
        "# Système du premier ordre en régime transitoire\n"
        "uC(t) et tau dans le régime transitoire."
    ))
    assert result.selected_project_id == "first-order-transient"
