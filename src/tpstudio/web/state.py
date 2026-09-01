"""Explicit session-state keys and pure invalidation helpers."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path


WORKSPACE_KEY = "tpstudio_web_workspace"
SELECTION_KEY = "tpstudio_web_selection"
PLAN_KEY = "tpstudio_web_plan"
SIGNATURE_KEY = "tpstudio_web_plan_signature"
UPLOADER_GENERATION_KEY = "tpstudio_web_uploader_generation"
RUN_RESULT_KEY = "tpstudio_web_run_result"
RUN_SIGNATURE_KEY = "tpstudio_web_run_signature"
DISPATCH_RESULT_KEY = "tpstudio_web_dispatch_result"
DISPATCH_SIGNATURE_KEY = "tpstudio_web_dispatch_signature"
PROJECT_OVERRIDES_KEY = "tpstudio_web_project_overrides"
EXPORT_RESULTS_KEY = "tpstudio_web_export_results"
ANNOTATION_REVIEWS_KEY = "tpstudio_web_annotation_reviews"
HTML_PREVIEWS_KEY = "tpstudio_web_html_previews"
RUN_IN_PROGRESS_KEY = "tpstudio_web_run_in_progress"
REVIEW_INDEX_KEY = "tpstudio_web_review_index"
REVIEW_FILTER_KEY = "tpstudio_web_review_only_pending"
REVIEW_MESSAGE_KEY = "tpstudio_web_review_message"
SEMANTIC_ANALYSIS_ENABLED_KEY = "tpstudio_semantic_analysis_enabled"


def default_output_dir() -> Path:
    return Path.home() / "Documents" / "Sup" / "TP" / "Notebooks-corrigés"


def initialize_session_state(state: MutableMapping) -> None:
    state.setdefault(WORKSPACE_KEY, None)
    state.setdefault(SELECTION_KEY, ())
    state.setdefault(PLAN_KEY, None)
    state.setdefault(SIGNATURE_KEY, None)
    state.setdefault(UPLOADER_GENERATION_KEY, 0)
    state.setdefault(RUN_RESULT_KEY, None)
    state.setdefault(RUN_SIGNATURE_KEY, None)
    state.setdefault(DISPATCH_RESULT_KEY, None)
    state.setdefault(DISPATCH_SIGNATURE_KEY, None)
    state.setdefault(PROJECT_OVERRIDES_KEY, {})
    state.setdefault(EXPORT_RESULTS_KEY, {})
    state.setdefault(ANNOTATION_REVIEWS_KEY, {})
    state.setdefault(HTML_PREVIEWS_KEY, {})
    state.setdefault(RUN_IN_PROGRESS_KEY, False)
    state.setdefault(REVIEW_INDEX_KEY, 0)
    state.setdefault(REVIEW_FILTER_KEY, True)
    state.setdefault(REVIEW_MESSAGE_KEY, None)
    state.setdefault(SEMANTIC_ANALYSIS_ENABLED_KEY, False)


def clear_prepared_batch(state: MutableMapping) -> None:
    state[PLAN_KEY] = None
    state[SIGNATURE_KEY] = None


def clear_run_result(state: MutableMapping) -> None:
    state[RUN_RESULT_KEY] = None
    state[RUN_SIGNATURE_KEY] = None


def clear_dispatch_result(state: MutableMapping) -> None:
    state[DISPATCH_RESULT_KEY] = None
    state[DISPATCH_SIGNATURE_KEY] = None
    state[PROJECT_OVERRIDES_KEY] = {}
    state[EXPORT_RESULTS_KEY] = {}
    state[ANNOTATION_REVIEWS_KEY] = {}
    state[HTML_PREVIEWS_KEY] = {}


def set_run_result(state: MutableMapping, result, signature: tuple) -> None:
    state[RUN_RESULT_KEY] = result
    state[RUN_SIGNATURE_KEY] = signature


def get_current_run_result(state: MutableMapping, signature: tuple):
    if state.get(RUN_SIGNATURE_KEY) == signature:
        return state.get(RUN_RESULT_KEY)
    return None


def set_dispatch_result(state: MutableMapping, result, signature: tuple) -> None:
    state[DISPATCH_RESULT_KEY] = result
    state[DISPATCH_SIGNATURE_KEY] = signature
    state[PROJECT_OVERRIDES_KEY] = {}
    state[EXPORT_RESULTS_KEY] = {}
    state[ANNOTATION_REVIEWS_KEY] = {}
    state[HTML_PREVIEWS_KEY] = {}


def get_project_overrides(state: MutableMapping) -> dict:
    return dict(state.get(PROJECT_OVERRIDES_KEY, {}))


def set_project_override(state: MutableMapping, override) -> None:
    overrides = get_project_overrides(state)
    overrides[override.source_id] = override
    state[PROJECT_OVERRIDES_KEY] = overrides
    state[EXPORT_RESULTS_KEY] = {}
    reviews = get_annotation_reviews(state)
    reviews.pop(override.source_id, None)
    state[ANNOTATION_REVIEWS_KEY] = reviews
    previews = dict(state.get(HTML_PREVIEWS_KEY, {}))
    previews.pop(override.source_id, None)
    state[HTML_PREVIEWS_KEY] = previews


def remove_project_override(state: MutableMapping, source_id: str) -> None:
    overrides = get_project_overrides(state)
    overrides.pop(source_id, None)
    state[PROJECT_OVERRIDES_KEY] = overrides
    state[EXPORT_RESULTS_KEY] = {}
    reviews = get_annotation_reviews(state)
    reviews.pop(source_id, None)
    state[ANNOTATION_REVIEWS_KEY] = reviews
    previews = dict(state.get(HTML_PREVIEWS_KEY, {}))
    previews.pop(source_id, None)
    state[HTML_PREVIEWS_KEY] = previews


def get_export_results(state: MutableMapping) -> dict:
    return dict(state.get(EXPORT_RESULTS_KEY, {}))


def set_export_results(state: MutableMapping, results: dict) -> None:
    state[EXPORT_RESULTS_KEY] = dict(results)


def get_annotation_reviews(state: MutableMapping) -> dict:
    return {
        source_id: tuple(reviews)
        for source_id, reviews in state.get(ANNOTATION_REVIEWS_KEY, {}).items()
    }


def set_annotation_review(state: MutableMapping, source_id: str, review) -> None:
    reviews = get_annotation_reviews(state)
    current = {
        item.annotation_id: item for item in reviews.get(source_id, ())
    }
    current[review.annotation_id] = review
    reviews[source_id] = tuple(current.values())
    state[ANNOTATION_REVIEWS_KEY] = reviews
    state[EXPORT_RESULTS_KEY] = {}


def set_annotation_reviews_for_source(
    state: MutableMapping, source_id: str, source_reviews,
) -> None:
    reviews = get_annotation_reviews(state)
    values = tuple(source_reviews)
    if values:
        reviews[source_id] = values
    else:
        reviews.pop(source_id, None)
    state[ANNOTATION_REVIEWS_KEY] = reviews
    state[EXPORT_RESULTS_KEY] = {}


def remove_annotation_review(
    state: MutableMapping, source_id: str, annotation_id: str,
) -> None:
    reviews = get_annotation_reviews(state)
    remaining = tuple(
        item for item in reviews.get(source_id, ())
        if item.annotation_id != annotation_id
    )
    if remaining:
        reviews[source_id] = remaining
    else:
        reviews.pop(source_id, None)
    state[ANNOTATION_REVIEWS_KEY] = reviews
    state[EXPORT_RESULTS_KEY] = {}


def get_html_preview(state: MutableMapping, source_id: str, signature: tuple):
    cached = state.get(HTML_PREVIEWS_KEY, {}).get(source_id)
    if cached is not None and cached[0] == signature:
        return cached[1]
    return None


def set_html_preview(
    state: MutableMapping, source_id: str, signature: tuple, html: str,
) -> None:
    previews = dict(state.get(HTML_PREVIEWS_KEY, {}))
    previews[source_id] = (signature, html)
    state[HTML_PREVIEWS_KEY] = previews


def get_current_dispatch_result(state: MutableMapping, signature: tuple):
    if state.get(DISPATCH_SIGNATURE_KEY) == signature:
        return state.get(DISPATCH_RESULT_KEY)
    return None


def invalidate_dispatch_if_signature_changed(state: MutableMapping, signature: tuple) -> bool:
    """Drop stale analysis results without invalidating the prepared plan."""
    previous = state.get(DISPATCH_SIGNATURE_KEY)
    if previous is not None and previous != signature:
        clear_dispatch_result(state)
        return True
    return False


def run_result_is_current(state: MutableMapping, signature: tuple) -> bool:
    return get_current_run_result(state, signature) is not None


def reset_web_session(state: MutableMapping) -> None:
    state[SELECTION_KEY] = ()
    clear_prepared_batch(state)
    clear_run_result(state)
    clear_dispatch_result(state)
    state[RUN_IN_PROGRESS_KEY] = False
    state[REVIEW_INDEX_KEY] = 0
    state[REVIEW_MESSAGE_KEY] = None
    state[UPLOADER_GENERATION_KEY] = state.get(UPLOADER_GENERATION_KEY, 0) + 1


def set_prepared_batch(state: MutableMapping, plan, signature: tuple) -> None:
    state[PLAN_KEY] = plan
    state[SIGNATURE_KEY] = signature


def invalidate_if_signature_changed(state: MutableMapping, signature: tuple) -> bool:
    if state.get(SIGNATURE_KEY) != signature:
        clear_prepared_batch(state)
        clear_run_result(state)
        clear_dispatch_result(state)
        state[REVIEW_INDEX_KEY] = 0
        return True
    return False
