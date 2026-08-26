from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from tpstudio.projects import (
    ExpectedGraphModel,
    GraphExpectation,
    GraphExpectationSet,
    NotebookReference,
    NotebookReferenceRole,
    TeacherProjectIdentity,
    thin_lens_teacher_project,
    torsion_pendulum_teacher_project,
    snells_laws_teacher_project,
    summarize_teacher_project_configuration,
    validate_teacher_project_configuration,
)
from tpstudio.projects.first_order_transient import (
    CHARGE_OBJECTIVE_SEMANTIC_CONTRACT,
    first_order_transient_teacher_project,
)
from tpstudio.expectations import (
    EvaluationBasis,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
    assess_expectation_sufficiency,
)


def test_notebook_reference_roles_have_exact_values() -> None:
    assert [(item.name, item.value) for item in NotebookReferenceRole] == [
        ("STATEMENT", "statement"),
        ("CORRECTION", "correction"),
        ("CONTROL_COPY", "control_copy"),
    ]


@pytest.mark.parametrize(
    "field",
    ("project_id", "title", "subject", "level", "version", "language"),
)
def test_identity_rejects_blank_required_fields(field: str) -> None:
    values = dict(
        project_id="project", title="Title", subject="Physics", level="CPGE",
        version="v1", language="fr",
    )
    values[field] = "  "
    with pytest.raises(ValueError):
        TeacherProjectIdentity(**values)


def test_identity_is_immutable_and_preserves_text() -> None:
    identity = TeacherProjectIdentity(" id ", " title ", " subject ", " level ", " v ", description=" note ")
    assert identity.project_id == " id "
    assert identity.description == " note "
    with pytest.raises(FrozenInstanceError):
        identity.title = "changed"


@pytest.mark.parametrize(
    "filename",
    ("/tmp/a.ipynb", r"folder\a.ipynb", "folder/a.ipynb", "~/a.ipynb"),
)
def test_notebook_reference_rejects_paths(filename: str) -> None:
    with pytest.raises(ValueError):
        NotebookReference("statement", NotebookReferenceRole.STATEMENT, filename)


def test_notebook_reference_preserves_optional_fields() -> None:
    reference = NotebookReference(
        "statement", NotebookReferenceRole.STATEMENT, "statement.ipynb", "abc", " note "
    )
    assert reference.content_fingerprint == "abc"
    assert reference.description == " note "


def test_configuration_rejects_duplicate_reference_ids() -> None:
    project = snells_laws_teacher_project()
    duplicate = replace(project.notebook_references[1], reference_id="statement")
    with pytest.raises(ValueError):
        replace(project, notebook_references=(project.notebook_references[0], duplicate))


def test_configuration_requires_exactly_one_statement() -> None:
    project = snells_laws_teacher_project()
    without = tuple(item for item in project.notebook_references if item.role is not NotebookReferenceRole.STATEMENT)
    with pytest.raises(ValueError):
        replace(project, notebook_references=without)
    second = NotebookReference("statement-2", NotebookReferenceRole.STATEMENT, "other.ipynb")
    with pytest.raises(ValueError):
        replace(project, notebook_references=(*project.notebook_references, second))


def test_configuration_allows_at_most_one_optional_role() -> None:
    project = snells_laws_teacher_project()
    extra = NotebookReference("correction-2", NotebookReferenceRole.CORRECTION, "other.ipynb")
    with pytest.raises(ValueError):
        replace(project, notebook_references=(*project.notebook_references, extra))


def test_configuration_rejects_foreign_expectation_set() -> None:
    project = snells_laws_teacher_project()
    foreign = snells_laws_teacher_project().quantity_expectation_set
    with pytest.raises(ValueError):
        replace(project, quantity_expectation_set=foreign)


def test_semantic_expectations_default_to_empty_for_legacy_projects() -> None:
    assert torsion_pendulum_teacher_project().semantic_response_expectations == ()


def test_semantic_expectation_rejects_duplicate_production_ids() -> None:
    project = first_order_transient_teacher_project()
    with pytest.raises(ValueError, match="uniques"):
        replace(
            project,
            semantic_response_expectations=(
                CHARGE_OBJECTIVE_SEMANTIC_CONTRACT,
                CHARGE_OBJECTIVE_SEMANTIC_CONTRACT,
            ),
        )


def test_semantic_expectation_rejects_unknown_production() -> None:
    project = first_order_transient_teacher_project()
    unknown = replace(
        CHARGE_OBJECTIVE_SEMANTIC_CONTRACT,
        production_id="unknown",
    )
    with pytest.raises(ValueError, match="Production inconnue"):
        replace(project, semantic_response_expectations=(unknown,))


def test_semantic_expectation_rejects_nonsemantic_production() -> None:
    project = first_order_transient_teacher_project()
    wrong_basis = replace(
        CHARGE_OBJECTIVE_SEMANTIC_CONTRACT,
        production_id="charge_graph",
    )
    with pytest.raises(ValueError, match="SEMANTIC"):
        replace(project, semantic_response_expectations=(wrong_basis,))


def test_semantic_expectation_rejects_wrong_element_type() -> None:
    project = first_order_transient_teacher_project()
    with pytest.raises(TypeError, match="ExpectedSemanticResponse"):
        replace(project, semantic_response_expectations=("not a contract",))


def test_configuration_apis_return_declared_objects() -> None:
    project = snells_laws_teacher_project()
    assert project.statement_reference is project.get_notebook_reference("statement")
    assert project.correction_reference is project.get_notebook_reference("correction")
    assert project.control_copy_reference is project.get_notebook_reference("control-copy")
    assert project.get_production("direct_index").id == "direct_index"
    assert project.get_comparison("compare_direct_geometric").production_id == "compare_direct_geometric"
    assert project.get_production("unknown") is None


def test_global_validation_returns_none_and_rejects_wrong_type() -> None:
    project = snells_laws_teacher_project()
    assert validate_teacher_project_configuration(project) is None
    with pytest.raises(TypeError):
        validate_teacher_project_configuration(object())


def test_summary_is_deterministic_and_contains_no_physical_path() -> None:
    project = snells_laws_teacher_project()
    first = summarize_teacher_project_configuration(project)
    second = summarize_teacher_project_configuration(project)
    assert first == second
    assert "snells-laws-mvp" in first
    assert str(Path.home()) not in first
    assert "COPY_" not in first


def test_project_model_has_no_file_reading_imports() -> None:
    source = Path("src/tpstudio/projects/model.py").read_text(encoding="utf-8")
    assert "import nbformat" not in source
    assert "from pathlib" not in source
    assert ".read_text(" not in source


def test_autonomous_graph_expectation_needs_no_slope_contract() -> None:
    plan = ScientificProductionPlan(
        "autonomous-graph-plan", "Autonomous graph plan", (
            ScientificProductionSpec(
                "plot", "Plot", ScientificProductionKind.PLOT,
                (EvaluationBasis.STRUCTURAL,),
            ),
        ),
    )
    graph = GraphExpectation(
        "plot", "x", "y", ("x",), ("y",), True,
        expected_model=ExpectedGraphModel.AFFINE,
    )
    graph_set = GraphExpectationSet(plan, (graph,))
    assert graph_set.get("plot") is graph
    assert assess_expectation_sufficiency(graph).is_analyzable
