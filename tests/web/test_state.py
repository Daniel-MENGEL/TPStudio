from tpstudio.web.state import (
    PLAN_KEY, SELECTION_KEY, SIGNATURE_KEY, UPLOADER_GENERATION_KEY, clear_prepared_batch, initialize_session_state,
    invalidate_if_signature_changed, set_prepared_batch,
    reset_web_session,
    RUN_IN_PROGRESS_KEY, RUN_RESULT_KEY, RUN_SIGNATURE_KEY,
    clear_run_result, get_current_run_result, set_run_result, default_output_dir,
    REVIEW_INDEX_KEY,
    DISPATCH_RESULT_KEY, DISPATCH_SIGNATURE_KEY, invalidate_dispatch_if_signature_changed,
    set_dispatch_result,
    get_annotation_reviews, set_annotation_review,
    set_annotation_reviews_for_source,
)
from tpstudio.orchestration import BatchDispatchResult
from tpstudio.annotation import AnnotationReview, AnnotationReviewAction


def test_state_initialization_and_invalidation():
    state = {}
    initialize_session_state(state)
    assert state[PLAN_KEY] is None
    set_prepared_batch(state, "plan", ("signature",))
    set_run_result(state, "result", ("signature",))
    assert state[PLAN_KEY] == "plan"
    assert not invalidate_if_signature_changed(state, ("signature",))
    assert invalidate_if_signature_changed(state, ("changed",))
    assert state[PLAN_KEY] is None and state[SIGNATURE_KEY] is None and state[RUN_RESULT_KEY] is None
    assert state[REVIEW_INDEX_KEY] == 0
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


def test_run_result_lifecycle_and_reset():
    state = {}
    initialize_session_state(state)
    assert state[RUN_RESULT_KEY] is None and not state[RUN_IN_PROGRESS_KEY]
    set_run_result(state, "result", ("sig",))
    assert get_current_run_result(state, ("sig",)) == "result"
    assert get_current_run_result(state, ("other",)) is None
    clear_run_result(state)
    assert state[RUN_RESULT_KEY] is None and state[RUN_SIGNATURE_KEY] is None
    state[RUN_IN_PROGRESS_KEY] = True
    reset_web_session(state)
    assert state[RUN_RESULT_KEY] is None and not state[RUN_IN_PROGRESS_KEY]


def test_default_output_dir_is_local_home_path():
    from pathlib import Path
    assert default_output_dir() == Path.home() / "Documents" / "Sup" / "TP" / "Notebooks-corrigés"


def test_dispatch_signature_change_clears_analysis_without_clearing_plan():
    state = {}
    initialize_session_state(state)
    set_prepared_batch(state, "plan", ("plan-signature",))
    set_dispatch_result(state, BatchDispatchResult(()), (("plan-signature",), False, "gpt-5-mini"))
    assert invalidate_dispatch_if_signature_changed(
        state, (("plan-signature",), True, "gpt-5-mini")
    )
    assert state[DISPATCH_RESULT_KEY] is None
    assert state[DISPATCH_SIGNATURE_KEY] is None
    assert state[PLAN_KEY] == "plan"


def test_annotation_reviews_are_scoped_per_copy_and_cleared_with_analysis():
    state = {}
    initialize_session_state(state)
    first = AnnotationReview("a", AnnotationReviewAction.KEEP)
    second = AnnotationReview("b", AnnotationReviewAction.REMOVE)
    set_annotation_review(state, "copy-1", first)
    set_annotation_reviews_for_source(state, "copy-2", (second,))
    assert get_annotation_reviews(state) == {
        "copy-1": (first,), "copy-2": (second,),
    }
    set_dispatch_result(state, BatchDispatchResult(()), ("signature",))
    assert get_annotation_reviews(state) == {}
