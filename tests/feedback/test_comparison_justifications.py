from dataclasses import FrozenInstanceError

import pytest

from tests.diagnostics.test_comparison_justifications import _diagnostics
from tests.evaluation.test_comparison_interpretations import _evaluate
from tests.evaluation.test_comparison_justifications import _custom_result, _expectation
from tpstudio.diagnostics import (
    ComparisonJustificationDiagnosticCode as Code,
    build_comparison_justification_diagnostics,
)
from tpstudio.evaluation import ComparisonInterpretationEvaluationStatus as InterpretationStatus, evaluate_comparison_justifications
from tpstudio.expectations import (
    ComparisonJustificationElementKind as Kind, ComparisonJustificationExpectationSet,
    ComparisonJustificationRequirement as Requirement, ComparisonPedagogicalContext as Context,
    ExpectedComparisonJustification, ExpectedComparisonJustificationElement,
)
from tpstudio.feedback import (
    ComparisonJustificationFeedbackCatalog as Catalog,
    ComparisonJustificationFeedbackItem as Item,
    ComparisonJustificationFeedbackRenderer, ComparisonJustificationFeedbackSet as FeedbackSet,
    ComparisonJustificationFeedbackTemplate as Template,
    ComparisonJustificationFeedbackVariant as Variant,
    FeedbackAudience as Audience, FeedbackPriority as Priority,
    comparison_justification_feedback_variant,
    french_comparison_justification_feedback_catalog,
    render_comparison_justification_feedback,
)


def _template(code=Code.JUSTIFICATION_PARTIAL, audience=Audience.STUDENT, priority=Priority.NORMAL, text=" texte ", variant=Variant.GENERIC, context=None, status=None):
    return Template(code, audience, priority, text, variant, context, status)


def _variant_for(text): return comparison_justification_feedback_variant(_diagnostics(text)[0].diagnostics[0])


def test_variant_enum_and_canonical_classification() -> None:
    assert tuple(item.value for item in Variant) == ("generic", "required_elements_missing", "alternative_groups_missing", "required_and_alternative_missing", "optional_only")
    assert _variant_for("forte E_n = 5 méthode peu fiable") is Variant.REQUIRED_ELEMENTS_MISSING
    assert _variant_for("forte E_n = 5 En > 4") is Variant.ALTERNATIVE_GROUPS_MISSING
    assert _variant_for("forte incertitudes") is Variant.REQUIRED_AND_ALTERNATIVE_MISSING
    assert _variant_for("forte") is Variant.GENERIC


def test_optional_only_variant() -> None:
    optional = ExpectedComparisonJustificationElement("optional", Kind.UNCERTAINTY_REFERENCE, Requirement.OPTIONAL, ("incertitudes",))
    evaluations = _custom_result("forte incertitudes", (optional,))
    diagnostic = build_comparison_justification_diagnostics(evaluations).diagnostics[0]
    assert comparison_justification_feedback_variant(diagnostic) is Variant.OPTIONAL_ONLY


def test_template_validation_exact_text_and_immutability() -> None:
    template = _template()
    assert template.text == " texte "
    with pytest.raises(FrozenInstanceError): template.text = "x"
    for text in ("", "  "):
        with pytest.raises(ValueError): _template(text=text)
    with pytest.raises(TypeError): _template(code="x")


def test_catalog_keys_get_exact_and_resolution_hierarchy() -> None:
    exact = _template(text="exact", variant=Variant.REQUIRED_ELEMENTS_MISSING, context=Context.OPEN, status=InterpretationStatus.MATCHES_OBJECTIVE_CLASSIFICATION)
    context = _template(text="context", variant=Variant.REQUIRED_ELEMENTS_MISSING, context=Context.OPEN)
    status = _template(text="status", variant=Variant.REQUIRED_ELEMENTS_MISSING, status=InterpretationStatus.MATCHES_OBJECTIVE_CLASSIFICATION)
    variant = _template(text="variant", variant=Variant.REQUIRED_ELEMENTS_MISSING)
    generic = _template(text="generic")
    catalog = Catalog((generic, variant, status, context, exact))
    assert catalog.get_exact(exact.code, exact.audience, exact.variant, exact.pedagogical_context, exact.interpretation_status) is exact
    assert catalog.resolve(exact.code, exact.audience, exact.variant, Context.OPEN, InterpretationStatus.MATCHES_OBJECTIVE_CLASSIFICATION) is exact
    assert catalog.resolve(exact.code, exact.audience, exact.variant, Context.OPEN, InterpretationStatus.CONTRADICTS_OBJECTIVE_CLASSIFICATION) is context
    assert catalog.resolve(exact.code, exact.audience, exact.variant, Context.COHERENCE_EXPECTED, InterpretationStatus.MATCHES_OBJECTIVE_CLASSIFICATION) is status
    assert catalog.resolve(exact.code, exact.audience, Variant.ALTERNATIVE_GROUPS_MISSING, Context.COHERENCE_EXPECTED, InterpretationStatus.CONTRADICTS_OBJECTIVE_CLASSIFICATION) is generic
    with pytest.raises(ValueError): Catalog(())
    with pytest.raises(ValueError): Catalog((generic, generic))


def test_no_fallback_between_code_audience_context_or_status() -> None:
    catalog = Catalog((_template(context=Context.OPEN, status=InterpretationStatus.MATCHES_OBJECTIVE_CLASSIFICATION),))
    assert catalog.resolve(Code.JUSTIFICATION_MISSING, Audience.STUDENT, Variant.GENERIC, Context.OPEN, InterpretationStatus.MATCHES_OBJECTIVE_CLASSIFICATION) is None
    assert catalog.resolve(Code.JUSTIFICATION_PARTIAL, Audience.TEACHER, Variant.GENERIC, Context.OPEN, InterpretationStatus.MATCHES_OBJECTIVE_CLASSIFICATION) is None
    assert catalog.resolve(Code.JUSTIFICATION_PARTIAL, Audience.STUDENT, Variant.GENERIC, Context.COHERENCE_EXPECTED, InterpretationStatus.CONTRADICTS_OBJECTIVE_CLASSIFICATION) is None


@pytest.mark.parametrize(("text", "variant", "priority"), [
    ("forte E_n = 5 méthode peu fiable", Variant.REQUIRED_ELEMENTS_MISSING, Priority.NORMAL),
    ("forte E_n = 5 En > 4", Variant.ALTERNATIVE_GROUPS_MISSING, Priority.NORMAL),
    ("forte incertitudes", Variant.REQUIRED_AND_ALTERNATIVE_MISSING, Priority.HIGH),
])
def test_french_partial_variants(text, variant, priority) -> None:
    diagnostics, _ = _diagnostics(text)
    feedback = render_comparison_justification_feedback(diagnostics, french_comparison_justification_feedback_catalog())
    assert len(feedback) == 2 and all(item.variant is variant for item in feedback)
    assert feedback.student_feedback[0].priority is priority


def test_french_optional_only_variant() -> None:
    optional = ExpectedComparisonJustificationElement("optional", Kind.UNCERTAINTY_REFERENCE, Requirement.OPTIONAL, ("incertitudes",))
    diagnostics = build_comparison_justification_diagnostics(_custom_result("forte incertitudes", (optional,)))
    feedback = render_comparison_justification_feedback(diagnostics, french_comparison_justification_feedback_catalog())
    assert feedback.student_feedback[0].variant is Variant.OPTIONAL_ONLY


def test_missing_matches_interpretation_specific_and_not_false_claim() -> None:
    diagnostics, _ = _diagnostics("forte")
    feedback = render_comparison_justification_feedback(diagnostics, french_comparison_justification_feedback_catalog())
    assert "correspond au classement" in feedback.student_feedback[0].text
    assert "fausse" not in feedback.student_feedback[0].text


def test_not_evaluable_teacher_only_and_structured_reason() -> None:
    evaluations, _, _ = __import__("tests.evaluation.test_comparison_justifications", fromlist=["_result"])._result((), failures=1)
    diagnostics = build_comparison_justification_diagnostics(evaluations)
    feedback = render_comparison_justification_feedback(diagnostics, french_comparison_justification_feedback_catalog())
    assert feedback.student_feedback == () and len(feedback.teacher_feedback) == 1
    assert feedback.teacher_feedback[0].not_evaluable_reasons == diagnostics.diagnostics[0].not_evaluable_reasons


def test_method_limitation_context_changes_feedback_only() -> None:
    interpretations, references, _ = _evaluate(("incohérente E_n = 5 En > 4",), context=Context.METHOD_LIMITATION_EXPECTED)
    expectations = _expectation(references.expectation_set)
    evaluations = evaluate_comparison_justifications(interpretations, expectations)
    diagnostics = build_comparison_justification_diagnostics(evaluations)
    feedback = render_comparison_justification_feedback(diagnostics, french_comparison_justification_feedback_catalog())
    assert "limite de la méthode" in feedback.student_feedback[0].text
    assert diagnostics.diagnostics[0].missing_alternative_groups == ("limits",)


def test_complete_and_incomplete_catalog_produce_no_automatic_feedback() -> None:
    complete, _, _ = __import__("tests.evaluation.test_comparison_justifications", fromlist=["_result"])._result()
    diagnostics = build_comparison_justification_diagnostics(complete)
    assert not render_comparison_justification_feedback(diagnostics, Catalog((_template(),))).has_feedback
    missing, _ = _diagnostics("forte")
    assert not render_comparison_justification_feedback(missing, Catalog((_template(),))).has_feedback


def test_item_set_identity_order_queries_priority_and_no_interpolation() -> None:
    diagnostics, _ = _diagnostics("forte incertitudes")
    diagnostic = diagnostics.diagnostics[0]
    student_template = _template(priority=Priority.HIGH, text="fixe", variant=Variant.REQUIRED_AND_ALTERNATIVE_MISSING)
    teacher_template = _template(audience=Audience.TEACHER, text="prof", variant=Variant.REQUIRED_AND_ALTERNATIVE_MISSING)
    student = Item(diagnostic, student_template, Variant.REQUIRED_AND_ALTERNATIVE_MISSING)
    teacher = Item(diagnostic, teacher_template, Variant.REQUIRED_AND_ALTERNATIVE_MISSING)
    feedback = FeedbackSet(diagnostics, (student, teacher))
    assert feedback.for_comparison("comparison") == (student, teacher)
    assert feedback.for_variant(Variant.REQUIRED_AND_ALTERNATIVE_MISSING) == (student, teacher)
    assert feedback.high_priority == (student,)
    assert student.text == "fixe" and "threshold" not in student.text and "limits" not in student.text
    assert not hasattr(student, "score") and not hasattr(student, "penalty")
    with pytest.raises(ValueError): FeedbackSet(diagnostics, (student, student))
    with pytest.raises(ValueError): FeedbackSet(diagnostics, (teacher, student))
