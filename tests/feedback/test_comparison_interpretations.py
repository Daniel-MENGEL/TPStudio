from dataclasses import FrozenInstanceError

import pytest

from tests.diagnostics.test_comparison_interpretations import _diagnostics
from tpstudio.diagnostics import ComparisonInterpretationDiagnosticCode as Code
from tpstudio.expectations import ComparisonInterpretationKind as Kind, ComparisonPedagogicalContext as Context
from tpstudio.feedback import (
    ComparisonInterpretationFeedbackCatalog as Catalog,
    ComparisonInterpretationFeedbackItem as Item,
    ComparisonInterpretationFeedbackRenderer,
    ComparisonInterpretationFeedbackSet as FeedbackSet,
    ComparisonInterpretationFeedbackTemplate as Template,
    FeedbackAudience as Audience, FeedbackPriority as Priority,
    french_comparison_interpretation_feedback_catalog,
    render_comparison_interpretation_feedback,
)


def _template(code=Code.INTERPRETATION_PARTIALLY_MATCHES, audience=Audience.STUDENT, priority=Priority.NORMAL, text=" texte ", context=None, kind=None):
    return Template(code, audience, priority, text, context, kind)


def test_template_exact_values_validation_and_immutability() -> None:
    template = _template()
    assert template.text == " texte " and template.pedagogical_context is None and template.observed_kind is None
    with pytest.raises(FrozenInstanceError): template.text = "x"
    for text in ("", "  "):
        with pytest.raises(ValueError): _template(text=text)
    with pytest.raises(TypeError): _template(code="x")


def test_catalog_validation_get_exact_and_order() -> None:
    generic, teacher = _template(), _template(audience=Audience.TEACHER)
    catalog = Catalog([teacher, generic])
    assert tuple(catalog) == (teacher, generic) and len(catalog) == 2
    assert catalog.get_exact(generic.code, generic.audience, None, None) is generic
    with pytest.raises(ValueError): Catalog(())
    with pytest.raises(ValueError): Catalog((generic, generic))


def test_resolution_hierarchy_is_exact() -> None:
    code = Code.INTERPRETATION_PARTIALLY_MATCHES
    exact = _template(text="exact", context=Context.METHOD_LIMITATION_EXPECTED, kind=Kind.INCOHERENT)
    context = _template(text="context", context=Context.METHOD_LIMITATION_EXPECTED)
    kind = _template(text="kind", kind=Kind.INCOHERENT)
    generic = _template(text="generic")
    catalog = Catalog((generic, kind, context, exact))
    assert catalog.resolve(code, Audience.STUDENT, Context.METHOD_LIMITATION_EXPECTED, Kind.INCOHERENT) is exact
    assert catalog.resolve(code, Audience.STUDENT, Context.METHOD_LIMITATION_EXPECTED, Kind.COHERENT) is context
    assert catalog.resolve(code, Audience.STUDENT, Context.OPEN, Kind.INCOHERENT) is kind
    assert catalog.resolve(code, Audience.STUDENT, Context.OPEN, Kind.COHERENT) is generic


def test_no_fallback_between_code_audience_context_or_kind() -> None:
    catalog = Catalog((_template(context=Context.OPEN, kind=Kind.COHERENT),))
    assert catalog.resolve(Code.INTERPRETATION_CONTRADICTS, Audience.STUDENT, Context.OPEN, Kind.COHERENT) is None
    assert catalog.resolve(Code.INTERPRETATION_PARTIALLY_MATCHES, Audience.TEACHER, Context.OPEN, Kind.COHERENT) is None
    assert catalog.resolve(Code.INTERPRETATION_PARTIALLY_MATCHES, Audience.STUDENT, Context.COHERENCE_EXPECTED, Kind.INCOHERENT) is None


def test_french_catalog_generic_partial_and_contradiction() -> None:
    catalog = french_comparison_interpretation_feedback_catalog()
    partial, _ = _diagnostics("incohérente")
    feedback = render_comparison_interpretation_feedback(partial, catalog)
    assert len(feedback) == 2 and feedback.student_feedback[0].priority is Priority.NORMAL
    contradiction, _ = _diagnostics("compatible")
    feedback = render_comparison_interpretation_feedback(contradiction, catalog)
    assert len(feedback) == 2 and all(item.priority is Priority.HIGH for item in feedback)
    assert feedback.high_priority == tuple(feedback)


@pytest.mark.parametrize(("text", "fragment"), [
    ("incohérente", "limites de la méthode"),
    ("forte", None),
])
def test_method_limitation_context_variants(text, fragment) -> None:
    diagnostics, _ = _diagnostics(text, context=Context.METHOD_LIMITATION_EXPECTED)
    feedback = render_comparison_interpretation_feedback(diagnostics, french_comparison_interpretation_feedback_catalog())
    if fragment is None:
        assert feedback.feedback == ()
    else:
        assert fragment in feedback.student_feedback[0].text
        assert len(feedback.student_feedback) == 1


def test_method_limitation_strong_partial_specific_variant() -> None:
    diagnostics, _ = _diagnostics(
        "forte", context=Context.METHOD_LIMITATION_EXPECTED,
        left="x = (0 ± 0.4) m",
    )
    feedback = render_comparison_interpretation_feedback(
        diagnostics, french_comparison_interpretation_feedback_catalog()
    )
    assert "forte incohérence" in feedback.student_feedback[0].text


def test_not_evaluable_has_teacher_only_and_keeps_reasons() -> None:
    diagnostics, _ = _diagnostics("aucune", left="x = 0 m")
    feedback = render_comparison_interpretation_feedback(diagnostics, french_comparison_interpretation_feedback_catalog())
    assert feedback.student_feedback == () and len(feedback.teacher_feedback) == 1
    assert feedback.teacher_feedback[0].not_evaluable_reasons == diagnostics.diagnostics[0].not_evaluable_reasons


def test_incomplete_catalog_and_matches_produce_no_feedback() -> None:
    matches, _ = _diagnostics("forte")
    empty_result = render_comparison_interpretation_feedback(matches, Catalog((_template(),)))
    assert not empty_result.has_feedback
    contradiction, _ = _diagnostics("compatible")
    assert not render_comparison_interpretation_feedback(contradiction, Catalog((_template(),))).has_feedback


def test_item_and_set_validate_identity_code_context_kind_duplicates_and_order() -> None:
    diagnostics, _ = _diagnostics()
    diagnostic = diagnostics.diagnostics[0]
    template = _template()
    item = Item(diagnostic, template)
    assert item.text == template.text and item.diagnostic is diagnostic
    with pytest.raises(ValueError): Item(diagnostic, _template(code=Code.INTERPRETATION_CONTRADICTS))
    with pytest.raises(ValueError): FeedbackSet(diagnostics, (item, item))
    teacher = Item(diagnostic, _template(audience=Audience.TEACHER))
    with pytest.raises(ValueError): FeedbackSet(diagnostics, (teacher, item))


def test_feedback_queries_priority_does_not_reorder_and_no_values_are_interpolated() -> None:
    diagnostics, _ = _diagnostics()
    catalog = Catalog((_template(priority=Priority.HIGH, text="fixe"), _template(audience=Audience.TEACHER, priority=Priority.LOW, text="prof")))
    feedback = ComparisonInterpretationFeedbackRenderer().render(diagnostics, catalog)
    assert tuple(item.audience for item in feedback) == (Audience.STUDENT, Audience.TEACHER)
    assert feedback.for_comparison("comparison") == tuple(feedback)
    assert feedback.for_code(Code.INTERPRETATION_PARTIALLY_MATCHES) == tuple(feedback)
    assert feedback.for_priority(Priority.HIGH) == (feedback.feedback[0],)
    assert feedback.feedback[0].text == "fixe"
    assert not hasattr(feedback.feedback[0], "score") and not hasattr(feedback.feedback[0], "penalty")
