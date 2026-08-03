from dataclasses import FrozenInstanceError

import pytest

from tests.evaluation.test_comparison_interpretations import _evaluate
from tpstudio.diagnostics import (
    ComparisonInterpretationDiagnostic, ComparisonInterpretationDiagnosticBuilder,
    ComparisonInterpretationDiagnosticCode as Code,
    ComparisonInterpretationDiagnosticSet,
    ComparisonInterpretationDiagnosticSource as Source,
    build_comparison_interpretation_diagnostics,
)
from tpstudio.evaluation import ComparisonInterpretationEvaluationStatus as Status


def _diagnostics(text="incohérente", **kwargs):
    evaluations, _, _ = _evaluate((text,), **kwargs)
    return build_comparison_interpretation_diagnostics(evaluations), evaluations


def test_enum_values_and_central_mapping_are_exact() -> None:
    assert tuple(item.value for item in Source) == ("classification", "evaluability")
    assert tuple(item.value for item in Code) == ("interpretation_partially_matches", "interpretation_contradicts", "interpretation_not_evaluable")
    expected = (
        (Source.CLASSIFICATION, Status.PARTIALLY_MATCHES_OBJECTIVE_CLASSIFICATION, "comparison_interpretation.partially_matches"),
        (Source.CLASSIFICATION, Status.CONTRADICTS_OBJECTIVE_CLASSIFICATION, "comparison_interpretation.contradicts"),
        (Source.EVALUABILITY, Status.NOT_EVALUABLE, "comparison_interpretation.not_evaluable"),
    )
    assert tuple((code.source, code.status, code.message_key) for code in Code) == expected


@pytest.mark.parametrize(("text", "code"), [
    ("incohérente", Code.INTERPRETATION_PARTIALLY_MATCHES),
    ("compatible", Code.INTERPRETATION_CONTRADICTS),
    ("aucune", Code.INTERPRETATION_NOT_EVALUABLE),
])
def test_builder_maps_each_non_matching_status_once(text, code) -> None:
    diagnostics, evaluations = _diagnostics(text)
    assert len(diagnostics) == 1 and diagnostics.diagnostics[0].code is code
    assert diagnostics.diagnostics[0].evaluation is evaluations.evaluations[0]


def test_matches_has_no_positive_diagnostic() -> None:
    diagnostics, _ = _diagnostics("forte")
    assert tuple(diagnostics) == () and not diagnostics.has_diagnostics


def test_diagnostic_properties_retain_all_structured_sources() -> None:
    diagnostics, evaluations = _diagnostics("incohérente")
    item = diagnostics.diagnostics[0]
    assert item.comparison_id == item.production_id == "comparison"
    assert item.status is evaluations.evaluations[0].status
    assert item.objective_status is evaluations.evaluations[0].objective_status
    assert item.observed_kind is evaluations.evaluations[0].observed_kind
    assert item.pedagogical_context is evaluations.evaluations[0].pedagogical_context
    assert item.student_normalized_error_status is None
    assert item.not_evaluable_reasons == ()
    assert not hasattr(item, "text") and not hasattr(item, "priority") and not hasattr(item, "score")


def test_not_evaluable_keeps_all_reasons_in_one_diagnostic() -> None:
    diagnostics, evaluations = _diagnostics("aucune", left="x = 0 m")
    assert len(diagnostics) == 1
    assert diagnostics.diagnostics[0].not_evaluable_reasons == evaluations.evaluations[0].not_evaluable_reasons
    assert len(diagnostics.diagnostics[0].not_evaluable_reasons) == 2


def test_model_rejects_matching_and_incompatible_codes_and_is_frozen() -> None:
    matches, _, _ = _evaluate(("forte",))
    with pytest.raises(ValueError):
        ComparisonInterpretationDiagnostic(matches.evaluations[0], Code.INTERPRETATION_CONTRADICTS)
    diagnostics, _ = _diagnostics()
    item = diagnostics.diagnostics[0]
    with pytest.raises(ValueError):
        ComparisonInterpretationDiagnostic(item.evaluation, Code.INTERPRETATION_CONTRADICTS)
    with pytest.raises(FrozenInstanceError):
        item.code = Code.INTERPRETATION_CONTRADICTS


def test_set_validation_identity_order_duplicates_and_foreign_items() -> None:
    diagnostics, evaluations = _diagnostics()
    item = diagnostics.diagnostics[0]
    with pytest.raises(ValueError):
        ComparisonInterpretationDiagnosticSet(evaluations, ())
    with pytest.raises(ValueError):
        ComparisonInterpretationDiagnosticSet(evaluations, (item, item))
    foreign, _ = _diagnostics()
    with pytest.raises(ValueError):
        ComparisonInterpretationDiagnosticSet(evaluations, foreign.diagnostics)


def test_set_queries_properties_and_builder_api() -> None:
    diagnostics, evaluations = _diagnostics()
    item = diagnostics.get("comparison")
    assert item is diagnostics.diagnostics[0]
    assert diagnostics.for_code(item.code) == (item,)
    assert diagnostics.for_source(item.source) == (item,)
    assert diagnostics.for_status(item.status) == (item,)
    assert diagnostics.partial_matches == (item,) and diagnostics.has_partial_matches
    assert not diagnostics.has_contradictions and not diagnostics.has_not_evaluable
    assert ComparisonInterpretationDiagnosticBuilder().build(evaluations).diagnostics[0].evaluation is item.evaluation
