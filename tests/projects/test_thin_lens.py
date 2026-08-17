from tpstudio.projects import (
    ExpectedGraphModel,
    snells_laws_teacher_project,
    thin_lens_teacher_project,
)


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
