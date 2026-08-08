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
RUN_IN_PROGRESS_KEY = "tpstudio_web_run_in_progress"


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
    state.setdefault(RUN_IN_PROGRESS_KEY, False)


def clear_prepared_batch(state: MutableMapping) -> None:
    state[PLAN_KEY] = None
    state[SIGNATURE_KEY] = None


def clear_run_result(state: MutableMapping) -> None:
    state[RUN_RESULT_KEY] = None
    state[RUN_SIGNATURE_KEY] = None


def set_run_result(state: MutableMapping, result, signature: tuple) -> None:
    state[RUN_RESULT_KEY] = result
    state[RUN_SIGNATURE_KEY] = signature


def get_current_run_result(state: MutableMapping, signature: tuple):
    if state.get(RUN_SIGNATURE_KEY) == signature:
        return state.get(RUN_RESULT_KEY)
    return None


def run_result_is_current(state: MutableMapping, signature: tuple) -> bool:
    return get_current_run_result(state, signature) is not None


def reset_web_session(state: MutableMapping) -> None:
    state[SELECTION_KEY] = ()
    clear_prepared_batch(state)
    clear_run_result(state)
    state[RUN_IN_PROGRESS_KEY] = False
    state[UPLOADER_GENERATION_KEY] = state.get(UPLOADER_GENERATION_KEY, 0) + 1


def set_prepared_batch(state: MutableMapping, plan, signature: tuple) -> None:
    state[PLAN_KEY] = plan
    state[SIGNATURE_KEY] = signature


def invalidate_if_signature_changed(state: MutableMapping, signature: tuple) -> bool:
    if state.get(SIGNATURE_KEY) != signature:
        clear_prepared_batch(state)
        clear_run_result(state)
        return True
    return False
