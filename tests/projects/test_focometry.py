from pathlib import Path

import nbformat

from tpstudio.notebooks import NotebookBindingResolutionStatus, resolve_notebook_bindings
from tpstudio.orchestration import AnalysisReadiness, NotebookCopySource, analyze_copy
from tpstudio.projects import (
    FOCOMETRY_CORRECTION_FILENAME,
    FOCOMETRY_STATEMENT_FILENAME,
    focometry_teacher_project,
    resolve_project_for_copy,
)
from tpstudio.semantic_analysis import SemanticRole


REFERENCE_DIR = (
    Path(__file__).parents[2]
    / "reference-notebooks"
    / "session-03"
    / "focometry"
)


def _read(filename: str):
    return nbformat.read(REFERENCE_DIR / filename, as_version=4)


def test_focometry_identity_and_references() -> None:
    project = focometry_teacher_project()
    assert project.identity.project_id == "optical-instruments-focometry"
    assert project.identity.title == "Instruments d'optique et application à la focométrie"
    assert project.identity.version == "A79g1"
    assert project.statement_reference.expected_filename == FOCOMETRY_STATEMENT_FILENAME
    assert project.correction_reference.expected_filename == FOCOMETRY_CORRECTION_FILENAME


def test_focometry_quantities_and_comparisons_follow_the_methods() -> None:
    project = focometry_teacher_project()
    assert tuple(item.production_id for item in project.quantity_expectation_set) == (
        "autocollimation_focal_length",
        "plus5_theoretical_focal_length",
        "diverging_box_focal_length",
        "minus2_theoretical_focal_length",
        "bessel_focal_length",
        "plus33_theoretical_focal_length",
        "collimator_focal_length",
        "vff_focal_length",
    )
    assert tuple(item.production_id for item in project.quantity_comparison_expectation_set) == (
        "compare_autocollimation_theory",
        "compare_diverging_box_theory",
        "compare_bessel_theory",
        "compare_collimator_theory",
        "compare_bessel_collimator",
        "compare_vff_theory",
        "compare_vff_box",
    )


def test_vff_productions_are_optional() -> None:
    project = focometry_teacher_project()
    for production_id in (
        "vff_focal_length",
        "compare_vff_theory",
        "compare_vff_box",
    ):
        assert project.get_production(production_id).required is False
    assert all(
        "vff" not in item.production_id
        for item in project.semantic_response_expectations
    )


def test_vff_uses_the_same_minus_two_lens_and_compares_both_f2_measurements() -> None:
    project = focometry_teacher_project()
    comparison = project.quantity_comparison_expectation_set.get("compare_vff_box")
    assert {comparison.left_quantity_id, comparison.right_quantity_id} == {
        "vff_focal_length",
        "diverging_box_focal_length",
    }
    for filename in (FOCOMETRY_STATEMENT_FILENAME, FOCOMETRY_CORRECTION_FILENAME):
        notebook = _read(filename)
        setup = next(cell.source for cell in notebook.cells if cell.id == "tpstudio-019")
        result = next(cell.source for cell in notebook.cells if cell.id == "tpstudio-022")
        calculation = next(cell.source for cell in notebook.cells if cell.id == "tpstudio-021")
        assert "$-2$" in setup
        assert "$-6,6$" not in setup
        assert "E_n_viseur_boite = ecart_normalise(f2_viseur, u_f2_viseur, f2, u_f2)" in calculation
        assert "boîte de verre" in result


def test_semantic_contracts_follow_required_notebook_responses() -> None:
    project = focometry_teacher_project()
    assert tuple(item.production_id for item in project.semantic_response_expectations) == (
        "autocollimation_protocol",
        "autocollimation_result_comment",
        "diverging_box_protocol",
        "diverging_box_result_comment",
        "bessel_protocol",
        "bessel_result_comment",
        "collimator_protocol",
        "collimator_result_comment",
        "final_conclusion",
    )
    assert tuple(item.semantic_role for item in project.semantic_response_expectations) == (
        SemanticRole.PROTOCOL,
        SemanticRole.INTERPRETATION,
        SemanticRole.PROTOCOL,
        SemanticRole.INTERPRETATION,
        SemanticRole.PROTOCOL,
        SemanticRole.INTERPRETATION,
        SemanticRole.PROTOCOL,
        SemanticRole.INTERPRETATION,
        SemanticRole.CONCLUSION,
    )


def test_all_bindings_resolve_once_in_statement_and_correction() -> None:
    project = focometry_teacher_project()
    for filename in (FOCOMETRY_STATEMENT_FILENAME, FOCOMETRY_CORRECTION_FILENAME):
        resolutions = resolve_notebook_bindings(_read(filename), project.notebook_binding_plan)
        assert len(resolutions.failures) == 0
        assert len(resolutions.resolved) == len(project.notebook_binding_plan.bindings)
        assert all(
            item.status is NotebookBindingResolutionStatus.RESOLVED
            for item in resolutions
        )


def test_reference_notebooks_resolve_to_focometry_with_high_confidence() -> None:
    for filename in (FOCOMETRY_STATEMENT_FILENAME, FOCOMETRY_CORRECTION_FILENAME):
        result = resolve_project_for_copy(_read(filename), filename=filename)
        assert result.selected_project_id == "optical-instruments-focometry"
        assert result.requires_teacher_choice is False


def test_reference_correction_is_ready_for_complete_analysis() -> None:
    path = REFERENCE_DIR / FOCOMETRY_CORRECTION_FILENAME
    result = analyze_copy(NotebookCopySource(path.name, path.name, path))
    assert result.resolution.selected_project_id == "optical-instruments-focometry"
    assert result.readiness is AnalysisReadiness.READY
    assert result.analysis is not None
    assert result.analysis.project_id == "optical-instruments-focometry"
    assert len(result.analysis.semantic_response_analyses) == 9


def test_focal_length_answers_require_an_explicit_result_with_uncertainty_and_unit() -> None:
    result_markers = (
        "autocollimation-result-response",
        "diverging-box-result-response",
        "bessel-result-response",
        "collimator-result-response",
        "vff-result-response",
    )
    for filename, expected_count in (
        (FOCOMETRY_STATEMENT_FILENAME, 1),
        (FOCOMETRY_CORRECTION_FILENAME, 2),
    ):
        notebook = _read(filename)
        for marker in result_markers:
            cell = next(cell for cell in notebook.cells if marker in cell.source)
            assert cell.source.count(r"\pm") >= expected_count
            assert r"\mathrm{cm}" in cell.source
