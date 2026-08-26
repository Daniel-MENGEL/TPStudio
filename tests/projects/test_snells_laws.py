from decimal import Decimal
from pathlib import Path

from tpstudio.expectations import (
    ComparisonJustificationElementKind,
    ComparisonJustificationRequirement,
    ComparisonPedagogicalContext,
    NormalizedErrorThresholds,
    PresenceRequirement,
)
from tpstudio.projects import ExpectedGraphModel, snells_laws_teacher_project
from tpstudio.reasoning import extract_comparison_justification
from tpstudio.semantic_analysis import SemanticRole


def test_factory_is_deterministic_and_returns_fresh_equal_objects() -> None:
    first = snells_laws_teacher_project()
    second = snells_laws_teacher_project()
    assert first == second
    assert first is not second
    assert first.scientific_production_plan is not second.scientific_production_plan


def test_project_identity_and_notebook_references_are_public_safe() -> None:
    project = snells_laws_teacher_project()
    assert project.identity.project_id == "snells-laws-mvp"
    assert project.identity.title == "Lois de Snell-Descartes"
    assert project.identity.level == "CPGE"
    assert project.identity.version == "A79e1"
    assert [item.expected_filename for item in project.notebook_references] == [
        "Lois-de-Snell-Descartes.ipynb",
        "Correction-Lois-de-Snell-Descartes.ipynb",
        "Fausse-copie-etudiant-Lois-de-Snell-Descartes-ameliore.ipynb",
    ]
    assert all(item.content_fingerprint is None for item in project.notebook_references)


def test_production_and_comparison_ids_are_unique_and_semantic() -> None:
    project = snells_laws_teacher_project()
    production_ids = tuple(item.id for item in project.scientific_production_plan)
    comparison_ids = tuple(item.production_id for item in project.quantity_comparison_expectation_set)
    assert len(production_ids) == len(set(production_ids)) == 24
    assert comparison_ids == ("compare_direct_geometric", "compare_geometric_regression")
    assert all("cell" not in identifier and "partie" not in identifier for identifier in production_ids)


def test_bindings_use_source_markers_and_share_the_project_plan() -> None:
    project = snells_laws_teacher_project()
    assert project.notebook_binding_plan.production_plan is project.scientific_production_plan
    assert len(project.notebook_binding_plan.bindings) == 24
    assert all(binding.selector.kind.value == "source_marker" for binding in project.notebook_binding_plan)


def test_semantic_contracts_follow_the_aligned_notebook_order() -> None:
    project = snells_laws_teacher_project()
    assert tuple(item.production_id for item in project.semantic_response_expectations) == (
        "setup_understanding",
        "critical_protocol",
        "direct_result_comment",
        "single_pair_protocol",
        "geometric_result_comment",
        "series_protocol",
        "graph_analysis",
        "compare_geometric_regression",
        "final_conclusion",
    )
    assert project.semantic_response_expectations[0].semantic_role is SemanticRole.PROTOCOL
    assert project.semantic_response_expectations[-1].semantic_role is SemanticRole.CONCLUSION


def test_quantities_declare_angles_and_dimensionless_results() -> None:
    quantities = snells_laws_teacher_project().quantity_expectation_set
    assert quantities.get("incidence_angle").canonical_unit == "°"
    assert quantities.get("refraction_angle").accepted_units == ("deg",)
    assert quantities.get("direct_index").unit_requirement is PresenceRequirement.IGNORE
    assert quantities.get("regression_slope").canonical_unit is None
    assert quantities.get("regression_index").uncertainty_requirement is PresenceRequirement.REQUIRED


def test_uncertainty_policies_are_distinct_from_recognition_tolerance() -> None:
    project = snells_laws_teacher_project()
    assert project.uncertainty_expectation_set.get("direct_index") is not None
    assert project.uncertainty_expectation_set.get("regression_slope") is None
    assert all(item.absolute_tolerance == Decimal("0.05") for item in project.student_normalized_error_expectation_set)


def test_relations_include_snell_direct_geometric_slope_and_normalized_error() -> None:
    relations = snells_laws_teacher_project().relation_expectation_set
    assert tuple(item.id for item in relations.relations) == (
        "snell_relation", "direct_index_relation", "geometric_index_relation",
        "slope_index_relation", "normalized_error_relation",
    )
    assert relations.relation_by_id("slope_index_relation").canonical_expression == "a = n"


def test_graph_orientation_and_slope_index_relation_are_explicit() -> None:
    graph = snells_laws_teacher_project().graph_expectation_set.get("regression_graph")
    assert graph.x_expression == "sin(i2)"
    assert graph.y_expression == "sin(i1)"
    assert graph.regression_required
    assert graph.slope_quantity_id == "regression_slope"
    assert graph.index_quantity_id == "regression_index"
    assert graph.slope_index_relation_id == "slope_index_relation"
    assert not graph.title_required
    assert graph.legend_required
    assert graph.expected_model is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN


def test_comparisons_keep_standard_thresholds_and_declared_contexts() -> None:
    comparisons = snells_laws_teacher_project().quantity_comparison_expectation_set
    assert all(item.thresholds == NormalizedErrorThresholds() for item in comparisons)
    assert comparisons.get("compare_direct_geometric").pedagogical_context is ComparisonPedagogicalContext.OPEN
    assert comparisons.get("compare_geometric_regression").pedagogical_context is ComparisonPedagogicalContext.INCOHERENCE_POSSIBLE


def test_student_normalized_error_expectations_have_explicit_labels() -> None:
    expectations = snells_laws_teacher_project().student_normalized_error_expectation_set
    assert len(expectations) == 2
    assert all(item.labels == ("E_n", "En") for item in expectations)


def test_literal_interpretations_are_small_and_declared() -> None:
    expectations = snells_laws_teacher_project().comparison_interpretation_expectation_set
    assert len(expectations) == 2
    assert all(len(item.phrases) == 6 for item in expectations)
    assert any(phrase == "Les mesures sont cohérentes" for _, phrase in expectations.expectations[0].phrases)


def test_justifications_use_required_and_optional_without_inventing_group_obligations() -> None:
    expectations = snells_laws_teacher_project().comparison_justification_expectation_set
    first = expectations.get("compare_direct_geometric")
    second = expectations.get("compare_geometric_regression")
    assert [item.requirement for item in first.elements].count(ComparisonJustificationRequirement.REQUIRED) == 3
    assert any(item.requirement is ComparisonJustificationRequirement.OPTIONAL for item in second.elements)
    assert all(item.requirement is not ComparisonJustificationRequirement.ONE_OF_GROUP for item in second.elements)


def test_justification_threshold_phrases_cover_all_objective_domains() -> None:
    expectations = snells_laws_teacher_project().comparison_justification_expectation_set
    for expectation in expectations:
        phrases = expectation.elements[1].phrases
        assert "En < 2" in phrases
        assert "En >= 2" in phrases or "supérieur à 2" in phrases
        assert "En >= 4" in phrases or "supérieur à 4" in phrases


def test_justification_classification_phrases_align_with_interpretations() -> None:
    project = snells_laws_teacher_project()
    interpretation = project.comparison_interpretation_expectation_set.expectations[0]
    expected_phrases = {
        phrase
        for kind, phrase in interpretation.phrases
        if kind.value != "method_limitation"
    }
    for justification in project.comparison_justification_expectation_set:
        classification = next(
            element for element in justification.elements
            if element.kind is ComparisonJustificationElementKind.COHERENCE_CLASSIFICATION
        )
        assert expected_phrases <= set(classification.phrases)


def test_justification_phrases_are_globally_unique_per_expectation() -> None:
    expectations = snells_laws_teacher_project().comparison_justification_expectation_set
    for expectation in expectations:
        phrases = tuple(phrase for element in expectation.elements for phrase in element.phrases)
        assert len(phrases) == len(set(phrases))


def test_literal_justification_detects_moderate_incoherence_elements() -> None:
    expectation = (
        snells_laws_teacher_project().comparison_justification_expectation_set
        .get("compare_direct_geometric")
    )
    detection = extract_comparison_justification(
        "En = 2,8. Comme En est supérieur à 2, les mesures ne sont pas cohérentes.",
        expectation,
    )
    assert {
        ComparisonJustificationElementKind.NORMALIZED_ERROR_VALUE,
        ComparisonJustificationElementKind.THRESHOLD_REFERENCE,
        ComparisonJustificationElementKind.COHERENCE_CLASSIFICATION,
    } <= set(detection.observed_kinds)


def test_literal_justification_detects_strong_incoherence_elements() -> None:
    expectation = (
        snells_laws_teacher_project().comparison_justification_expectation_set
        .get("compare_geometric_regression")
    )
    detection = extract_comparison_justification(
        "En = 5,1. Comme En est supérieur à 4, les résultats sont fortement incohérents.",
        expectation,
    )
    assert {
        ComparisonJustificationElementKind.NORMALIZED_ERROR_VALUE,
        ComparisonJustificationElementKind.THRESHOLD_REFERENCE,
        ComparisonJustificationElementKind.COHERENCE_CLASSIFICATION,
    } <= set(detection.observed_kinds)


def test_feedback_catalogs_are_explicit_typed_and_not_global() -> None:
    catalogs = snells_laws_teacher_project().feedback_catalogs
    assert [type(item).__name__ for item in catalogs] == [
        "QuantityFeedbackCatalog", "QuantityComparisonFeedbackCatalog",
        "ComparisonInterpretationFeedbackCatalog", "ComparisonJustificationFeedbackCatalog",
    ]
    assert len({type(item) for item in catalogs}) == len(catalogs)


def test_configuration_contains_no_results_grading_or_private_data() -> None:
    project = snells_laws_teacher_project()
    text = repr(project)
    forbidden = (str(Path.home()), "COPY_A", "score=", "grade=", "penalty=")
    assert not any(item in text for item in forbidden)


def test_imported_configuration_module_has_no_side_effect_dependencies() -> None:
    source = Path("src/tpstudio/projects/snells_laws.py").read_text(encoding="utf-8")
    assert "nbformat" not in source
    assert "pathlib" not in source
    assert "open(" not in source
    assert "os.environ" not in source
