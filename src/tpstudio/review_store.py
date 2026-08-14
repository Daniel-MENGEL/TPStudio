"""Local append-only persistence for human interpretation reviews."""

from __future__ import annotations

import json
from pathlib import Path

from .interpretation import InterpretationReviewTrace


def review_store_path(output_dir: Path) -> Path:
    if not isinstance(output_dir, Path):
        raise TypeError("output_dir doit être un Path.")
    return output_dir / ".tpstudio" / "interpretation_reviews.jsonl"


def append_interpretation_review(path: Path, trace: InterpretationReviewTrace) -> None:
    if not isinstance(path, Path) or type(trace) is not InterpretationReviewTrace:
        raise TypeError("Le chemin ou la trace de revue est invalide.")
    if trace.teacher_decision is None:
        raise ValueError("Une trace PENDING ne peut pas être persistée comme décision.")
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(trace.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")
        stream.flush()


def load_interpretation_reviews(path: Path) -> tuple[InterpretationReviewTrace, ...]:
    if not isinstance(path, Path):
        raise TypeError("Le chemin du store doit être un Path.")
    if not path.exists():
        return ()
    traces = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            traces.append(InterpretationReviewTrace.from_dict(json.loads(line)))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Trace de revue invalide à la ligne {line_number}.") from exc
    return tuple(traces)


def latest_interpretation_review(
    traces: tuple[InterpretationReviewTrace, ...],
    *,
    copy_id: str,
    copy_sha256: str,
    expectation_id: str,
    cell_id: str,
) -> InterpretationReviewTrace | None:
    for trace in reversed(tuple(traces)):
        if (
            trace.copy_id == copy_id
            and trace.copy_sha256 == copy_sha256
            and trace.expectation_id == expectation_id
            and trace.cell_id == cell_id
            and trace.teacher_decision is not None
        ):
            return trace
    return None


def resolve_interpretation_review(
    path: Path,
    *,
    copy_id: str,
    copy_sha256: str,
    expectation_id: str,
    cell_id: str,
) -> InterpretationReviewTrace | None:
    return latest_interpretation_review(
        load_interpretation_reviews(path), copy_id=copy_id, copy_sha256=copy_sha256,
        expectation_id=expectation_id, cell_id=cell_id,
    )
