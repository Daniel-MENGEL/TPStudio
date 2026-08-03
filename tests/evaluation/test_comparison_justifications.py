import pytest

from tests.evaluation.test_comparison_interpretations import _evaluate
from tpstudio.evaluation import (
    ComparisonJustificationEvaluation, ComparisonJustificationEvaluationStatus as Status,
    ComparisonJustificationNotEvaluableReason as Reason,
    evaluate_comparison_justifications,
)
from tpstudio.expectations import (
    ComparisonJustificationElementKind as Kind, ComparisonJustificationExpectationSet,
    ComparisonJustificationRequirement as Requirement, ExpectedComparisonJustification,
    ExpectedComparisonJustificationElement,
)
from tpstudio.reasoning import ComparisonJustificationDetection


def _expectation(comparisons, *, group=True):
    elements = [
        ExpectedComparisonJustificationElement("en", Kind.NORMALIZED_ERROR_VALUE, Requirement.REQUIRED, ("E_n =",)),
        ExpectedComparisonJustificationElement("threshold", Kind.THRESHOLD_REFERENCE, Requirement.REQUIRED, ("En > 4",)),
        ExpectedComparisonJustificationElement("optional", Kind.UNCERTAINTY_REFERENCE, Requirement.OPTIONAL, ("incertitudes",)),
    ]
    if group:
        elements.extend((
            ExpectedComparisonJustificationElement("method", Kind.METHOD_LIMITATION, Requirement.ONE_OF_GROUP, ("méthode peu fiable",), "limits"),
            ExpectedComparisonJustificationElement("bias", Kind.EXPERIMENTAL_BIAS, Requirement.ONE_OF_GROUP, ("biais expérimental",), "limits"),
        ))
    return ComparisonJustificationExpectationSet(comparisons, (ExpectedComparisonJustification("comparison", tuple(elements)),))


def _result(texts=("forte E_n = 5,2 En > 4 méthode peu fiable",), *, group=True, failures=0):
    interpretations, references, _ = _evaluate(texts, failures=failures)
    expectations = _expectation(references.expectation_set, group=group)
    return evaluate_comparison_justifications(interpretations, expectations), interpretations, expectations


def _custom_result(text, elements):
    interpretations, references, _ = _evaluate((text,))
    expectations = ComparisonJustificationExpectationSet(
        references.expectation_set,
        (ExpectedComparisonJustification("comparison", tuple(elements)),),
    )
    return evaluate_comparison_justifications(interpretations, expectations)


def test_enum_values_are_exact() -> None:
    assert tuple(item.value for item in Status) == ("complete", "partial", "missing", "not_evaluable")
    assert tuple(item.value for item in Reason) == ("source_unavailable", "source_ambiguous")


def test_complete_required_and_alternative_group_properties() -> None:
    result, interpretations, _ = _result()
    item = result.evaluations[0]
    assert item.complete and item.status is Status.COMPLETE
    assert item.interpretation_evaluation is interpretations.evaluations[0]
    assert item.missing_required_element_ids == ()
    assert item.satisfied_alternative_groups == ("limits",) and item.missing_alternative_groups == ()


@pytest.mark.parametrize("text", ["forte E_n = 5,2 méthode peu fiable", "forte E_n = 5,2 En > 4", "forte incertitudes"])
def test_partial_for_missing_required_group_or_optional_only(text) -> None:
    result, _, _ = _result((text,))
    assert result.evaluations[0].partial


def test_missing_is_evaluable_even_when_interpretation_matches() -> None:
    result, _, _ = _result(("forte",))
    item = result.evaluations[0]
    assert item.missing and item.evaluable and not item.not_evaluable
    assert item.interpretation_status.value == "matches_objective_classification"


@pytest.mark.parametrize(("texts", "failures", "reason"), [
    ((), 1, Reason.SOURCE_UNAVAILABLE),
    (("forte", "forte"), 0, Reason.SOURCE_AMBIGUOUS),
])
def test_source_not_evaluable_policies(texts, failures, reason) -> None:
    result, _, _ = _result(texts, failures=failures)
    item = result.evaluations[0]
    assert item.status is Status.NOT_EVALUABLE and item.not_evaluable_reasons == (reason,)


def test_one_success_plus_failure_is_usable_and_occurrences_do_not_count_twice() -> None:
    result, _, _ = _result(("forte E_n = E_n = 5,2 En > 4 méthode peu fiable",), failures=1)
    item = result.evaluations[0]
    assert item.complete and len(item.source_candidates) == 2
    assert len(item.detection.for_element("en")) == 2


def test_two_elements_same_group_satisfy_group_once() -> None:
    result, _, _ = _result(("forte E_n = 5 En > 4 méthode peu fiable biais expérimental",))
    assert result.evaluations[0].satisfied_alternative_groups == ("limits",)


def test_manual_incomplete_detection_is_rejected_as_noncanonical() -> None:
    result, _, _ = _result()
    item = result.evaluations[0]
    incomplete = ComparisonJustificationDetection(item.expectation, item.detection.observations[:-1])
    with pytest.raises(ValueError, match="texte résolu"):
        ComparisonJustificationEvaluation(item.expectation, item.interpretation_evaluation, None, item.source_candidates, item.source_resolution, incomplete, Status.PARTIAL)


def test_set_api_and_collection_properties() -> None:
    result, _, _ = _result()
    item = result.get("comparison")
    assert result.for_status(Status.COMPLETE) == (item,)
    assert result.complete == (item,) and result.all_complete and result.all_evaluable
    assert not result.has_partial and not result.has_missing and not result.has_not_evaluable
    assert item.student_normalized_error_evaluation is None and item.student_normalized_error_status is None


def test_optional_only_observed_is_partial_never_complete() -> None:
    optional = ExpectedComparisonJustificationElement(
        "optional", Kind.UNCERTAINTY_REFERENCE, Requirement.OPTIONAL,
        ("incertitudes",),
    )
    item = _custom_result("forte incertitudes", (optional,)).evaluations[0]
    assert item.partial and not item.complete and not item.missing


def test_multiple_optional_only_all_observed_remain_partial() -> None:
    elements = (
        ExpectedComparisonJustificationElement("a", Kind.UNCERTAINTY_REFERENCE, Requirement.OPTIONAL, ("incertitudes",)),
        ExpectedComparisonJustificationElement("b", Kind.MEASUREMENT_LIMITATION, Requirement.OPTIONAL, ("protocole limité",)),
    )
    assert _custom_result("forte incertitudes protocole limité", elements).evaluations[0].status is Status.PARTIAL


def test_optional_only_without_observation_is_missing() -> None:
    optional = ExpectedComparisonJustificationElement("optional", Kind.UNCERTAINTY_REFERENCE, Requirement.OPTIONAL, ("incertitudes",))
    assert _custom_result("forte", (optional,)).evaluations[0].status is Status.MISSING


@pytest.mark.parametrize("text", ["forte E_n =", "forte E_n = incertitudes"])
def test_satisfied_required_is_complete_with_optional_absent_or_present(text) -> None:
    elements = (
        ExpectedComparisonJustificationElement("required", Kind.NORMALIZED_ERROR_VALUE, Requirement.REQUIRED, ("E_n =",)),
        ExpectedComparisonJustificationElement("optional", Kind.UNCERTAINTY_REFERENCE, Requirement.OPTIONAL, ("incertitudes",)),
    )
    assert _custom_result(text, elements).evaluations[0].status is Status.COMPLETE


@pytest.mark.parametrize("suffix", ["", " incertitudes"])
def test_satisfied_alternative_group_is_complete_with_optional_absent_or_present(suffix) -> None:
    elements = (
        ExpectedComparisonJustificationElement("method", Kind.METHOD_LIMITATION, Requirement.ONE_OF_GROUP, ("méthode limitée",), "limits"),
        ExpectedComparisonJustificationElement("bias", Kind.EXPERIMENTAL_BIAS, Requirement.ONE_OF_GROUP, ("biais",), "limits"),
        ExpectedComparisonJustificationElement("optional", Kind.UNCERTAINTY_REFERENCE, Requirement.OPTIONAL, ("incertitudes",)),
    )
    assert _custom_result("forte méthode limitée" + suffix, elements).evaluations[0].status is Status.COMPLETE


def test_manual_statuses_reject_optional_only_and_satisfied_required_inconsistencies() -> None:
    optional = ExpectedComparisonJustificationElement("optional", Kind.UNCERTAINTY_REFERENCE, Requirement.OPTIONAL, ("incertitudes",))
    partial = _custom_result("forte incertitudes", (optional,)).evaluations[0]
    with pytest.raises(ValueError):
        ComparisonJustificationEvaluation(partial.expectation, partial.interpretation_evaluation, None, partial.source_candidates, partial.source_resolution, partial.detection, Status.COMPLETE)
    missing = _custom_result("forte", (optional,)).evaluations[0]
    with pytest.raises(ValueError):
        ComparisonJustificationEvaluation(missing.expectation, missing.interpretation_evaluation, None, missing.source_candidates, missing.source_resolution, missing.detection, Status.PARTIAL)
    required = ExpectedComparisonJustificationElement("required", Kind.NORMALIZED_ERROR_VALUE, Requirement.REQUIRED, ("E_n =",))
    complete = _custom_result("forte E_n =", (required,)).evaluations[0]
    with pytest.raises(ValueError):
        ComparisonJustificationEvaluation(complete.expectation, complete.interpretation_evaluation, None, complete.source_candidates, complete.source_resolution, complete.detection, Status.PARTIAL)
