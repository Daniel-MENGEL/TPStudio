from tpstudio.web.state import (
    PLAN_KEY, SELECTION_KEY, SIGNATURE_KEY, UPLOADER_GENERATION_KEY, clear_prepared_batch, initialize_session_state,
    invalidate_if_signature_changed, set_prepared_batch,
    reset_web_session,
)


def test_state_initialization_and_invalidation():
    state = {}
    initialize_session_state(state)
    assert state[PLAN_KEY] is None
    set_prepared_batch(state, "plan", ("signature",))
    assert state[PLAN_KEY] == "plan"
    assert not invalidate_if_signature_changed(state, ("signature",))
    assert invalidate_if_signature_changed(state, ("changed",))
    assert state[PLAN_KEY] is None and state[SIGNATURE_KEY] is None
    clear_prepared_batch(state)


def test_reset_web_session_clears_selection_and_advances_uploader():
    state = {}
    initialize_session_state(state)
    state[SELECTION_KEY] = ("copy-001",)
    set_prepared_batch(state, "plan", ("sig",))
    assert state[UPLOADER_GENERATION_KEY] == 0
    reset_web_session(state)
    assert state[UPLOADER_GENERATION_KEY] == 1
    assert state[SELECTION_KEY] == () and state[PLAN_KEY] is None and state[SIGNATURE_KEY] is None
