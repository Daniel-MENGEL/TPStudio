from __future__ import annotations

import hashlib

import nbformat

from tpstudio.interpretation import (
    InterpretationClassification,
    InterpretationContext,
    InterpretationFeedbackItem,
    InterpretationReviewTrace,
    build_interpretation_review_traces,
    evaluate_interpretation_cells,
)
from tpstudio.review_store import (
    append_interpretation_review,
    latest_interpretation_review,
    load_interpretation_reviews,
    resolve_interpretation_review,
    review_store_path,
)


def _trace(*, sha: str, decision=None, cell_id="cell-1"):
    return InterpretationReviewTrace(
        1, "copy-001", sha, "interp-1", cell_id, 2, "La valeur est compatible.",
        InterpretationContext("interp-1", local_prompt="Interpréter le résultat."),
        InterpretationClassification.AMBIGUOUS,
        "Interprétation à revoir.", decision, "Retour enseignant" if decision else None,
        "2026-08-14T12:00:00+00:00" if decision else None,
    )


def test_trace_status_and_round_trip_serialization():
    sha = hashlib.sha256(b"copy").hexdigest()
    pending = _trace(sha=sha)
    assert pending.review_status == "PENDING"
    confirmed = _trace(sha=sha, decision=InterpretationClassification.AMBIGUOUS)
    replaced = _trace(sha=sha, decision=InterpretationClassification.CLEARLY_SUFFICIENT)
    assert confirmed.review_status == "CONFIRMED"
    assert replaced.review_status == "REPLACED"
    assert InterpretationReviewTrace.from_dict(confirmed.to_dict()) == confirmed


def test_trace_reviewed_at_and_context_invariants():
    sha = hashlib.sha256(b"copy").hexdigest()
    assert _trace(sha=sha).review_status == "PENDING"
    import pytest
    with pytest.raises(ValueError, match="PENDING"):
        InterpretationReviewTrace(
            1, "copy-001", sha, "interp-1", "cell-1", 2, "Réponse.",
            InterpretationContext("interp-1"), InterpretationClassification.AMBIGUOUS,
            None, None, None, "2026-08-14T12:00:00+00:00",
        )
    with pytest.raises(ValueError, match="reviewed_at"):
        InterpretationReviewTrace(
            1, "copy-001", sha, "interp-1", "cell-1", 2, "Réponse.",
            InterpretationContext("interp-1"), InterpretationClassification.AMBIGUOUS,
            None, InterpretationClassification.AMBIGUOUS, None, None,
        )
    with pytest.raises(TypeError, match="local_context"):
        InterpretationReviewTrace(
            1, "copy-001", sha, "interp-1", "cell-1", 2, "Réponse.",
            "contexte", InterpretationClassification.AMBIGUOUS, None,
        )


def test_trace_cell_id_and_deterministic_fallback_do_not_collide():
    cells = [
        nbformat.v4.new_markdown_cell("La valeur est compatible.", metadata={"tpstudio": {"role": "interpretation_response", "expectation_id": "i1"}}),
        nbformat.v4.new_markdown_cell("La courbe augmente.", metadata={"tpstudio": {"role": "interpretation_response", "expectation_id": "i2"}}),
    ]
    notebook = nbformat.v4.new_notebook(cells=cells)
    for cell in notebook.cells:
        cell.pop("id", None)
    evaluations = evaluate_interpretation_cells(notebook)
    traces = build_interpretation_review_traces(
        notebook, evaluations, {"i1": InterpretationContext("i1"), "i2": InterpretationContext("i2")}, (),
        copy_id="copy-001", copy_sha256=hashlib.sha256(b"copy").hexdigest(),
    )
    assert traces[0].cell_id.startswith("fallback:")
    assert traces[0].cell_id != traces[1].cell_id
    assert traces[0].cell_index_snapshot == 0


def test_existing_nbformat_cell_id_is_preserved():
    cell = nbformat.v4.new_markdown_cell(
        "Réponse.", metadata={"tpstudio": {"role": "interpretation_response", "expectation_id": "i1"}}
    )
    expected_id = cell.id
    notebook = nbformat.v4.new_notebook(cells=[cell])
    traces = build_interpretation_review_traces(
        notebook, evaluate_interpretation_cells(notebook), {"i1": InterpretationContext("i1")}, (),
        copy_id="copy-001", copy_sha256=hashlib.sha256(b"copy").hexdigest(),
    )
    assert traces[0].cell_id == expected_id


def test_same_expectation_id_uses_cell_identity_for_context_and_feedback():
    first = nbformat.v4.new_markdown_cell(
        "Le graphe est correct.", metadata={"tpstudio": {"role": "interpretation_response", "expectation_id": "same"}}
    )
    second = nbformat.v4.new_markdown_cell(
        "L'écart est faible, donc c'est bon.", metadata={"tpstudio": {"role": "interpretation_response", "expectation_id": "same"}}
    )
    notebook = nbformat.v4.new_notebook(cells=[first, second])
    evaluations = evaluate_interpretation_cells(notebook)
    contexts = {
        ("same", 0): InterpretationContext("same", local_prompt="Consigne A", local_scientific_context=("Résultat A",)),
        ("same", 1): InterpretationContext("same", local_prompt="Consigne B", local_scientific_context=("Résultat B",)),
    }
    feedback = (
        InterpretationFeedbackItem("same", "Feedback A", 0),
        InterpretationFeedbackItem("same", "Feedback B", 1),
    )
    traces = build_interpretation_review_traces(
        notebook, evaluations, contexts, feedback,
        copy_id="copy-001", copy_sha256=hashlib.sha256(b"copy").hexdigest(),
    )
    assert [trace.cell_id for trace in traces] == [first.id, second.id]
    assert [trace.student_answer for trace in traces] == [
        "Le graphe est correct.", "L'écart est faible, donc c'est bon."
    ]
    assert [trace.local_context.local_prompt for trace in traces] == ["Consigne A", "Consigne B"]
    assert [trace.tpstudio_feedback for trace in traces] == ["Feedback A", "Feedback B"]
    assert traces[0].tpstudio_proposal is InterpretationClassification.CLEARLY_INSUFFICIENT
    assert traces[1].tpstudio_proposal is InterpretationClassification.AMBIGUOUS


def test_jsonl_store_handles_missing_file_revisions_utf8_and_sha_mismatch(tmp_path):
    path = review_store_path(tmp_path / "corrections")
    assert load_interpretation_reviews(path) == ()
    sha = hashlib.sha256("copie-éudiant".encode()).hexdigest()
    first = _trace(sha=sha, decision=InterpretationClassification.CLEARLY_INSUFFICIENT)
    second = _trace(sha=sha, decision=InterpretationClassification.CLEARLY_SUFFICIENT, cell_id="cell-1")
    append_interpretation_review(path, first)
    append_interpretation_review(path, second)
    loaded = load_interpretation_reviews(path)
    assert len(loaded) == 2
    assert latest_interpretation_review(loaded, copy_id="copy-001", copy_sha256=sha, expectation_id="interp-1", cell_id="cell-1") == second
    assert resolve_interpretation_review(path, copy_id="copy-001", copy_sha256=hashlib.sha256(b"changed").hexdigest(), expectation_id="interp-1", cell_id="cell-1") is None


def test_pending_trace_is_not_persisted(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="PENDING"):
        append_interpretation_review(tmp_path / "reviews.jsonl", _trace(sha=hashlib.sha256(b"copy").hexdigest()))


def test_truncated_jsonl_is_reported_explicitly(tmp_path):
    import pytest
    path = tmp_path / "reviews.jsonl"
    path.write_text('{"schema_version":1', encoding="utf-8")
    with pytest.raises(ValueError, match="ligne 1"):
        load_interpretation_reviews(path)
