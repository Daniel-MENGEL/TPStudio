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
RUN_IN_PROGRESS_KEY = "tpstudio_web_run_in_progress"
REVIEW_INDEX_KEY = "tpstudio_web_review_index"
REVIEW_FILTER_KEY = "tpstudio_web_review_only_pending"
REVIEW_MESSAGE_KEY = "tpstudio_web_review_message"


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
    state.setdefault(RUN_IN_PROGRESS_KEY, False)
    state.setdefault(REVIEW_INDEX_KEY, 0)
    state.setdefault(REVIEW_FILTER_KEY, True)
    state.setdefault(REVIEW_MESSAGE_KEY, None)


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


def get_project_overrides(state: MutableMapping) -> dict:
    return dict(state.get(PROJECT_OVERRIDES_KEY, {}))


def set_project_override(state: MutableMapping, override) -> None:
    overrides = get_project_overrides(state)
    overrides[override.source_id] = override
    state[PROJECT_OVERRIDES_KEY] = overrides
    state[EXPORT_RESULTS_KEY] = {}


def remove_project_override(state: MutableMapping, source_id: str) -> None:
    overrides = get_project_overrides(state)
    overrides.pop(source_id, None)
    state[PROJECT_OVERRIDES_KEY] = overrides
    state[EXPORT_RESULTS_KEY] = {}


def get_export_results(state: MutableMapping) -> dict:
    return dict(state.get(EXPORT_RESULTS_KEY, {}))


def set_export_results(state: MutableMapping, results: dict) -> None:
    state[EXPORT_RESULTS_KEY] = dict(results)


def get_current_dispatch_result(state: MutableMapping, signature: tuple):
    if state.get(DISPATCH_SIGNATURE_KEY) == signature:
        return state.get(DISPATCH_RESULT_KEY)
    return None


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
