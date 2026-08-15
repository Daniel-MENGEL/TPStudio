from __future__ import annotations

import hashlib
import json
from dataclasses import replace

from tpstudio.interpretation import (
    InterpretationClassification,
    InterpretationContext,
    InterpretationReviewTrace,
)
from tpstudio.batch import BatchCopyResult, BatchCopyStatus, BatchRunResult
from tpstudio.protocol import ProtocolStatus
from tpstudio.review_corpus import (
    build_interpretation_review_corpus,
    export_interpretation_review_corpus,
    load_or_create_corpus_pseudonym_key,
    pseudonymize_identifier,
    summarize_interpretation_review_corpus,
)

KEY = b"k" * 32


def _trace(*, copy_id="review-jean-dupont-copy-001", sha=None, decision=InterpretationClassification.CLEARLY_SUFFICIENT, proposal=InterpretationClassification.AMBIGUOUS):
    sha = sha or hashlib.sha256(b"source").hexdigest()
    return InterpretationReviewTrace(
        1, copy_id, sha, "interp-1", "cell-1", 2,
        "La valeur mesurée est compatible avec la théorie.",
        InterpretationContext(
            "interp-1", local_prompt="Comparer le résultat à la valeur attendue.",
            local_scientific_context=("Résultat local : 1,52.",), linked_protocol="Mesurer puis comparer.",
        ), proposal, "Feedback automatique.", decision, "Retour enseignant.",
        "2026-08-15T12:00:00+00:00",
    )


def test_corpus_projection_is_pseudonymized_and_deterministic():
    trace = _trace()
    row = build_interpretation_review_corpus((trace,), pseudonym_key=KEY)[0]
    serialized = json.dumps(row, ensure_ascii=False)
    assert row["anonymous_copy_id"].startswith("copy_")
    assert row["anonymous_cell_id"].startswith("cell_")
    assert "review-jean-dupont-copy-001" not in serialized
    assert trace.copy_sha256 not in serialized
    assert "/Users/" not in serialized
    assert "Jean-Dupont" not in serialized
    assert row["student_answer"] == trace.student_answer
    assert row["local_context"]["local_prompt"] == trace.local_context.local_prompt
    assert build_interpretation_review_corpus((trace,), pseudonym_key=KEY)[0]["anonymous_copy_id"] == row["anonymous_copy_id"]
    other = build_interpretation_review_corpus((_trace(copy_id="review-other-copy", sha=hashlib.sha256(b"other source").hexdigest()),), pseudonym_key=KEY)[0]
    assert other["anonymous_copy_id"] != row["anonymous_copy_id"]


def test_pending_is_excluded_and_utf8_jsonl_is_written(tmp_path):
    pending = replace(_trace(), teacher_decision=None, reviewed_at=None)
    reviewed = _trace()
    destination = export_interpretation_review_corpus((pending, reviewed), tmp_path / "corpus.jsonl", pseudonym_key=KEY)
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["schema_version"] == "a73c2d-v1"
    assert payload["teacher_feedback"] == "Retour enseignant."
    assert "Résultat local" in lines[0]


def test_history_index_preserves_jsonl_order_for_equal_timestamps():
    first = _trace(copy_id="first")
    second = replace(_trace(copy_id="second"), cell_id="cell-2")
    rows = build_interpretation_review_corpus((first, second), pseudonym_key=KEY)
    assert [row["history_index"] for row in rows] == [1, 2]
    assert rows[0]["reviewed_at"] == rows[1]["reviewed_at"]


def test_stale_history_is_explicit_when_current_copy_hash_differs():
    old = _trace()
    assert build_interpretation_review_corpus((old,), pseudonym_key=KEY)[0]["stale"] is None
    current = replace(old, copy_sha256=hashlib.sha256(b"new source").hexdigest())
    row = build_interpretation_review_corpus((old,), pseudonym_key=KEY, current_traces=(current,))[0]
    assert row["stale"] is True


def test_statistics_cover_agreement_disagreement_and_not_evaluable():
    agreed = _trace(proposal=InterpretationClassification.CLEARLY_SUFFICIENT, decision=InterpretationClassification.CLEARLY_SUFFICIENT)
    disagreement = _trace(copy_id="other-copy", proposal=InterpretationClassification.AMBIGUOUS, decision=InterpretationClassification.CLEARLY_INSUFFICIENT)
    not_evaluable = replace(_trace(copy_id="third-copy", proposal=None, decision=InterpretationClassification.AMBIGUOUS), tpstudio_status=ProtocolStatus.NOT_EVALUABLE)
    stats = summarize_interpretation_review_corpus(build_interpretation_review_corpus((agreed, disagreement, not_evaluable), pseudonym_key=KEY))
    assert stats["total"] == 3
    assert stats["confirmed"] == 1
    assert stats["replaced"] == 2
    assert stats["agreement"] == 1
    assert stats["disagreement"] == 1
    assert stats["teacher_decision"]["AMBIGUOUS"] == 1


def test_ui_corpus_export_is_explicit_and_does_not_write_without_download(tmp_path, monkeypatch):
    from tpstudio.web.app import _render_review_corpus
    monkeypatch.setattr("tpstudio.web.app.load_or_create_corpus_pseudonym_key", lambda: KEY)

    class FakeStreamlit:
        def __init__(self):
            self.downloads = []
            self.captions = []

        def subheader(self, *_args, **_kwargs):
            pass

        def write(self, *_args, **_kwargs):
            pass

        def caption(self, *_args, **_kwargs):
            self.captions.append(str(_args[0]))

        def download_button(self, *args, **kwargs):
            self.downloads.append((args, kwargs))
            return False

    reviewed = _trace()
    append_path = tmp_path / ".tpstudio" / "interpretation_reviews.jsonl"
    from tpstudio.review_store import append_interpretation_review
    append_interpretation_review(append_path, reviewed)
    result = BatchRunResult(
        "snells-laws-mvp",
        (BatchCopyResult("review-jean-dupont-copy-001", BatchCopyStatus.SUCCESS, tmp_path / "copy.ipynb", tmp_path / "copy.html", interpretation_review_traces=(reviewed,)),),
        tmp_path, 1, 1, 0, 0, 0, 0,
    )
    fake = FakeStreamlit()
    _render_review_corpus(fake, result, tmp_path)
    assert len(fake.downloads) == 1
    assert not (tmp_path / "tpstudio-interpretation-reviews-a73c2d.jsonl").exists()
    payload = fake.downloads[0][1]["data"].decode("utf-8")
    assert "email" not in payload
    assert "review-jean-dupont-copy-001" not in payload
    assert any("pseudonymes" in caption for caption in fake.captions)
    assert any("textes libres" in caption for caption in fake.captions)


def test_hmac_key_is_injected_and_local_key_is_created_once(tmp_path):
    path = tmp_path / "key"
    first = load_or_create_corpus_pseudonym_key(path)
    second = load_or_create_corpus_pseudonym_key(path)
    assert len(first) == 32 and first == second
    assert pseudonymize_identifier(KEY, "copy", "sha-a", "copy") == pseudonymize_identifier(KEY, "copy", "sha-a", "copy")
    assert pseudonymize_identifier(KEY, "copy", "sha-a", "copy") != pseudonymize_identifier(KEY, "copy", "sha-b", "copy")
    assert pseudonymize_identifier(KEY, "copy", "sha-a", "copy") != pseudonymize_identifier(b"z" * 32, "copy", "sha-a", "copy")
    assert pseudonymize_identifier(KEY, "copy", "sha-a", "copy") != pseudonymize_identifier(KEY, "cell", "sha-a", "cell")
