from dataclasses import FrozenInstanceError

import pytest

from tests.evaluation.test_comparison_justifications import _result
from tpstudio.diagnostics import (
    ComparisonJustificationDiagnostic, ComparisonJustificationDiagnosticBuilder,
    ComparisonJustificationDiagnosticCode as Code, ComparisonJustificationDiagnosticSet,
    ComparisonJustificationDiagnosticSource as Source,
    build_comparison_justification_diagnostics,
)
from tpstudio.evaluation import ComparisonJustificationEvaluationStatus as Status


def _diagnostics(text="forte E_n = 5", **kwargs):
    evaluations, _, _ = _result((text,), **kwargs)
    return build_comparison_justification_diagnostics(evaluations), evaluations


def test_enum_values_and_mappings_are_exact() -> None:
    assert tuple(item.value for item in Source) == ("completeness", "evaluability")
    assert tuple(item.value for item in Code) == ("justification_partial", "justification_missing", "justification_not_evaluable")
    assert tuple((item.source, item.status, item.message_key) for item in Code) == (
        (Source.COMPLETENESS, Status.PARTIAL, "comparison_justification.partial"),
        (Source.COMPLETENESS, Status.MISSING, "comparison_justification.missing"),
        (Source.EVALUABILITY, Status.NOT_EVALUABLE, "comparison_justification.not_evaluable"),
    )


@pytest.mark.parametrize(("text", "kwargs", "code"), [
    ("forte E_n = 5", {}, Code.JUSTIFICATION_PARTIAL),
    ("forte", {}, Code.JUSTIFICATION_MISSING),
    (None, {"failures": 1}, Code.JUSTIFICATION_NOT_EVALUABLE),
])
def test_builder_maps_each_non_complete_status_once(text, kwargs, code) -> None:
    if text is None:
        evaluations, _, _ = _result((), **kwargs)
        diagnostics = build_comparison_justification_diagnostics(evaluations)
    else:
        diagnostics, evaluations = _diagnostics(text, **kwargs)
    assert len(diagnostics) == 1 and diagnostics.diagnostics[0].code is code
    assert diagnostics.diagnostics[0].evaluation is evaluations.evaluations[0]


def test_complete_has_no_positive_diagnostic() -> None:
    diagnostics, _ = _diagnostics("forte E_n = 5 En > 4 méthode peu fiable")
    assert tuple(diagnostics) == () and not diagnostics.has_diagnostics


def test_properties_preserve_a70g_a70e_and_structured_details() -> None:
    diagnostics, evaluations = _diagnostics("forte E_n = 5")
    item = diagnostics.diagnostics[0]
    assert item.comparison_id == item.production_id == "comparison"
    assert item.status is evaluations.evaluations[0].status
    assert item.interpretation_status is evaluations.evaluations[0].interpretation_status
    assert item.student_normalized_error_status is None
    assert item.observed_element_ids == ("en",)
    assert item.missing_required_element_ids == ("threshold",)
    assert item.missing_alternative_groups == ("limits",)
    assert item.satisfied_alternative_groups == ()
    assert item.pedagogical_context is evaluations.evaluations[0].interpretation_evaluation.pedagogical_context
    assert not hasattr(item, "text") and not hasattr(item, "priority") and not hasattr(item, "score")


def test_not_evaluable_keeps_one_reason_in_one_diagnostic() -> None:
    evaluations, _, _ = _result((), failures=1)
    diagnostics = build_comparison_justification_diagnostics(evaluations)
    assert len(diagnostics) == 1
    assert diagnostics.diagnostics[0].not_evaluable_reasons == evaluations.evaluations[0].not_evaluable_reasons


def test_model_rejects_complete_and_wrong_code_and_is_frozen() -> None:
    complete, _, _ = _result()
    with pytest.raises(ValueError): ComparisonJustificationDiagnostic(complete.evaluations[0], Code.JUSTIFICATION_PARTIAL)
    diagnostics, _ = _diagnostics()
    item = diagnostics.diagnostics[0]
    with pytest.raises(ValueError): ComparisonJustificationDiagnostic(item.evaluation, Code.JUSTIFICATION_MISSING)
    with pytest.raises(FrozenInstanceError): item.code = Code.JUSTIFICATION_MISSING


def test_set_validation_queries_and_collection_properties() -> None:
    diagnostics, evaluations = _diagnostics()
    item = diagnostics.get("comparison")
    assert diagnostics.for_code(item.code) == (item,)
    assert diagnostics.for_source(item.source) == (item,)
    assert diagnostics.for_status(item.status) == (item,)
    assert diagnostics.for_missing_required_element("threshold") == (item,)
    assert diagnostics.for_missing_alternative_group("limits") == (item,)
    assert diagnostics.partial == (item,) and diagnostics.has_partial
    assert not diagnostics.has_missing and not diagnostics.has_not_evaluable
    with pytest.raises(ValueError): ComparisonJustificationDiagnosticSet(evaluations, ())
    with pytest.raises(ValueError): ComparisonJustificationDiagnosticSet(evaluations, (item, item))
    foreign, _ = _diagnostics()
    with pytest.raises(ValueError): ComparisonJustificationDiagnosticSet(evaluations, foreign.diagnostics)
    assert ComparisonJustificationDiagnosticBuilder().build(evaluations).diagnostics[0].evaluation is item.evaluation
