from dataclasses import FrozenInstanceError

import pytest

from tests.diagnostics.test_quantity_comparisons import _evaluation
from tpstudio.diagnostics import (
    QuantityComparisonDiagnosticCode as Code,
    build_quantity_comparison_diagnostics,
)
from tpstudio.expectations import ComparisonPedagogicalContext as Context
from tpstudio.feedback import (
    FeedbackAudience as Audience,
    FeedbackPriority as Priority,
    QuantityComparisonFeedbackCatalog,
    QuantityComparisonFeedbackItem,
    QuantityComparisonFeedbackRenderer,
    QuantityComparisonFeedbackSet,
    QuantityComparisonFeedbackTemplate,
    french_quantity_comparison_feedback_catalog,
    render_quantity_comparison_feedback,
)


def _diagnostics(right="x2 = (12.0 ± 0.2) m", *, left="x1 = (9.7 ± 0.4) m", context=Context.OPEN):
    return build_quantity_comparison_diagnostics(
        _evaluation(right, left=left, context=context)
    )


def _template(code=Code.COMPARISON_STRONGLY_INCOHERENT, audience=Audience.STUDENT, priority=Priority.HIGH, text="Texte", context=None):
    return QuantityComparisonFeedbackTemplate(code, audience, priority, text, context)


def test_template_is_immutable_preserves_text_and_validates_fields() -> None:
    template = _template(text="  Texte exact  ")
    assert template.text == "  Texte exact  "
    with pytest.raises(FrozenInstanceError):
        template.text = "autre"
    for text in ("", "   "):
        with pytest.raises(ValueError):
            _template(text=text)
    with pytest.raises(TypeError):
        _template(code="bad")
    with pytest.raises(TypeError):
        _template(audience="student")
    with pytest.raises(TypeError):
        _template(priority="high")
    with pytest.raises(TypeError):
        _template(context="open")


def test_catalog_converts_tuple_and_rejects_empty_invalid_or_duplicate_keys() -> None:
    template = _template()
    catalog = QuantityComparisonFeedbackCatalog([template])
    assert catalog.templates == (template,)
    with pytest.raises(FrozenInstanceError):
        catalog.templates = ()
    with pytest.raises(ValueError):
        QuantityComparisonFeedbackCatalog(())
    with pytest.raises(TypeError):
        QuantityComparisonFeedbackCatalog((object(),))
    with pytest.raises(ValueError):
        QuantityComparisonFeedbackCatalog((template, template))


def test_catalog_exact_and_contextual_resolution_policy() -> None:
    generic = _template(text="générique")
    contextual = _template(text="contextuel", context=Context.METHOD_LIMITATION_EXPECTED)
    teacher = _template(audience=Audience.TEACHER, text="professeur")
    catalog = QuantityComparisonFeedbackCatalog((generic, contextual, teacher))
    assert catalog.get_exact(generic.code, Audience.STUDENT, None) is generic
    assert catalog.resolve(generic.code, Audience.STUDENT, Context.METHOD_LIMITATION_EXPECTED) is contextual
    assert catalog.resolve(generic.code, Audience.STUDENT, Context.OPEN) is generic
    assert catalog.resolve(generic.code, Audience.TEACHER, Context.OPEN) is teacher
    assert catalog.resolve(Code.COMPARISON_NOT_EVALUABLE, Audience.STUDENT, Context.OPEN) is None
    assert catalog.resolve(generic.code, Audience.TEACHER, Context.METHOD_LIMITATION_EXPECTED) is teacher


def test_feedback_item_validates_code_and_context_and_derives_data() -> None:
    diagnostic = _diagnostics(context=Context.METHOD_LIMITATION_EXPECTED).diagnostics[0]
    template = _template(context=Context.METHOD_LIMITATION_EXPECTED)
    item = QuantityComparisonFeedbackItem(diagnostic, template)
    assert item.production_id == "comparison"
    assert item.code is diagnostic.code
    assert item.audience is Audience.STUDENT
    assert item.priority is Priority.HIGH
    assert item.text == "Texte"
    assert item.normalized_error == diagnostic.normalized_error
    assert item.not_evaluable_reasons == ()
    with pytest.raises(FrozenInstanceError):
        item.template = template
    with pytest.raises(ValueError):
        QuantityComparisonFeedbackItem(diagnostic, _template(code=Code.COMPARISON_NOT_EVALUABLE))
    with pytest.raises(ValueError):
        QuantityComparisonFeedbackItem(diagnostic, _template(context=Context.COHERENCE_EXPECTED))


def test_renderer_uses_diagnostic_then_student_teacher_order_not_priority() -> None:
    diagnostics = _diagnostics()
    student = _template(priority=Priority.LOW, text="étudiant")
    teacher = _template(audience=Audience.TEACHER, priority=Priority.HIGH, text="professeur")
    rendered = QuantityComparisonFeedbackRenderer().render(
        diagnostics, QuantityComparisonFeedbackCatalog((teacher, student))
    )
    assert tuple(item.audience for item in rendered) == (Audience.STUDENT, Audience.TEACHER)
    assert tuple(item.priority for item in rendered) == (Priority.LOW, Priority.HIGH)
    assert rendered.student_feedback == (rendered.feedback[0],)
    assert rendered.teacher_feedback == (rendered.feedback[1],)
    assert rendered.has_feedback and rendered.has_student_feedback and rendered.has_teacher_feedback


def test_feedback_set_rejects_foreign_duplicate_and_wrong_order_items() -> None:
    diagnostics = _diagnostics()
    diagnostic = diagnostics.diagnostics[0]
    student = QuantityComparisonFeedbackItem(diagnostic, _template())
    teacher = QuantityComparisonFeedbackItem(diagnostic, _template(audience=Audience.TEACHER))
    with pytest.raises(ValueError):
        QuantityComparisonFeedbackSet(diagnostics, (student, student))
    with pytest.raises(ValueError, match="ordre"):
        QuantityComparisonFeedbackSet(diagnostics, (teacher, student))
    foreign_diagnostic = _diagnostics().diagnostics[0]
    foreign = QuantityComparisonFeedbackItem(foreign_diagnostic, _template())
    with pytest.raises(ValueError):
        QuantityComparisonFeedbackSet(diagnostics, (foreign,))


def test_feedback_set_queries() -> None:
    rendered = render_quantity_comparison_feedback(
        _diagnostics(), QuantityComparisonFeedbackCatalog((_template(),))
    )
    item = rendered.feedback[0]
    assert rendered.for_production("comparison") == (item,)
    assert rendered.for_production("unknown") == ()
    assert rendered.for_audience(Audience.STUDENT) == (item,)
    assert rendered.for_code(item.code) == (item,)


def test_incomplete_catalog_and_no_matching_template_produce_no_feedback() -> None:
    catalog = QuantityComparisonFeedbackCatalog((
        _template(code=Code.COMPARISON_MODERATELY_INCOHERENT),
    ))
    rendered = render_quantity_comparison_feedback(_diagnostics(), catalog)
    assert rendered.feedback == () and not rendered.has_feedback


def test_coherent_result_has_no_feedback_even_with_explicit_catalog() -> None:
    diagnostics = _diagnostics(right="x2 = (9.8 ± 0.2) m")
    rendered = render_quantity_comparison_feedback(
        diagnostics, french_quantity_comparison_feedback_catalog()
    )
    assert rendered.feedback == ()


def test_french_moderate_feedback_is_student_normal_without_en_value() -> None:
    rendered = render_quantity_comparison_feedback(
        _diagnostics(right="x2 = (10.8 ± 0.2) m"),
        french_quantity_comparison_feedback_catalog(),
    )
    assert len(rendered.feedback) == 1
    item = rendered.feedback[0]
    assert item.audience is Audience.STUDENT and item.priority is Priority.NORMAL
    assert item.normalized_error is not None
    assert str(item.normalized_error) not in item.text
    assert "Votre En" not in item.text


def test_french_generic_strong_feedback_is_student_high_only() -> None:
    rendered = render_quantity_comparison_feedback(
        _diagnostics(), french_quantity_comparison_feedback_catalog()
    )
    assert len(rendered.feedback) == 1
    assert rendered.feedback[0].audience is Audience.STUDENT
    assert rendered.feedback[0].priority is Priority.HIGH


def test_method_limitation_uses_contextual_student_and_teacher_variants() -> None:
    diagnostics = _diagnostics(context=Context.METHOD_LIMITATION_EXPECTED)
    diagnostic = diagnostics.diagnostics[0]
    assert diagnostic.code is Code.COMPARISON_STRONGLY_INCOHERENT
    rendered = render_quantity_comparison_feedback(
        diagnostics, french_quantity_comparison_feedback_catalog()
    )
    assert tuple(item.audience for item in rendered) == (Audience.STUDENT, Audience.TEACHER)
    assert tuple(item.priority for item in rendered) == (Priority.HIGH, Priority.NORMAL)
    assert "limitation de méthode" in rendered.student_feedback[0].text
    assert "pédagogiquement plausible" in rendered.teacher_feedback[0].text
    assert len(rendered.student_feedback) == 1


def test_not_evaluable_french_feedback_is_teacher_only_and_keeps_reasons() -> None:
    diagnostics = _diagnostics(left="x1 = 9.7", right="x2 = 9.8")
    rendered = render_quantity_comparison_feedback(
        diagnostics, french_quantity_comparison_feedback_catalog()
    )
    assert rendered.student_feedback == ()
    assert len(rendered.teacher_feedback) == 1
    assert len(rendered.teacher_feedback[0].not_evaluable_reasons) == 4


def test_no_implicit_catalog_or_scoring_contract_exists() -> None:
    with pytest.raises(TypeError):
        render_quantity_comparison_feedback(_diagnostics(), None)
    item = render_quantity_comparison_feedback(
        _diagnostics(), french_quantity_comparison_feedback_catalog()
    ).feedback[0]
    for name in ("score", "penalty", "weight", "points", "grade", "severity"):
        assert not hasattr(item, name)
    assert "correctement calculé" not in item.text
    assert "Votre calcul" not in item.text
