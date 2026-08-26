from tpstudio.projects import (
    ExpectedGraphModel,
    snells_laws_teacher_project,
    thin_lens_teacher_project,
)
from tpstudio.semantic_analysis import SemanticRole


def test_thin_lens_project_identity_and_graph_contract() -> None:
    project = thin_lens_teacher_project()
    assert project.identity.project_id == "thin-lens-image"
    assert project.identity.title == "Formation d'une image par une lentille mince"
    graph = project.graph_expectation_set.get("conjugation_graph")
    assert graph is not None
    assert graph.x_expression == "1/OA"
    assert graph.y_expression == "1/OA'"
    assert graph.regression_required is True
    assert graph.expected_model is ExpectedGraphModel.AFFINE
    assert graph.slope_quantity_id == "conjugation_slope"
    assert graph.index_quantity_id is None
    assert graph.slope_index_relation_id == "conjugation_relation"
    assert project.identity.version == "A79f1"


def test_thin_lens_quantities_and_comparisons_are_physically_homogeneous() -> None:
    project = thin_lens_teacher_project()
    quantities = project.quantity_expectation_set
    assert tuple(item.production_id for item in quantities) == (
        "single_focal_length",
        "theoretical_focal_length",
        "conjugation_slope",
        "focal_intercept",
        "theoretical_slope",
        "multiple_focal_length",
    )
    comparisons = project.quantity_comparison_expectation_set
    assert tuple(item.production_id for item in comparisons) == (
        "compare_single_theory",
        "compare_conjugation",
        "compare_multiple_theory",
        "compare_single_multiple",
    )
    assert comparisons.get("compare_conjugation").left_quantity_id == "conjugation_slope"
    assert comparisons.get("compare_conjugation").right_quantity_id == "theoretical_slope"


def test_thin_lens_semantic_contracts_follow_notebook_order() -> None:
    project = thin_lens_teacher_project()
    assert tuple(item.production_id for item in project.semantic_response_expectations) == (
        "lens_identification",
        "real_image_protocol",
        "gauss_observation",
        "single_uncertainty_justification",
        "single_result_comment",
        "multiple_protocol",
        "graph_analysis",
        "multiple_result_comment",
        "final_conclusion",
    )
    assert project.semantic_response_expectations[0].semantic_role is SemanticRole.INTERPRETATION
    assert project.semantic_response_expectations[-1].semantic_role is SemanticRole.CONCLUSION


def test_thin_lens_references_are_real_resource_names() -> None:
    project = thin_lens_teacher_project()
    assert project.statement_reference.expected_filename == "Formation-dune-image-par-une-lentille-mince.ipynb"
    assert project.correction_reference.expected_filename == "Correction-Formation-dune-image-par-une-lentille-mince.ipynb"
    assert project.control_copy_reference.expected_filename == "TP_physique_2_Galaad-Louis_Louis[]Galaad.ipynb"


def test_thin_lens_project_does_not_change_snell_contract() -> None:
    snell = snells_laws_teacher_project()
    graph = snell.graph_expectation_set.get("regression_graph")
    assert graph is not None
    assert graph.expected_model is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN
