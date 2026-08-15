"""Explicit, local and pseudonymized export of human interpretation reviews."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from collections import Counter
from pathlib import Path
from typing import Iterable

from .interpretation import InterpretationReviewTrace


SCHEMA_VERSION = "a73c2d-v1"
_KEY_FILENAME = "corpus_pseudonym_key"
_KEY_BYTES = 32


def corpus_pseudonym_key_path() -> Path:
    return Path.home() / ".tpstudio" / _KEY_FILENAME


def load_or_create_corpus_pseudonym_key(path: Path | None = None) -> bytes:
    """Load a local HMAC key, creating it once with private permissions."""
    path = corpus_pseudonym_key_path() if path is None else path
    if not isinstance(path, Path):
        raise TypeError("Le chemin de clé doit être un Path.")
    if path.exists():
        key = path.read_bytes()
        if len(key) != _KEY_BYTES:
            raise ValueError("La clé de pseudonymisation locale est invalide.")
        return key
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = secrets.token_bytes(_KEY_BYTES)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        key = path.read_bytes()
        if len(key) != _KEY_BYTES:
            raise ValueError("La clé de pseudonymisation locale est invalide.")
        return key
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(key)
    return key


def pseudonymize_identifier(key: bytes, namespace: str, value: str, prefix: str) -> str:
    if not isinstance(key, bytes) or len(key) != _KEY_BYTES:
        raise ValueError("La clé de pseudonymisation doit contenir 32 octets.")
    if not isinstance(namespace, str) or not isinstance(value, str):
        raise TypeError("Le namespace et la valeur doivent être des chaînes.")
    digest = hmac.new(key, f"tpstudio-corpus-{namespace}-v1:{value}".encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _current_sha_by_key(current_traces: Iterable[InterpretationReviewTrace]) -> dict[tuple[str, str, str], str]:
    return {
        (trace.copy_id, trace.expectation_id, trace.cell_id): trace.copy_sha256
        for trace in current_traces
    }


def _local_context(trace: InterpretationReviewTrace) -> dict[str, object]:
    context = trace.local_context
    return {
        "local_prompt": context.local_prompt,
        "local_scientific_context": list(context.local_scientific_context),
        "linked_protocol": context.linked_protocol,
    }


def pseudonymize_review_trace(
    trace: InterpretationReviewTrace,
    *,
    pseudonym_key: bytes,
    history_index: int,
    current_traces: Iterable[InterpretationReviewTrace] = (),
) -> dict[str, object] | None:
    """Project one human-reviewed trace without internal or personal IDs."""
    if type(trace) is not InterpretationReviewTrace:
        raise TypeError("La trace de corpus est invalide.")
    if trace.teacher_decision is None:
        return None
    if type(history_index) is not int or history_index < 1:
        raise ValueError("history_index doit être un entier positif.")
    current = _current_sha_by_key(tuple(current_traces))
    key = (trace.copy_id, trace.expectation_id, trace.cell_id)
    current_sha = current.get(key)
    stale = None if current_sha is None else current_sha != trace.copy_sha256
    proposal = trace.tpstudio_proposal.name if trace.tpstudio_proposal is not None else None
    decision = trace.teacher_decision.name
    return {
        "schema_version": SCHEMA_VERSION,
        "anonymous_copy_id": pseudonymize_identifier(pseudonym_key, "copy", trace.copy_sha256, "copy"),
        "anonymous_cell_id": pseudonymize_identifier(pseudonym_key, "cell", trace.cell_id, "cell"),
        "history_index": history_index,
        "expectation_id": trace.expectation_id,
        "tpstudio_status": trace.tpstudio_status.name,
        "tpstudio_proposal": proposal,
        "tpstudio_feedback": trace.tpstudio_feedback,
        "teacher_decision": decision,
        "teacher_feedback": trace.teacher_feedback,
        "review_status": trace.review_status,
        "stale": stale,
        "reviewed_at": trace.reviewed_at,
        "student_answer": trace.student_answer,
        "local_context": _local_context(trace),
        "agreement": (decision == proposal) if proposal is not None else None,
    }


def build_interpretation_review_corpus(
    reviews: Iterable[InterpretationReviewTrace],
    *,
    pseudonym_key: bytes,
    current_traces: Iterable[InterpretationReviewTrace] = (),
) -> tuple[dict[str, object], ...]:
    current = tuple(current_traces)
    rows = []
    for history_index, trace in enumerate(reviews, 1):
        row = pseudonymize_review_trace(trace, pseudonym_key=pseudonym_key, history_index=history_index, current_traces=current)
        if row is not None:
            rows.append(row)
    return tuple(rows)


def export_interpretation_review_corpus(
    reviews: Iterable[InterpretationReviewTrace],
    destination: Path,
    *,
    pseudonym_key: bytes,
    current_traces: Iterable[InterpretationReviewTrace] = (),
) -> Path:
    if not isinstance(destination, Path):
        raise TypeError("La destination du corpus doit être un Path.")
    rows = build_interpretation_review_corpus(reviews, pseudonym_key=pseudonym_key, current_traces=current_traces)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(interpretation_review_corpus_jsonl(rows))
    return destination


def interpretation_review_corpus_jsonl(rows: Iterable[dict[str, object]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def summarize_interpretation_review_corpus(rows: Iterable[dict[str, object]]) -> dict[str, object]:
    rows = tuple(rows)
    agreements = [row["agreement"] for row in rows if row.get("agreement") is not None]
    return {
        "total": len(rows),
        "confirmed": sum(row.get("review_status") == "CONFIRMED" for row in rows),
        "replaced": sum(row.get("review_status") == "REPLACED" for row in rows),
        "agreement": sum(agreements),
        "disagreement": sum(not value for value in agreements),
        "teacher_decision": dict(Counter(str(row["teacher_decision"]) for row in rows)),
        "tpstudio_proposal": dict(Counter(str(row["tpstudio_proposal"]) for row in rows if row.get("tpstudio_proposal") is not None)),
    }
