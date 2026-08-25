from dataclasses import replace

from tpstudio.notebooks import (
    NotebookBindingResolution,
    NotebookBindingResolutionStatus,
    NotebookCellReference,
)
from tpstudio.orchestration import SemanticResponseAnalysis
from tpstudio.projects import first_order_transient_teacher_project
from tpstudio.semantic_analysis import (
    SemanticAnalysisResult,
    SemanticCriterionResult,
    SemanticCriterionStatus,
)
from tpstudio.web.presenters import semantic_response_rows


def _analysis_with_all_statuses():
    project = first_order_transient_teacher_project()
    contract = next(item for item in project.semantic_response_expectations if item.production_id == "leakage_protocol")
    binding = project.notebook_binding_plan.for_production("leakage_protocol")[0]
    text = "### Réponse :\nDéclenchement et acquisition."
    resolution = NotebookBindingResolution(
        binding,
        NotebookBindingResolutionStatus.RESOLVED,
        (2,),
        NotebookCellReference(2, "markdown", None, ()),
        text,
        0,
        len(text),
    )
    statuses = (
        SemanticCriterionStatus.SATISFIED,
        SemanticCriterionStatus.PARTIAL,
        SemanticCriterionStatus.NOT_FOUND,
        SemanticCriterionStatus.UNCERTAIN,
    )
    result = SemanticAnalysisResult(
        "leakage_protocol",
        "Déclenchement et acquisition.",
        tuple(
            SemanticCriterionResult(criterion.criterion_id, status, f"preuve-{status.value}")
            for criterion, status in zip(contract.criteria, statuses)
        ),
        contradictions=("Réglage à examiner.",),
        confidence="high",
        diagnostics=("SEMANTIC_PROVIDER_ERROR:RuntimeError",),
    )
    return SemanticResponseAnalysis(contract, (resolution,), "Déclenchement et acquisition.", result)


def test_semantic_presenter_rows_are_ordered_and_non_scoring():
    row = semantic_response_rows((_analysis_with_all_statuses(),), source_id="copy-1")[0]
    assert row.production_id == "leakage_protocol"
    assert row.role_label == "Protocole"
    assert row.binding_label == "Réponse localisée"
    assert [item.status_label for item in row.criteria] == [
        "Présent", "Partiel", "Non repéré", "À vérifier",
    ]
    assert [item.importance_label for item in row.criteria] == [
        "Requis", "Requis", "Requis", "Recommandé",
    ]
    assert row.student_response.startswith("Déclenchement")
    assert row.contradictions == ("Réglage à examiner.",)
    assert row.confidence == "Haute"
    assert row.diagnostics == ("Erreur contrôlée du fournisseur sémantique.",)
    assert row.stable_key == "semantic-copy-1-leakage_protocol"
    assert row.criteria[0].stable_key == "semantic-copy-1-leakage_protocol-discharge_observation"
    assert row.criteria[0].description == "Proposer d'observer ou d'acquérir la décharge du condensateur."
    assert row.criteria[0].criterion_id != row.criteria[0].description


def test_semantic_presenter_marks_missing_and_ambiguous_bindings_without_student_fault():
    project = first_order_transient_teacher_project()
    contract = project.semantic_response_expectations[0]
    binding = project.notebook_binding_plan.for_production(contract.production_id)[0]
    absent = SemanticResponseAnalysis(
        contract,
        (NotebookBindingResolution(binding, NotebookBindingResolutionStatus.CELL_NOT_FOUND),),
        None,
        None,
    )
    ambiguous = SemanticResponseAnalysis(
        contract,
        (NotebookBindingResolution(binding, NotebookBindingResolutionStatus.CELL_AMBIGUOUS, (1, 2)),),
        None,
        None,
    )
    rows = semantic_response_rows((absent, ambiguous), source_id="copy-1")
    assert [row.binding_label for row in rows] == [
        "Cellule de réponse introuvable", "Cellule de réponse ambiguë",
    ]
    assert rows[0].diagnostics == ("La cellule contenant la réponse n’a pas été trouvée.",)
    assert rows[1].diagnostics == ("Plusieurs cellules peuvent correspondre à cette réponse.",)
    assert all(item.status == "not_evaluated" for row in rows for item in row.criteria)
    assert all(item.status_label == "Non évalué" for row in rows for item in row.criteria)
    assert all(item.evidence == "" for row in rows for item in row.criteria)
    assert all(row.confidence is None for row in rows)
    assert all(row.student_response is None for row in rows)


def test_semantic_presenter_keeps_empty_response_and_safe_diagnostic():
    analysis = _analysis_with_all_statuses()
    empty = replace(
        analysis,
        student_response="",
        result=replace(analysis.result, raw_response="", diagnostics=("EMPTY_RESPONSE",)),
    )
    row = semantic_response_rows((empty,), source_id="copy-empty")[0]
    assert row.student_response == ""
    assert row.diagnostics == ("Réponse vide.",)
