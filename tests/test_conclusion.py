import nbformat

from tpstudio.conclusion import (
    ConclusionContext,
    build_conclusion_feedback,
    build_conclusion_contexts,
    ConclusionQuality,
    evaluate_conclusion_cells,
)
from tpstudio.protocol import ProtocolStatus


def _notebook(source=None, *, role="conclusion_response"):
    cells = []
    if source is not None:
        cell = nbformat.v4.new_markdown_cell(source)
        if role is not None:
            cell.metadata["tpstudio"] = {"role": role, "expectation_id": "conclusion-main"}
        cells.append(cell)
    return nbformat.v4.new_notebook(cells=cells)


def test_empty_and_placeholders_are_missing():
    for text in ("", "...", "À compléter : ..."):
        result = evaluate_conclusion_cells(_notebook(text))[0]
        assert result.status is ProtocolStatus.MISSING


def test_unmarked_markdown_does_not_trigger():
    assert evaluate_conclusion_cells(_notebook("Nous concluons.", role=None)) == ()


def test_prompt_is_not_counted_as_student_response():
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("La conclusion doit préciser tau, RC et la résistance de fuite."),
        nbformat.v4.new_markdown_cell("Nous avons étudié la charge d’un condensateur.", metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "conclusion-main"}}),
    ])
    result = evaluate_conclusion_cells(notebook)[0]
    assert result.status is ProtocolStatus.PRESENT
    assert result.quality is ConclusionQuality.A_REVOIR
    assert not result.results_coverage


def test_synthetic_conclusion_can_be_maximal_without_repeating_all_numbers():
    text = (
        "Nous avons déterminé les deux longueurs d’onde du doublet du sodium. "
        "Les mesures sont compatibles avec les valeurs attendues et l’écart reste cohérent "
        "avec la précision expérimentale. Ainsi, la relation étudiée est vérifiée et la méthode "
        "permet de mettre en évidence le résultat physique recherché."
    )
    result = evaluate_conclusion_cells(_notebook(text), contexts={
        "conclusion-main": ConclusionContext(
            objectives=("Déterminer les longueurs d'onde du sodium",),
            prior_results=("Les valeurs mesurées sont compatibles avec les valeurs attendues.",),
        )
    })[0]
    assert result.status is ProtocolStatus.PRESENT
    assert result.quality is ConclusionQuality.TB


def test_concise_scientific_conclusion_is_not_penalized_by_length():
    text = "La valeur mesurée de l'indice est compatible avec celle du constructeur."
    result = evaluate_conclusion_cells(_notebook(text), contexts={
        "conclusion-main": ConclusionContext(objectives=("Déterminer l'indice",))
    })[0]
    assert result.quality is ConclusionQuality.B


def test_descriptive_conclusion_is_weak():
    result = evaluate_conclusion_cells(_notebook("Nous avons fait plusieurs mesures puis tracé des courbes."))[0]
    assert result.status is ProtocolStatus.PRESENT
    assert result.quality is ConclusionQuality.A_REVOIR


def test_results_without_interpretation_are_not_tb():
    text = "Les résultats obtenus sont 589,0 nm et 589,6 nm. La pente vaut 2,1."
    result = evaluate_conclusion_cells(_notebook(text))[0]
    assert result.status is ProtocolStatus.PRESENT
    assert result.quality is not ConclusionQuality.TB


def test_missing_conclusion_response_is_unchanged_when_absent():
    assert evaluate_conclusion_cells(_notebook(None)) == ()


def test_not_evaluable_when_conclusion_response_is_not_markdown():
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(
        "x = 1", metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "c"}}
    )])
    assert evaluate_conclusion_cells(notebook)[0].status is ProtocolStatus.NOT_EVALUABLE


def test_multiple_marked_conclusions_are_each_reported_not_evaluable():
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("Première", metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "c1"}}),
        nbformat.v4.new_markdown_cell("Seconde", metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "c2"}}),
    ])
    results = evaluate_conclusion_cells(notebook)
    assert [item.expectation_id for item in results] == ["c1", "c2"]
    assert [item.status for item in results] == [ProtocolStatus.PRESENT, ProtocolStatus.PRESENT]


def test_two_missing_conclusions_produce_distinct_cell_anchored_feedback():
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(
            "...", metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "c1"}}
        ),
        nbformat.v4.new_markdown_cell(
            "À compléter : ...", metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "c2"}}
        ),
    ])
    evaluations = evaluate_conclusion_cells(notebook)
    feedback = build_conclusion_feedback(evaluations)
    assert [item.expectation_id for item in evaluations] == ["c1", "c2"]
    assert [item.cell_index for item in feedback] == [0, 1]
    assert len({item.expectation_id for item in feedback}) == 2


def test_context_excludes_other_conclusion_responses_and_keeps_interpretations():
    prior = nbformat.v4.new_markdown_cell(
        "Les résultats sont compatibles.",
        metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "other"}},
    )
    interpretation = nbformat.v4.new_markdown_cell(
        "La comparaison montre un accord avec la théorie.",
        metadata={"tpstudio": {"role": "interpretation_response", "expectation_id": "interp"}},
    )
    response = nbformat.v4.new_markdown_cell(
        "La valeur obtenue est compatible avec la théorie.",
        metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "current"}},
    )
    contexts = build_conclusion_contexts(nbformat.v4.new_notebook(cells=[prior, interpretation, response]))
    assert contexts["current"].prior_results == (interpretation.source,)


def test_context_is_structured_and_never_merged_into_response():
    prompt = nbformat.v4.new_markdown_cell("Mentionner tau, RC et Rf.")
    prompt.metadata["tpstudio"] = {"role": "conclusion_prompt"}
    response = nbformat.v4.new_markdown_cell(
        "Nous avons étudié un condensateur.",
        metadata={"tpstudio": {"role": "conclusion_response", "expectation_id": "c"}},
    )
    notebook = nbformat.v4.new_notebook(cells=[prompt, response])
    contexts = build_conclusion_contexts(notebook)
    assert contexts["c"].local_prompt == "Mentionner tau, RC et Rf."
    evaluation = evaluate_conclusion_cells(notebook, contexts=contexts)[0]
    assert not evaluation.results_coverage
