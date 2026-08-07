"""Explicit session-state keys and pure invalidation helpers."""

from __future__ import annotations

from collections.abc import MutableMapping


WORKSPACE_KEY = "tpstudio_web_workspace"
SELECTION_KEY = "tpstudio_web_selection"
PLAN_KEY = "tpstudio_web_plan"
SIGNATURE_KEY = "tpstudio_web_plan_signature"
UPLOADER_GENERATION_KEY = "tpstudio_web_uploader_generation"


def initialize_session_state(state: MutableMapping) -> None:
    state.setdefault(WORKSPACE_KEY, None)
    state.setdefault(SELECTION_KEY, ())
    state.setdefault(PLAN_KEY, None)
    state.setdefault(SIGNATURE_KEY, None)
    state.setdefault(UPLOADER_GENERATION_KEY, 0)


def clear_prepared_batch(state: MutableMapping) -> None:
    state[PLAN_KEY] = None
    state[SIGNATURE_KEY] = None


def reset_web_session(state: MutableMapping) -> None:
    state[SELECTION_KEY] = ()
    clear_prepared_batch(state)
    state[UPLOADER_GENERATION_KEY] = state.get(UPLOADER_GENERATION_KEY, 0) + 1


def set_prepared_batch(state: MutableMapping, plan, signature: tuple) -> None:
    state[PLAN_KEY] = plan
    state[SIGNATURE_KEY] = signature


def invalidate_if_signature_changed(state: MutableMapping, signature: tuple) -> bool:
    if state.get(SIGNATURE_KEY) != signature:
        clear_prepared_batch(state)
        return True
    return False
