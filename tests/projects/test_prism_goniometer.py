from pathlib import Path

import nbformat

from tpstudio.notebooks import NotebookBindingResolutionStatus, resolve_notebook_bindings
from tpstudio.orchestration import AnalysisReadiness, NotebookCopySource, analyze_copy
from tpstudio.projects import (
    PRISM_GONIOMETER_CORRECTION_FILENAME,
    PRISM_GONIOMETER_STATEMENT_FILENAME,
    prism_goniometer_teacher_project,
    resolve_project_for_copy,
)
from tpstudio.semantic_analysis import SemanticRole


REFERENCE_DIR = (
    Path(__file__).parents[2]
    / "reference-notebooks"
    / "session-03"
    / "prism-goniometer"
)


def _read(filename: str):
    return nbformat.read(REFERENCE_DIR / filename, as_version=4)


def test_identity_references_and_version() -> None:
    project = prism_goniometer_teacher_project()
    assert project.identity.project_id == "prism-goniometer-index"
    assert project.identity.title == "Mesure de l'indice au goniomètre à prisme"
    assert project.identity.version == "A79h1"
    assert project.statement_reference.expected_filename == PRISM_GONIOMETER_STATEMENT_FILENAME
    assert project.correction_reference.expected_filename == PRISM_GONIOMETER_CORRECTION_FILENAME


def test_quantities_and_comparisons_match_the_aligned_notebook() -> None:
    project = prism_goniometer_teacher_project()
    assert tuple(item.production_id for item in project.quantity_expectation_set) == (
        "prism_angle",
        "prism_angle_reference",
        "minimum_deviation",
        "refractive_index",
        "refractive_index_reference",
    )
    assert tuple(
        item.production_id for item in project.quantity_comparison_expectation_set
    ) == ("compare_prism_angle", "compare_refractive_index")


def test_semantic_contracts_follow_student_responses_only() -> None:
    project = prism_goniometer_teacher_project()
    assert tuple(item.production_id for item in project.semantic_response_expectations) == (
        "goniometer_settings",
        "prism_angle_protocol",
        "prism_angle_result",
        "minimum_deviation_protocol",
        "prism_index_result",
        "final_conclusion",
    )
    assert tuple(item.semantic_role for item in project.semantic_response_expectations) == (
        SemanticRole.PROTOCOL,
        SemanticRole.PROTOCOL,
        SemanticRole.INTERPRETATION,
        SemanticRole.PROTOCOL,
        SemanticRole.INTERPRETATION,
        SemanticRole.CONCLUSION,
    )
    settings = project.semantic_response_expectations[0]
    assert any(item.criterion_id == "own_instrument" for item in settings.criteria)


def test_all_bindings_resolve_once_in_statement_and_correction() -> None:
    project = prism_goniometer_teacher_project()
    for filename in (
        PRISM_GONIOMETER_STATEMENT_FILENAME,
        PRISM_GONIOMETER_CORRECTION_FILENAME,
    ):
        resolutions = resolve_notebook_bindings(
            _read(filename), project.notebook_binding_plan
        )
        assert len(resolutions.failures) == 0
        assert len(resolutions.resolved) == len(project.notebook_binding_plan.bindings)
        assert all(
            item.status is NotebookBindingResolutionStatus.RESOLVED
            for item in resolutions
        )


def test_reference_notebooks_resolve_with_high_confidence() -> None:
    for filename in (
        PRISM_GONIOMETER_STATEMENT_FILENAME,
        PRISM_GONIOMETER_CORRECTION_FILENAME,
    ):
        result = resolve_project_for_copy(_read(filename), filename=filename)
        assert result.selected_project_id == "prism-goniometer-index"
        assert result.requires_teacher_choice is False


def test_reference_correction_is_ready_and_numeric_results_are_unique() -> None:
    path = REFERENCE_DIR / PRISM_GONIOMETER_CORRECTION_FILENAME
    result = analyze_copy(NotebookCopySource(path.name, path.name, path))
    assert result.resolution.selected_project_id == "prism-goniometer-index"
    assert result.readiness is AnalysisReadiness.READY
    assert result.analysis is not None
    assert result.analysis.project_id == "prism-goniometer-index"
    assert len(result.analysis.semantic_response_analyses) == 6
    assert all(item.unique for item in result.analysis.observed_value_detections)
