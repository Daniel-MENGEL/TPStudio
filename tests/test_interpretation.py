import nbformat

from tpstudio.interpretation import (
    InterpretationClassification,
    InterpretationContext,
    build_interpretation_contexts,
    build_interpretation_feedback,
    evaluate_interpretation_cells,
)
from tpstudio.protocol import ProtocolStatus


def _cell(text, role=None, expectation_id="i1", manipulation_id=None):
    cell = nbformat.v4.new_markdown_cell(text)
    if role:
        cell.metadata["tpstudio"] = {"role": role, "expectation_id": expectation_id}
        if manipulation_id:
            cell.metadata["tpstudio"]["manipulation_id"] = manipulation_id
    return cell


def test_only_marked_interpretations_trigger():
    notebook = nbformat.v4.new_notebook(cells=[_cell("Le graphe est correct."), _cell("Le graphe est correct.", "interpretation_response")])
    result = evaluate_interpretation_cells(notebook)
    assert len(result) == 1
    assert result[0].status is ProtocolStatus.PRESENT


def test_placeholders_are_missing_and_non_markdown_is_not_evaluable():
    for text in ("", "...", "À compléter : ..."):
        assert evaluate_interpretation_cells(nbformat.v4.new_notebook(cells=[_cell(text, "interpretation_response")]))[0].status is ProtocolStatus.MISSING
    code = nbformat.v4.new_code_cell("x = 1", metadata={"tpstudio": {"role": "interpretation_response", "expectation_id": "i1"}})
    assert evaluate_interpretation_cells(nbformat.v4.new_notebook(cells=[code]))[0].status is ProtocolStatus.NOT_EVALUABLE


def test_clear_insufficient_ambiguous_and_sufficient():
    context = {"i1": InterpretationContext("i1", local_scientific_context=("La valeur est 1,52.",))}
    cases = [
        ("Le graphe est correct.", InterpretationClassification.CLEARLY_INSUFFICIENT),
        ("La courbe augmente.", InterpretationClassification.CLEARLY_INSUFFICIENT),
        ("L'écart est faible, donc c'est bon.", InterpretationClassification.AMBIGUOUS),
        ("L'écart normalisé est inférieur à 2, les deux valeurs sont donc compatibles.", InterpretationClassification.CLEARLY_SUFFICIENT),
    ]
    for text, expected in cases:
        result = evaluate_interpretation_cells(nbformat.v4.new_notebook(cells=[_cell(text, "interpretation_response")]), contexts=context)[0]
        assert result.classification is expected


def test_prompt_does_not_improve_poor_answer():
    notebook = nbformat.v4.new_notebook(cells=[_cell("Comparer tau et RC.", "interpretation_prompt"), _cell("Les résultats sont bons.", "interpretation_response")])
    contexts = build_interpretation_contexts(notebook)
    result = evaluate_interpretation_cells(notebook, contexts=contexts)[0]
    assert result.classification is InterpretationClassification.CLEARLY_INSUFFICIENT


def test_context_filters_other_student_roles_and_keeps_linked_protocol():
    notebook = nbformat.v4.new_notebook(cells=[
        _cell("D'autres résultats", "interpretation_response", "other", "other-manip"),
        _cell("Placer le dispositif et relever les angles.", "protocol_response", "p", "m1"),
        _cell("L'écart normalisé est inférieur à 2, les valeurs sont compatibles.", "interpretation_response", "i1", "m1"),
    ])
    contexts = build_interpretation_contexts(notebook)
    assert "Placer" in contexts["i1"].linked_protocol
    assert all("D'autres" not in value for value in contexts["i1"].local_scientific_context)


def test_local_prompt_only_uses_unmarked_or_explicit_prompt_cell():
    normal = nbformat.v4.new_notebook(cells=[
        _cell("Comparer la valeur mesurée à la valeur attendue."),
        _cell("La courbe augmente.", "interpretation_response"),
    ])
    assert build_interpretation_contexts(normal)["i1"].local_prompt == "Comparer la valeur mesurée à la valeur attendue."
    for role in ("result_response", "production_response", "protocol_response", "conclusion_response", "interpretation_response"):
        notebook = nbformat.v4.new_notebook(cells=[_cell("Réponse précédente", role), _cell("La courbe augmente.", "interpretation_response")])
        assert build_interpretation_contexts(notebook)["i1"].local_prompt is None


def test_missing_reliable_prompt_is_none():
    notebook = nbformat.v4.new_notebook(cells=[_cell("x = 1", "code"), _cell("La courbe augmente.", "interpretation_response")])
    assert build_interpretation_contexts(notebook)["i1"].local_prompt is None


def test_multiple_interpretations_keep_ids_and_feedback_anchors():
    notebook = nbformat.v4.new_notebook(cells=[_cell("Le graphe est correct.", "interpretation_response", "i1"), _cell("La courbe augmente.", "interpretation_response", "i2")])
    evaluations = evaluate_interpretation_cells(notebook)
    feedback = build_interpretation_feedback(evaluations)
    assert [item.expectation_id for item in evaluations] == ["i1", "i2"]
    assert [item.cell_index for item in feedback] == [0, 1]
    assert all(item.cell_index == index for index, item in enumerate(feedback))
