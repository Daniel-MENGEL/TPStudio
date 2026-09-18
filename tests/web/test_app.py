from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal

import tpstudio.web.app as app
from tpstudio.semantic_analysis import CachedSemanticAnalysisProvider
from tpstudio.web.app import (
    _analysis_signature,
    _build_semantic_provider,
    _copy_issue_count,
    _coerce_rubric_level,
    _consume_preview_click_event,
    _consume_review_keyboard_event,
    _focus_annotation_html,
    _input_signature,
    _navigate_annotation,
    _next_copy_id,
    _next_unverified_copy_id,
    _open_local_html_artifact,
    _ordered_review_annotations,
    _render_first_lab_grading,
    _rerun_copy_review,
    _restore_reviewed_copy,
    _suggested_grade_label,
    _validation_status_label,
    _weighted_first_lab_score,
    web_error_message,
)
from tpstudio.annotation import (
    AnnotationKind, AnnotationPlacement, AnnotationPlan, AnnotationReviewLevel,
    NotebookAnnotation,
    SkippedAnnotationReason, StudentSummaryAnnotation,
)
from tpstudio.feedback import FeedbackAudience
from tpstudio.grading import RubricDecision, RubricLevel
from tpstudio.projects import FIRST_LAB_FORMATIVE_GRADING_PROFILE
from tpstudio.reporting import TeacherReportSeverity
from tpstudio.web.model import SelectedCopy, WebBatchOptions


def test_signature_changes_for_same_size_content_hashes():
    first = SelectedCopy("copy-001", "tp.ipynb", Path("tp.ipynb"), "a" * 64)
    second = SelectedCopy("copy-001", "tp.ipynb", Path("tp.ipynb"), "b" * 64)
    options = WebBatchOptions()
    assert _input_signature((first,), Path("out"), options) != _input_signature((second,), Path("out"), options)


def test_web_error_names_the_invalid_notebook():
    from tpstudio.web.planning import WebInputError

    assert web_error_message(
        WebInputError("Notebook invalide : copie-problematique.ipynb.")
    ) == "Notebook invalide : copie-problematique.ipynb."


def test_review_preview_only_scrolls_for_an_explicit_navigation_request():
    component = (
        Path(app.__file__).with_name("review_preview_component") / "index.html"
    ).read_text(encoding="utf-8")

    assert "function consumeScrollRequest()" in component
    assert "scrollRequest.sequence === lastScrollSequence" in component
    assert 'behavior: "auto"' in component
    assert 'behavior: "smooth"' not in component


def test_review_preview_preserves_position_when_reviewed_html_changes():
    component = (
        Path(app.__file__).with_name("review_preview_component") / "index.html"
    ).read_text(encoding="utf-8")

    assert "pendingScrollTop = preview.contentWindow" in component
    assert "preview.contentWindow.scrollY" in component
    assert "if (!explicitScroll && pendingScrollTop !== null)" in component
    assert "preview.contentWindow.scrollTo" in component


def test_review_preview_fits_notebook_content_to_available_width():
    component = (
        Path(app.__file__).with_name("review_preview_component") / "index.html"
    ).read_text(encoding="utf-8")

    assert "function makeNotebookResponsive(doc)" in component
    assert "min-width: 0 !important" in component
    assert "white-space: pre-wrap !important" in component
    assert "max-width: 100% !important" in component
    assert "makeNotebookResponsive(doc);" in component


def test_review_preview_exposes_expected_keyboard_shortcuts():
    component = (
        Path(app.__file__).with_name("review_preview_component") / "index.html"
    ).read_text(encoding="utf-8")

    assert 'Enter: "validate"' in component
    assert 'ArrowUp: "better"' in component
    assert 'ArrowDown: "worse"' in component
    assert 'ArrowLeft: "previous"' in component
    assert 'ArrowRight: "next"' in component
    assert 'tag === "input" || tag === "textarea"' in component


def test_keyboard_level_change_uses_one_shot_state_instead_of_widget_assignment():
    source = Path(app.__file__).read_text(encoding="utf-8")

    assert "st.session_state.pop(level_key, None)" in source
    assert "st.session_state[pending_level_key] = levels[target_index]" in source
    assert "pending_level = st.session_state.pop(pending_level_key, None)" in source


def test_review_keyboard_event_is_consumed_only_once():
    state = {}
    event = {"keyboard_action": "next", "event_id": "keyboard-1"}

    assert _consume_review_keyboard_event(
        state, event, event_key="last-keyboard"
    ) == "next"
    assert _consume_review_keyboard_event(
        state, event, event_key="last-keyboard"
    ) is None
    assert _consume_review_keyboard_event(
        state,
        {"keyboard_action": "unknown", "event_id": "keyboard-2"},
        event_key="last-keyboard",
    ) is None


def test_copy_review_rerun_preserves_the_active_copy():
    class FakeStreamlit:
        def __init__(self):
            self.session_state = {}
            self.rerun_called = False

        def rerun(self):
            self.rerun_called = True

    st = FakeStreamlit()
    _rerun_copy_review(st, "copy-ines-celia")

    assert st.rerun_called
    _restore_reviewed_copy(
        st.session_state, ("copy-maire-lambin", "copy-ines-celia")
    )
    assert st.session_state["active-analysis-copy"] == "copy-ines-celia"


def test_copy_review_restore_ignores_a_copy_no_longer_visible():
    state = {"tpstudio-review-copy-to-restore": "copy-hidden"}

    _restore_reviewed_copy(state, ("copy-visible",))

    assert "active-analysis-copy" not in state
    assert "tpstudio-review-copy-to-restore" not in state


def test_next_unverified_copy_follows_batch_order_and_wraps():
    progress = (
        ("copy-1", 4, 4, False),
        ("copy-2", 2, 4, False),
        ("reference", 0, 4, True),
        ("copy-3", 0, 4, False),
    )

    assert _next_unverified_copy_id(progress, "copy-1") == "copy-2"
    assert _next_unverified_copy_id(progress, "copy-2") == "copy-3"
    assert _next_unverified_copy_id(progress, "copy-3") == "copy-2"


def test_next_unverified_copy_returns_none_when_the_batch_is_complete():
    progress = (
        ("copy-1", 4, 4, False),
        ("copy-2", 4, 4, False),
        ("reference", 0, 4, True),
    )

    assert _next_unverified_copy_id(progress, "copy-1") is None


def test_next_copy_follows_display_order_without_wrapping():
    progress = (
        ("copy-1", 4, 4, False),
        ("reference", 0, 4, True),
        ("copy-2", 2, 4, False),
    )

    assert _next_copy_id(progress, "copy-1") == "copy-2"
    assert _next_copy_id(progress, "copy-2") is None


def test_validation_status_is_explicit_for_copy_selection():
    assert _validation_status_label(0, 5) == "À vérifier"
    assert _validation_status_label(2, 5) == "En cours (2/5)"
    assert _validation_status_label(5, 5) == "✅ Vérifiée"
    assert _validation_status_label(0, 0) == "—"


def test_analysis_summary_table_is_collapsed_by_default():
    source = Path(app.__file__).read_text(encoding="utf-8")

    assert 'st.expander("Tableau récapitulatif du lot", expanded=False)' in source


def test_annotation_navigation_selects_and_requests_one_scroll():
    state = {}

    _navigate_annotation(
        state,
        "choice",
        "scroll-sequence",
        "scroll-request",
        "annotation-2",
    )
    assert state == {
        "choice": "annotation-2",
        "scroll-sequence": 1,
        "scroll-request": {"annotation_id": "annotation-2", "sequence": 1},
    }

    state.pop("scroll-request")
    _navigate_annotation(
        state,
        "choice",
        "scroll-sequence",
        "scroll-request",
        "annotation-1",
    )
    assert state == {
        "choice": "annotation-1",
        "scroll-sequence": 2,
        "scroll-request": {"annotation_id": "annotation-1", "sequence": 2},
    }


def test_web_errors_do_not_expose_workspace_paths():
    for text in ("/Users/example/private/tp.ipynb", "/home/student/tp.ipynb", "/var/folders/xx/tp.ipynb", r"C:\\Users\\Student\\tp.ipynb"):
        message = web_error_message(ValueError(text))
        assert message == "Impossible de préparer le lot."
        assert text not in message
    assert web_error_message(ValueError("Aucune copie sélectionnée.")) == "Aucune copie sélectionnée."


def test_semantic_provider_factory_is_explicit_and_does_not_store_key(monkeypatch):
    assert _build_semantic_provider(False, environ={"OPENAI_API_KEY": "secret"}) is None
    assert _build_semantic_provider(True, environ={}) is None
    observed = {}

    class FakeProvider:
        def __init__(self, *, model=None, **kwargs):
            observed["model"] = model
            observed["kwargs"] = kwargs

        def analyze(self, contract, student_response):
            raise AssertionError("Aucun appel réseau attendu dans ce test.")

    monkeypatch.setenv("TPSTUDIO_OPENAI_MODEL", "public-test-model")
    monkeypatch.setattr(app, "OpenAISemanticAnalysisProvider", FakeProvider)
    provider = _build_semantic_provider(True, environ={"OPENAI_API_KEY": "secret"})
    assert isinstance(provider, CachedSemanticAnalysisProvider)
    assert isinstance(provider.provider, FakeProvider)
    assert observed == {"model": "public-test-model", "kwargs": {}}
    assert "secret" not in repr(provider)


def test_analysis_signature_is_stable_and_option_model_specific():
    base = (("copy",), "out", WebBatchOptions())
    assert _analysis_signature(base, False, "gpt-5-mini") == _analysis_signature(base, False, "gpt-5-mini")
    assert _analysis_signature(base, False, "gpt-5-mini") != _analysis_signature(base, True, "gpt-5-mini")
    assert _analysis_signature(base, True, "gpt-5-mini") != _analysis_signature(base, True, "other-model")
    assert _analysis_signature(base, True, "gpt-5-mini", False) != _analysis_signature(
        base, True, "gpt-5-mini", True
    )
    assert _analysis_signature(
        base, True, "gpt-5-mini", False, False
    ) != _analysis_signature(base, True, "gpt-5-mini", False, True)


def test_open_local_html_artifact_delegates_to_operating_system(tmp_path):
    html = tmp_path / "Copie corrigée.html"
    html.write_text("<html></html>", encoding="utf-8")
    opened = []
    assert _open_local_html_artifact(html, opener=lambda uri: opened.append(uri) or True)
    assert opened == [html.resolve().as_uri()]
    assert not _open_local_html_artifact(tmp_path / "absent.html", opener=lambda uri: True)


def test_html_preview_focuses_selected_annotation_safely():
    document = '<html><body><blockquote id="tpstudio:item"></blockquote></body></html>'
    focused = _focus_annotation_html(document, 'tpstudio:item')
    assert 'getElementById("tpstudio:item")' in focused
    assert "tpstudio-review-focus" in focused
    assert "scrollIntoView" in focused
    assert _focus_annotation_html(document, None) == document


def test_review_annotations_follow_rendered_notebook_order():
    def local(annotation_id, cell_index):
        return NotebookAnnotation(
            annotation_id, AnnotationKind.FEEDBACK, FeedbackAudience.STUDENT,
            annotation_id, (annotation_id,), None, None, cell_index,
            AnnotationPlacement.AFTER_CELL, TeacherReportSeverity.ATTENTION,
        )

    summary = StudentSummaryAnnotation(
        "summary", FeedbackAudience.STUDENT, "Synthèse",
        TeacherReportSeverity.IMPORTANT,
        SkippedAnnotationReason.TARGET_UNAVAILABLE,
    )
    plan = AnnotationPlan(
        "project", "source", (local("late", 12), local("early", 3)),
        summary_annotations=(summary,),
    )
    assert tuple(
        item.annotation_id for item in _ordered_review_annotations(plan)
    ) == ("summary", "early", "late")


def test_preview_click_event_is_consumed_once_and_updates_selection():
    state = {"choice": "last"}
    event = {"annotation_id": "first", "event_id": "event-1"}
    assert _consume_preview_click_event(
        state, event,
        event_key="seen", choice_key="choice", valid_ids=("first", "last"),
    )
    assert state == {"choice": "first", "seen": "event-1"}
    assert not _consume_preview_click_event(
        state, event,
        event_key="seen", choice_key="choice", valid_ids=("first", "last"),
    )


def test_compact_copy_issue_count_ignores_information_and_counts_reviews():
    row = SimpleNamespace(status="Analysée", error_message=None)
    overview = (
        SimpleNamespace(severity=SimpleNamespace(value="ok")),
        SimpleNamespace(severity=SimpleNamespace(value="review")),
    )
    graphs = (SimpleNamespace(requires_human_review=True),)
    semantics = (
        SimpleNamespace(
            contradictions=(),
            criteria=(SimpleNamespace(status="partial"),),
        ),
    )
    assert _copy_issue_count(row, overview, graphs, semantics) == 3


def test_compact_grade_label_is_hidden_without_first_lab_analysis():
    assert _suggested_grade_label(None) == "—"
    assert _suggested_grade_label(SimpleNamespace(project_id="snells-laws-mvp")) == "—"


def test_cached_text_grading_levels_are_coerced_to_rubric_levels():
    assert _coerce_rubric_level("Très bien", RubricLevel.ABSENT) is RubricLevel.VERY_GOOD
    assert _coerce_rubric_level("PARTIAL", RubricLevel.ABSENT) is RubricLevel.PARTIAL
    assert _coerce_rubric_level(
        AnnotationReviewLevel.TO_REVIEW, RubricLevel.ABSENT
    ) is RubricLevel.TO_REVIEW
    assert _coerce_rubric_level(3, RubricLevel.ABSENT) is RubricLevel.GOOD
    assert _coerce_rubric_level("ancienne-valeur", RubricLevel.GOOD) is RubricLevel.GOOD


def test_first_lab_grading_panel_only_displays_the_proposed_grade():
    class FakeStreamlit:
        def __init__(self):
            self.metrics = []
            self.keys = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def markdown(self, value):
            assert "Proposition de note formative" in value

        def caption(self, value):
            pass

        def selectbox(self, label, *, options, index, format_func, help, key):
            self.keys.append(key)
            assert format_func(options[index]) == "Absence de réponse"
            return options[index]

        def metric(self, label, value):
            self.metrics.append((label, value))

        def columns(self, widths):
            return self, self

        def button(self, label, **kwargs):
            assert label == "Copie suivante →"
            assert kwargs["disabled"] is True
            return False

    fake = FakeStreamlit()
    _render_first_lab_grading(
        fake,
        SimpleNamespace(
            project_id="first-lab-measurements",
            semantic_response_analyses=(),
            quantity_evaluations=(),
            graph_evaluations=(),
            has_placeholders=True,
            has_unexecuted_code=True,
        ),
        "copy-001",
    )
    assert fake.metrics == [("Note proposée", "4.0/20")]
    assert fake.keys == []


def test_weighted_grade_counts_all_reviewed_answers_in_one_category():
    suggestions = tuple(
        SimpleNamespace(
            decision=RubricDecision(criterion.criterion_id, RubricLevel.GOOD)
        )
        for criterion in FIRST_LAB_FORMATIVE_GRADING_PROFILE.criteria
    )
    levels = {
        "results_presentation": (
            RubricLevel.TO_REVIEW,
            RubricLevel.TO_REVIEW,
            RubricLevel.GOOD,
        )
    }

    assert _weighted_first_lab_score(levels, suggestions) == Decimal("14.7")


def test_first_lab_grading_panel_is_hidden_for_other_projects():
    class FailOnUse:
        def __getattr__(self, name):
            raise AssertionError(name)

    _render_first_lab_grading(
        FailOnUse(), SimpleNamespace(project_id="snells-laws-mvp"), "copy-001"
    )
