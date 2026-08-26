import nbformat

from tpstudio.expectations import ComparisonPedagogicalContext, PresenceRequirement
from tpstudio.notebooks import resolve_notebook_bindings
from tpstudio.orchestration import AnalysisReadiness, assess_analysis_readiness
from tpstudio.projects import first_lab_measurements_teacher_project
from tpstudio.semantic_analysis import SemanticRole, extract_student_response


def test_project_identity_references_and_readiness():
    project = first_lab_measurements_teacher_project()
    assert project.identity.project_id == "first-lab-measurements"
    assert project.identity.version == "A79d1"
    assert project.statement_reference.expected_filename == "Premieres-mesures-au-labo.ipynb"
    assert project.correction_reference is not None
    assert project.correction_reference.expected_filename == "Premieres-mesures-au-labo-Correction.ipynb"
    assert assess_analysis_readiness(project) is AnalysisReadiness.READY


def test_quantities_graph_and_open_comparison_are_declared():
    project = first_lab_measurements_teacher_project()
    quantities = project.quantity_expectation_set
    assert tuple(item.production_id for item in quantities) == (
        "period_result",
        "dynamic_stiffness",
        "hooke_slope",
        "static_stiffness",
    )
    assert quantities.get("period_result").uncertainty_requirement is PresenceRequirement.OPTIONAL
    assert quantities.get("dynamic_stiffness").uncertainty_requirement is PresenceRequirement.REQUIRED
    assert quantities.get("static_stiffness").uncertainty_requirement is PresenceRequirement.REQUIRED
    graph = project.graph_expectation_set.get("hooke_graph")
    assert (graph.x_expression, graph.y_expression) == ("m_static", "l_static")
    assert graph.expected_model.value == "affine"
    comparison = project.quantity_comparison_expectation_set.get("stiffness_comparison")
    assert comparison.pedagogical_context is ComparisonPedagogicalContext.OPEN
    assert project.student_normalized_error_expectation_set.get("stiffness_comparison").absolute_tolerance.is_finite()


def test_semantic_contracts_follow_notebook_order():
    project = first_lab_measurements_teacher_project()
    assert tuple(item.production_id for item in project.semantic_response_expectations) == (
        "dynamic_objective",
        "dynamic_protocol",
        "period_result_comment",
        "dynamic_stiffness_interpretation",
        "hooke_objective",
        "hooke_protocol",
        "hooke_interpretation",
        "stiffness_comparison_interpretation",
        "final_conclusion",
    )
    assert tuple(item.semantic_role for item in project.semantic_response_expectations) == (
        SemanticRole.OBJECTIVE,
        SemanticRole.PROTOCOL,
        SemanticRole.INTERPRETATION,
        SemanticRole.INTERPRETATION,
        SemanticRole.OBJECTIVE,
        SemanticRole.PROTOCOL,
        SemanticRole.INTERPRETATION,
        SemanticRole.INTERPRETATION,
        SemanticRole.CONCLUSION,
    )


def test_all_bindings_resolve_once_on_aligned_markers():
    project = first_lab_measurements_teacher_project()
    cells = [
        nbformat.v4.new_code_cell('print(f"T = {T_mean:.5f} s")'),
        nbformat.v4.new_code_cell('print(f"k dynamique = {k_dyn:.4f} ± {u_k_dyn:.4f} N/m")'),
        nbformat.v4.new_code_cell('plt.title("Vérification statique de la loi de Hooke")'),
        nbformat.v4.new_code_cell('print(f"a = {a_fit:.5f} m/kg")'),
        nbformat.v4.new_code_cell('print(f"k statique  = {k_static:.4f} ± {u_k_static:.4f} N/m")'),
        nbformat.v4.new_code_cell('print(f"Écart normalisé = {E_N:.3f}")'),
    ]
    for marker in (
        "dynamic-objective-response",
        "dynamic-protocol-response",
        "period-result-response",
        "dynamic-stiffness-interpretation-response",
        "hooke-objective-response",
        "hooke-protocol-response",
        "hooke-interpretation-response",
        "stiffness-comparison-response",
        "final-conclusion-response",
    ):
        cells.append(nbformat.v4.new_markdown_cell(
            f"<!-- {marker} -->\n<div class=\"alert alert-block\">\n### Réponse :\nÀ compléter.\n</div>"
        ))
    notebook = nbformat.v4.new_notebook(cells=cells)
    resolutions = resolve_notebook_bindings(notebook, project.notebook_binding_plan)
    assert len(resolutions) == len(project.notebook_binding_plan.bindings)
    assert all(item.resolved for item in resolutions)


def test_alert_wrapped_blank_response_is_empty():
    source = """<!-- final-conclusion-response -->
<div class=\"alert alert-block\">
### Conclusion générale
Consigne.

### Réponse :
À compléter.
</div>"""
    assert extract_student_response(source) == ""
