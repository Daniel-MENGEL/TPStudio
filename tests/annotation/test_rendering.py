from tpstudio.annotation import AnnotationKind, AnnotationPlacement, NotebookAnnotation, render_notebook_annotation
from dataclasses import replace
from tpstudio.annotation.rendering import annotation_css, annotation_presentation
from tpstudio.feedback import FeedbackAudience
from tpstudio.reporting import TeacherReportSeverity


def _item(placement):
    return NotebookAnnotation("tpstudio:stable", AnnotationKind.FEEDBACK, FeedbackAudience.STUDENT, "Message inchangé", ("f1",), "p", None, 0, placement, TeacherReportSeverity.INFO)


def test_appended_render_has_balanced_invisible_markers_and_exact_message() -> None:
    text = render_notebook_annotation(_item(AnnotationPlacement.APPEND_TO_MARKDOWN))
    assert "TPSTUDIO:BEGIN annotation_id=tpstudio:stable" in text
    assert "TPSTUDIO:END annotation_id=tpstudio:stable" in text
    assert "Message inchangé" in text and "score" not in text.lower()
    assert 'id="tpstudio:stable"' in text


def test_dedicated_render_is_deterministic() -> None:
    item = _item(AnnotationPlacement.AFTER_CELL)
    assert render_notebook_annotation(item) == render_notebook_annotation(item)
    text = render_notebook_annotation(item)
    assert text
    assert "TPSTUDIO:ANNOTATION" in text


def test_severity_maps_to_explicit_accessible_presentation() -> None:
    labels = {
        TeacherReportSeverity.INFO: ("info", "Très bien"),
        TeacherReportSeverity.ATTENTION: ("review", "À vérifier"),
        TeacherReportSeverity.IMPORTANT: ("important", "Remarque"),
        TeacherReportSeverity.BLOCKING: ("blocking", "Problème"),
    }
    for severity, (style, label) in labels.items():
        item = NotebookAnnotation("tpstudio:stable", AnnotationKind.FEEDBACK, FeedbackAudience.STUDENT, "Message inchangé", ("f1",), "p", None, 0, AnnotationPlacement.AFTER_CELL, severity)
        assert annotation_presentation(item) == (style, label)
        rendered = render_notebook_annotation(item)
        assert f"tpstudio-severity-{style}" in rendered
        assert f"<strong>{label}</strong>" in rendered
        assert "Retour TPStudio" not in rendered
        assert "Message inchangé" in rendered


def test_annotation_content_has_local_style_without_repeating_global_css() -> None:
    first = _item(AnnotationPlacement.AFTER_CELL)
    second = NotebookAnnotation("tpstudio:other", AnnotationKind.DIAGNOSTIC, FeedbackAudience.STUDENT, "<tag> & **gras**", ("f2",), "p", None, 0, AnnotationPlacement.AFTER_CELL, TeacherReportSeverity.BLOCKING)
    first_rendered = render_notebook_annotation(first)
    second_rendered = render_notebook_annotation(second)
    assert "<style>" not in first_rendered and "<style>" not in second_rendered
    assert first_rendered.count("tpstudio-annotation") == 1
    assert second_rendered.count("tpstudio-annotation") == 1
    assert "&lt;tag&gt; &amp; **gras**" in second_rendered


def test_review_level_overrides_visible_annotation_label():
    item = replace(
        _item(AnnotationPlacement.AFTER_CELL),
        metadata=(("review_level", "good"),),
    )
    rendered = render_notebook_annotation(item)
    assert "<strong>Bien</strong>" in rendered
    assert "<strong>Très bien</strong>" not in rendered


def test_to_verify_is_blue_while_partial_and_to_review_keep_their_colors():
    item = _item(AnnotationPlacement.AFTER_CELL)
    to_verify = replace(item, severity=TeacherReportSeverity.ATTENTION)
    partial = replace(to_verify, metadata=(("review_level", "partial"),))
    to_review = replace(
        item,
        severity=TeacherReportSeverity.IMPORTANT,
        metadata=(("review_level", "to_review"),),
    )

    assert "tpstudio-severity-review" in render_notebook_annotation(to_verify)
    assert "background:#e8f2ff" in render_notebook_annotation(to_verify)
    assert "tpstudio-severity-attention" in render_notebook_annotation(partial)
    assert "background:#fff4dc" in render_notebook_annotation(partial)
    assert "tpstudio-severity-important" in render_notebook_annotation(to_review)
    assert "<strong>À revoir</strong>" in render_notebook_annotation(to_review)


def test_label_only_annotation_hides_the_explanatory_message():
    item = replace(
        _item(AnnotationPlacement.AFTER_CELL),
        metadata=(("review_level", "very_good"), ("label_only", "true")),
    )

    rendered = render_notebook_annotation(item)

    assert "<strong>Très bien</strong>" in rendered
    assert "Message inchangé" not in rendered


def test_corrective_palette_progresses_from_amber_to_deep_red():
    css = annotation_css()

    assert ".tpstudio-severity-attention { background: #fff4dc; border-color: #d49a2a; }" in css
    assert ".tpstudio-severity-important { background: #fcefee; border-color: #d25555; }" in css
    assert ".tpstudio-severity-blocking { background: #fde8e8; border-color: #b91c1c; }" in css
