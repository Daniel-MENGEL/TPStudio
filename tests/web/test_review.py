from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import nbformat

from tpstudio.batch import BatchCopyResult, BatchCopyStatus, BatchRunResult
from tpstudio.batch import BatchCopySource, build_batch_plan
from tpstudio.interpretation import (
    InterpretationClassification,
    InterpretationContext,
    InterpretationReviewTrace,
)
from tpstudio.protocol import ProtocolStatus
from tpstudio.review_store import append_interpretation_review, review_store_path
from tpstudio.web.presenters import review_prefill, select_interpretation_review_items
from tpstudio.web.execution import run_prepared_batch
from tpstudio.batch.runner import stable_review_copy_id


def _trace(sha: str, *, decision=None, feedback="Proposition TPStudio", status=ProtocolStatus.PRESENT, requires=True):
    return InterpretationReviewTrace(
        1, "copy-001", sha, "interp-1", "cell-1", 3, "Réponse étudiante.",
        InterpretationContext("interp-1", local_prompt="Interpréter le résultat.", local_scientific_context=("Résultat local.",)),
        InterpretationClassification.AMBIGUOUS, feedback,
        decision, "", datetime.now(timezone.utc).isoformat() if decision else None,
        status, requires,
    )


def _result(trace):
    item = BatchCopyResult(
        "copy-001", BatchCopyStatus.SUCCESS, Path("copy.ipynb"), Path("copy.html"),
        interpretation_review_traces=(trace,),
    )
    return BatchRunResult("snells-laws-mvp", (item,), Path("out"), 1, 1, 0, 0, 0, 0)


def test_review_selection_prefills_proposal_then_persisted_decision(tmp_path):
    sha = sha256(b"copy").hexdigest()
    trace = _trace(sha)
    result = _result(trace)
    pending = select_interpretation_review_items(result, tmp_path)
    assert len(pending) == 1
    assert pending[0].status_label == "À revoir"
    assert review_prefill(pending[0]) == (InterpretationClassification.AMBIGUOUS, "Proposition TPStudio")

    reviewed = _trace(sha, decision=InterpretationClassification.CLEARLY_SUFFICIENT, feedback="")
    append_interpretation_review(review_store_path(tmp_path), reviewed)
    assert select_interpretation_review_items(result, tmp_path) == ()
    all_items = select_interpretation_review_items(result, tmp_path, only_pending=False)
    assert all_items[0].status_label == "Remplacée"
    assert review_prefill(all_items[0]) == (InterpretationClassification.CLEARLY_SUFFICIENT, "")


def test_review_selection_marks_sha_mismatch_stale_without_prefill(tmp_path):
    old_sha = sha256(b"old-copy").hexdigest()
    new_sha = sha256(b"new-copy").hexdigest()
    append_interpretation_review(
        review_store_path(tmp_path),
        _trace(old_sha, decision=InterpretationClassification.CLEARLY_INSUFFICIENT),
    )
    items = select_interpretation_review_items(_result(_trace(new_sha)), tmp_path)
    assert len(items) == 1
    assert items[0].stale_review is True
    assert items[0].current_review is None
    assert review_prefill(items[0]) == (InterpretationClassification.AMBIGUOUS, "Proposition TPStudio")


def test_not_evaluable_is_reviewable_without_becoming_a_teacher_classification(tmp_path):
    trace = _trace(
        sha256(b"not-evaluable").hexdigest(), status=ProtocolStatus.NOT_EVALUABLE,
    )
    trace = InterpretationReviewTrace(
        trace.schema_version, trace.copy_id, trace.copy_sha256, trace.expectation_id,
        trace.cell_id, trace.cell_index_snapshot, trace.student_answer, trace.local_context,
        None, trace.tpstudio_feedback, None, None, None, trace.tpstudio_status,
        trace.requires_human_review,
    )
    items = select_interpretation_review_items(_result(trace), tmp_path)
    assert len(items) == 1
    assert "NOT_EVALUABLE" in items[0].proposed_label
    assert review_prefill(items[0])[0] is InterpretationClassification.AMBIGUOUS


def test_real_batch_carries_review_traces_with_batch_copy_id(tmp_path):
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("Le graphe est correct.", metadata={
            "tpstudio": {"role": "interpretation_response", "expectation_id": "interp-1"}
        }),
    ])
    source = tmp_path / "copy.ipynb"
    nbformat.write(notebook, source)
    plan = build_batch_plan((BatchCopySource("copy-001", source),), tmp_path / "out")
    result = run_prepared_batch(plan)
    assert result.success
    traces = result.results[0].interpretation_review_traces
    assert len(traces) == 1
    assert traces[0].copy_id.startswith("review-copy-")
    assert traces[0].tpstudio_proposal is InterpretationClassification.CLEARLY_INSUFFICIENT


def test_review_copy_ids_are_order_independent_and_disambiguate_same_names(tmp_path):
    first_path = tmp_path / "first.ipynb"
    second_path = tmp_path / "second.ipynb"
    first_path.write_bytes(b"one")
    second_path.write_bytes(b"two")
    first = BatchCopySource("copy-001", first_path, "tp.ipynb")
    second = BatchCopySource("copy-002", second_path, "tp.ipynb")
    original = {stable_review_copy_id(item) for item in (first, second)}
    reversed_order = {stable_review_copy_id(item) for item in (second, first)}
    assert original == reversed_order
    assert stable_review_copy_id(first) != stable_review_copy_id(second)


def test_batch_disambiguates_identical_name_and_content_for_review_traces(tmp_path):
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("Le graphe est correct.", metadata={
            "tpstudio": {"role": "interpretation_response", "expectation_id": "interp-1"}
        }),
    ])
    first = tmp_path / "a" / "tp.ipynb"
    second = tmp_path / "b" / "tp.ipynb"
    first.parent.mkdir(); second.parent.mkdir()
    raw = nbformat.writes(notebook).encode("utf-8")
    first.write_bytes(raw); second.write_bytes(raw)
    plan = build_batch_plan((
        BatchCopySource("copy-001", first, "tp.ipynb"),
        BatchCopySource("copy-002", second, "tp.ipynb"),
    ), tmp_path / "out")
    result = run_prepared_batch(plan)
    assert result.success
    ids = [item.interpretation_review_traces[0].copy_id for item in result.results]
    assert ids[0] != ids[1]
    assert ids[1].endswith("-2")
