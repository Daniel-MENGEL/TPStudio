from pathlib import Path
from types import SimpleNamespace

import tpstudio.web.app as app
from tpstudio.semantic_analysis import CachedSemanticAnalysisProvider
from tpstudio.web.app import (
    _analysis_signature,
    _build_semantic_provider,
    _copy_issue_count,
    _consume_preview_click_event,
    _focus_annotation_html,
    _input_signature,
    _navigate_annotation,
    _open_local_html_artifact,
    _ordered_review_annotations,
    _render_first_lab_grading,
    _suggested_grade_label,
    web_error_message,
)
from tpstudio.annotation import (
    AnnotationKind, AnnotationPlacement, AnnotationPlan, NotebookAnnotation,
    SkippedAnnotationReason, StudentSummaryAnnotation,
)
from tpstudio.feedback import FeedbackAudience
from tpstudio.reporting import TeacherReportSeverity
from tpstudio.web.model import SelectedCopy, WebBatchOptions


def test_signature_changes_for_same_size_content_hashes():
    first = SelectedCopy("copy-001", "tp.ipynb", Path("tp.ipynb"), "a" * 64)
    second = SelectedCopy("copy-001", "tp.ipynb", Path("tp.ipynb"), "b" * 64)
    options = WebBatchOptions()
    assert _input_signature((first,), Path("out"), options) != _input_signature((second,), Path("out"), options)


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


def test_first_lab_grading_panel_only_displays_the_proposed_grade():
    class FakeStreamlit:
        def __init__(self):
            self.metrics = []
            self.keys = []

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


def test_first_lab_grading_panel_is_hidden_for_other_projects():
    class FailOnUse:
        def __getattr__(self, name):
            raise AssertionError(name)

    _render_first_lab_grading(
        FailOnUse(), SimpleNamespace(project_id="snells-laws-mvp"), "copy-001"
    )
