"""Persistent, content-addressed cache for teacher annotation decisions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from hashlib import sha256

from tpstudio.annotation import (
    AnnotationReview,
    AnnotationReviewAction,
    AnnotationReviewLevel,
)


def default_annotation_review_cache_dir() -> Path:
    return Path.home() / ".cache" / "tpstudio" / "annotation-reviews-v1"


def _cache_path(copy_sha256: str, cache_dir: Path) -> Path:
    if not isinstance(copy_sha256, str) or len(copy_sha256) != 64:
        raise ValueError("L'empreinte de la copie est invalide.")
    return cache_dir / f"{copy_sha256}.json"


def _annotation_key(annotation) -> str:
    identity = {
        "type": type(annotation).__name__,
        "message": annotation.message,
        "source_ids": tuple(annotation.source_ids),
        "production_id": annotation.production_id,
        "comparison_id": annotation.comparison_id,
        "target_cell_index": getattr(annotation, "target_cell_index", None),
        "placement": getattr(getattr(annotation, "placement", None), "value", None),
        "reason": getattr(getattr(annotation, "reason", None), "value", None),
    }
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def load_annotation_reviews(
    copy_sha256: str,
    annotations,
    *,
    cache_dir: Path | None = None,
) -> tuple[AnnotationReview, ...]:
    directory = default_annotation_review_cache_dir() if cache_dir is None else cache_dir
    path = _cache_path(copy_sha256, directory)
    if not path.exists():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        current_by_key = {
            _annotation_key(annotation): annotation.annotation_id
            for annotation in tuple(annotations)
        }
        return tuple(
            AnnotationReview(
                annotation_id=current_by_key[item["annotation_key"]],
                action=AnnotationReviewAction(item["action"]),
                message=item.get("message"),
                level=(
                    AnnotationReviewLevel(item["level"])
                    if item.get("level") is not None
                    else None
                ),
            )
            for item in payload.get("reviews", ())
            if item.get("annotation_key") in current_by_key
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return ()


def save_annotation_reviews(
    copy_sha256: str,
    reviews,
    annotations,
    *,
    cache_dir: Path | None = None,
) -> None:
    directory = default_annotation_review_cache_dir() if cache_dir is None else cache_dir
    path = _cache_path(copy_sha256, directory)
    values = tuple(reviews)
    annotation_by_id = {
        annotation.annotation_id: annotation for annotation in tuple(annotations)
    }
    payload = {
        "copy_sha256": copy_sha256,
        "reviews": [
            {
                "annotation_key": _annotation_key(annotation_by_id[item.annotation_id]),
                "action": item.action.value,
                "message": item.message,
                "level": item.level.value if item.level is not None else None,
            }
            for item in values
            if item.annotation_id in annotation_by_id
        ],
    }
    directory.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        prefix=".tpstudio-reviews-", suffix=".json", dir=directory
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
        Path(name).replace(path)
    finally:
        Path(name).unlink(missing_ok=True)
