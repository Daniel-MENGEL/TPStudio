"""Persistent, content-addressed cache for teacher annotation decisions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from hashlib import sha256
import nbformat

from tpstudio.annotation import (
    AnnotationReview,
    AnnotationReviewAction,
    AnnotationReviewLevel,
)


def default_annotation_review_cache_dir() -> Path:
    return Path.home() / ".cache" / "tpstudio" / "annotation-reviews-v1"


def default_shared_review_cache_dir() -> Path:
    return Path.home() / ".cache" / "tpstudio" / "shared-response-reviews-v1"


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


def _normalized_cell_source(notebook, annotation) -> str | None:
    index = getattr(annotation, "target_cell_index", None)
    if not isinstance(index, int) or index < 0 or index >= len(notebook.cells):
        return None
    source = notebook.cells[index].source
    if not isinstance(source, str):
        source = "".join(source)
    return " ".join(source.split())


def _shared_review_key(annotation, response: str) -> str:
    canonical = json.dumps(
        {
            "annotation": _annotation_key(annotation),
            "response": response,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
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


def load_shared_response_reviews(
    notebook_path: Path,
    annotations,
    *,
    cache_dir: Path | None = None,
) -> tuple[AnnotationReview, ...]:
    """Restore decisions for identical responses to the same question."""

    directory = default_shared_review_cache_dir() if cache_dir is None else cache_dir
    notebook = nbformat.read(notebook_path, as_version=4)
    restored = []
    for annotation in tuple(annotations):
        response = _normalized_cell_source(notebook, annotation)
        if response is None:
            continue
        path = directory / f"{_shared_review_key(annotation, response)}.json"
        if not path.exists():
            continue
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            restored.append(AnnotationReview(
                annotation.annotation_id,
                AnnotationReviewAction(item["action"]),
                item.get("message"),
                AnnotationReviewLevel(item["level"])
                if item.get("level") is not None else None,
            ))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return tuple(restored)


def save_shared_response_reviews(
    notebook_path: Path,
    reviews,
    annotations,
    *,
    cache_dir: Path | None = None,
) -> None:
    """Persist reviewed identical-response decisions without storing responses."""

    directory = default_shared_review_cache_dir() if cache_dir is None else cache_dir
    notebook = nbformat.read(notebook_path, as_version=4)
    annotation_by_id = {
        annotation.annotation_id: annotation for annotation in tuple(annotations)
    }
    directory.mkdir(parents=True, exist_ok=True)
    for review in tuple(reviews):
        annotation = annotation_by_id.get(review.annotation_id)
        if annotation is None:
            continue
        response = _normalized_cell_source(notebook, annotation)
        if response is None:
            continue
        path = directory / f"{_shared_review_key(annotation, response)}.json"
        payload = {
            "action": review.action.value,
            "message": review.message,
            "level": review.level.value if review.level is not None else None,
        }
        if path.exists():
            try:
                if json.loads(path.read_text(encoding="utf-8")) == payload:
                    continue
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        handle, name = tempfile.mkstemp(
            prefix=".tpstudio-shared-review-", suffix=".json", dir=directory
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
            Path(name).replace(path)
        finally:
            Path(name).unlink(missing_ok=True)
