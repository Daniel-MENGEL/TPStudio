from dataclasses import FrozenInstanceError, replace

import pytest

from tpstudio.evaluation import (
    EvaluationStatus,
    QuantityUncertaintyEvaluation,
    QuantityUncertaintyEvaluator,
    UncertaintyCriterionEvaluation,
    UncertaintyQualityCriterion,
    evaluate_quantity_structure,
    evaluate_quantity_uncertainty,
)
from tpstudio.expectations import (
    EvaluationBasis,
    ExpectedQuantity,
    PresenceRequirement,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
    UncertaintyQualityExpectationSet,
    UncertaintyQualitySpec,
)
from tpstudio.reasoning import QuantityObservation, extract_expected_quantity


def _context(
    *,
    significant_digits: tuple[int, ...] | None = (1, 2),
    positive: bool = True,
    alignment: bool = True,
    text: str = "g=(9,7 ± 0,4) m·s⁻²",
) -> tuple[object, UncertaintyQualityExpectationSet]:
    production = ScientificProductionSpec(
        "gravity",
        "Valeur de g",
        ScientificProductionKind.QUANTITY,
        (EvaluationBasis.STRUCTURAL,),
    )
    plan = ScientificProductionPlan("pendulum", "Pendule", (production,))
    quantity = ExpectedQuantity(
        "gravity",
        "g",
        canonical_unit="m·s⁻²",
        uncertainty_requirement=PresenceRequirement.REQUIRED,
    )
    quantity_set = QuantityExpectationSet(plan, (quantity,))
    structural = evaluate_quantity_structure(
        extract_expected_quantity(text, quantity), quantity_set
    )
    specification = UncertaintyQualitySpec(
        "gravity",
        require_strictly_positive=positive,
        allowed_significant_digits=significant_digits,
        require_matching_decimal_place=alignment,
    )
    return structural, UncertaintyQualityExpectationSet(
        quantity_set, (specification,)
    )


def _evaluate(**kwargs: object) -> QuantityUncertaintyEvaluation:
    structural, expectation_set = _context(**kwargs)  # type: ignore[arg-type]
    return evaluate_quantity_uncertainty(structural, expectation_set)  # type: ignore[arg-type]


def test_enum_values() -> None:
    assert [item.value for item in UncertaintyQualityCriterion] == [
        "strictly_positive",
        "significant_digits",
        "decimal_place_alignment",
    ]


def test_models_are_immutable() -> None:
    result = _evaluate()
    with pytest.raises(FrozenInstanceError):
        result.criteria = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.criteria[0].status = EvaluationStatus.DEFERRED  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"criterion": "strictly_positive"},
        {"status": "satisfied"},
        {"observation": object()},
    ],
)
def test_criterion_rejects_wrong_types(kwargs: dict[str, object]) -> None:
    structural, _ = _context()
    values: dict[str, object] = {
        "criterion": UncertaintyQualityCriterion.STRICTLY_POSITIVE,
        "status": EvaluationStatus.SATISFIED,
        "observation": structural.selected_observation,  # type: ignore[attr-defined]
    }
    values.update(kwargs)
    with pytest.raises(TypeError):
        UncertaintyCriterionEvaluation(**values)  # type: ignore[arg-type]


def test_deferred_is_rejected() -> None:
    with pytest.raises(ValueError):
        UncertaintyCriterionEvaluation(
            UncertaintyQualityCriterion.STRICTLY_POSITIVE,
            EvaluationStatus.DEFERRED,
        )


def test_applicable_status_requires_observed_uncertainty() -> None:
    with pytest.raises(ValueError):
        UncertaintyCriterionEvaluation(
            UncertaintyQualityCriterion.SIGNIFICANT_DIGITS,
            EvaluationStatus.SATISFIED,
        )
    structural, _ = _context(text="g=9,7 m·s⁻²")
    with pytest.raises(ValueError):
        UncertaintyCriterionEvaluation(
            UncertaintyQualityCriterion.SIGNIFICANT_DIGITS,
            EvaluationStatus.UNSATISFIED,
            structural.selected_observation,  # type: ignore[arg-type,attr-defined]
        )


def test_not_applicable_cannot_carry_observation() -> None:
    structural, _ = _context()
    with pytest.raises(ValueError):
        UncertaintyCriterionEvaluation(
            UncertaintyQualityCriterion.STRICTLY_POSITIVE,
            EvaluationStatus.NOT_APPLICABLE,
            structural.selected_observation,  # type: ignore[arg-type,attr-defined]
        )


@pytest.mark.parametrize(
    "text",
    ["g=(9,7 ± 0,4) m·s⁻²", "g=(9,70 ± 0,40) m·s⁻²"],
)
def test_default_policy_accepts_well_presented_uncertainty(text: str) -> None:
    result = _evaluate(text=text)
    assert all(item.status is EvaluationStatus.SATISFIED for item in result.criteria)
    assert result.failures == ()
    assert result.is_applicable
    assert result.satisfied


def test_decimal_place_mismatch_fails() -> None:
    result = _evaluate(text="g=(9,70 ± 0,4) m·s⁻²")
    assert result.failures == (
        result.get(UncertaintyQualityCriterion.DECIMAL_PLACE_ALIGNMENT),
    )


def test_too_many_significant_digits_fail() -> None:
    result = _evaluate(text="g=(9,7 ± 0,456) m·s⁻²")
    assert result.get(UncertaintyQualityCriterion.SIGNIFICANT_DIGITS).status is EvaluationStatus.UNSATISFIED  # type: ignore[union-attr]


@pytest.mark.parametrize("uncertainty", ["0", "-0,4"])
def test_non_positive_uncertainty_fails_only_positive_check(
    uncertainty: str,
) -> None:
    result = _evaluate(text=f"g=(9,7 ± {uncertainty}) m·s⁻²")
    assert result.get(UncertaintyQualityCriterion.STRICTLY_POSITIVE).status is EvaluationStatus.UNSATISFIED  # type: ignore[union-attr]
    assert result.get(UncertaintyQualityCriterion.SIGNIFICANT_DIGITS).status is EvaluationStatus.SATISFIED  # type: ignore[union-attr]


@pytest.mark.parametrize("text", ["g=9,7 m·s⁻²", "aucune grandeur"])
def test_missing_uncertainty_or_quantity_is_not_applicable(text: str) -> None:
    result = _evaluate(text=text)
    assert all(
        item.status is EvaluationStatus.NOT_APPLICABLE for item in result.criteria
    )
    assert result.failures == ()
    assert not result.is_applicable
    assert result.satisfied


@pytest.mark.parametrize(
    ("disabled", "criterion"),
    [
        ("positive", UncertaintyQualityCriterion.STRICTLY_POSITIVE),
        ("digits", UncertaintyQualityCriterion.SIGNIFICANT_DIGITS),
        ("alignment", UncertaintyQualityCriterion.DECIMAL_PLACE_ALIGNMENT),
    ],
)
def test_disabled_control_is_not_applicable(
    disabled: str, criterion: UncertaintyQualityCriterion
) -> None:
    kwargs: dict[str, object] = {}
    if disabled == "positive":
        kwargs["positive"] = False
    elif disabled == "digits":
        kwargs["significant_digits"] = None
    else:
        kwargs["alignment"] = False
    result = _evaluate(**kwargs)
    evaluation = result.get(criterion)
    assert evaluation is not None
    assert evaluation.status is EvaluationStatus.NOT_APPLICABLE
    assert evaluation.observation is None


@pytest.mark.parametrize(
    ("uncertainty", "allowed", "status"),
    [
        ("0,4", (1,), EvaluationStatus.SATISFIED),
        ("0,40", (1,), EvaluationStatus.UNSATISFIED),
        ("0,456", (3,), EvaluationStatus.SATISFIED),
        ("0,0040", (2,), EvaluationStatus.SATISFIED),
        ("4.00e-3", (3,), EvaluationStatus.SATISFIED),
    ],
)
def test_significant_digit_policy_preserves_trailing_zeroes(
    uncertainty: str,
    allowed: tuple[int, ...],
    status: EvaluationStatus,
) -> None:
    result = _evaluate(
        text=f"g=(9,7 ± {uncertainty}) m·s⁻²",
        significant_digits=allowed,
        alignment=False,
    )
    assert result.get(UncertaintyQualityCriterion.SIGNIFICANT_DIGITS).status is status  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("value", "uncertainty", "status"),
    [
        ("9.7", "0.4", EvaluationStatus.SATISFIED),
        ("9.70", "0.40", EvaluationStatus.SATISFIED),
        ("9.70", "0.4", EvaluationStatus.UNSATISFIED),
        ("9.7e3", "0.4e3", EvaluationStatus.SATISFIED),
        ("9.70e3", "0.4e3", EvaluationStatus.UNSATISFIED),
    ],
)
def test_decimal_alignment_uses_preserved_decimal_exponents(
    value: str, uncertainty: str, status: EvaluationStatus
) -> None:
    result = _evaluate(
        text=f"g=({value} ± {uncertainty}) m·s⁻²",
        significant_digits=None,
    )
    assert result.get(UncertaintyQualityCriterion.DECIMAL_PLACE_ALIGNMENT).status is status  # type: ignore[union-attr]


def test_result_uses_exact_structural_selection() -> None:
    result = _evaluate(text="g=9 ± 1 puis g=(9,7 ± 0,4) m·s⁻²")
    assert result.selected_observation is result.structural_evaluation.selected_observation
    assert all(
        item.observation is result.selected_observation for item in result.criteria
    )


def test_result_rejects_different_observation() -> None:
    structural, expectation_set = _context()
    specification = expectation_set.specifications[0]
    observation = structural.selected_observation  # type: ignore[attr-defined]
    assert isinstance(observation, QuantityObservation)
    foreign = QuantityObservation(
        production_id=observation.production_id,
        symbol=observation.symbol,
        value_text=observation.value_text,
        value=observation.value,
        uncertainty_marker=observation.uncertainty_marker,
        uncertainty_text=observation.uncertainty_text,
        uncertainty=observation.uncertainty,
        unit=observation.unit,
        matched_text=observation.matched_text,
        start=100,
        end=100 + len(observation.matched_text),
    )
    criteria = tuple(
        UncertaintyCriterionEvaluation(item.criterion, item.status, foreign)
        for item in _evaluate().criteria
    )
    with pytest.raises(ValueError):
        QuantityUncertaintyEvaluation(
            expectation_set,
            structural,  # type: ignore[arg-type]
            specification,
            criteria,
        )


def test_result_rejects_equal_copy_of_selected_observation() -> None:
    result = _evaluate()
    observation = result.selected_observation
    assert observation is not None
    equal_copy = replace(observation)
    assert equal_copy == observation and equal_copy is not observation
    criteria = tuple(
        UncertaintyCriterionEvaluation(item.criterion, item.status, equal_copy)
        for item in result.criteria
    )
    with pytest.raises(ValueError):
        QuantityUncertaintyEvaluation(
            result.expectation_set,
            result.structural_evaluation,
            result.specification,
            criteria,
        )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reordered"])
def test_result_requires_exact_criterion_order(mutation: str) -> None:
    result = _evaluate()
    criteria = list(result.criteria)
    if mutation == "missing":
        criteria.pop()
    elif mutation == "duplicate":
        criteria[-1] = criteria[0]
    else:
        criteria[0], criteria[1] = criteria[1], criteria[0]
    with pytest.raises(ValueError):
        QuantityUncertaintyEvaluation(
            result.expectation_set,
            result.structural_evaluation,
            result.specification,
            criteria,  # type: ignore[arg-type]
        )


def test_incoherent_expectation_sets_are_rejected() -> None:
    structural, _ = _context()
    _, other_set = _context(significant_digits=(1,))
    different_quantity_set = QuantityExpectationSet(
        other_set.quantity_expectation_set.plan,
        (
            ExpectedQuantity(
                "gravity",
                "G",
                canonical_unit="m·s⁻²",
                uncertainty_requirement=PresenceRequirement.REQUIRED,
            ),
        ),
    )
    incoherent = UncertaintyQualityExpectationSet(
        different_quantity_set, (UncertaintyQualitySpec("gravity"),)
    )
    with pytest.raises(ValueError):
        QuantityUncertaintyEvaluator().evaluate(structural, incoherent)  # type: ignore[arg-type]


def test_unconfigured_production_is_rejected() -> None:
    structural, expectation_set = _context()
    unrelated_spec = UncertaintyQualitySpec("other")
    production = ScientificProductionSpec(
        "other", "Autre", ScientificProductionKind.QUANTITY,
        (EvaluationBasis.STRUCTURAL,),
    )
    other_quantity = ExpectedQuantity(
        "other", "x", canonical_unit="m",
        uncertainty_requirement=PresenceRequirement.REQUIRED,
    )
    plan = ScientificProductionPlan("other", "Autre", (production,))
    unrelated = UncertaintyQualityExpectationSet(
        QuantityExpectationSet(plan, (other_quantity,)), (unrelated_spec,)
    )
    with pytest.raises(ValueError):
        QuantityUncertaintyEvaluator().evaluate(structural, unrelated)  # type: ignore[arg-type]
    assert expectation_set.get("gravity") is not None


def test_get_unknown_returns_none_and_properties_are_stable() -> None:
    result = _evaluate(text="g=(9,70 ± 0,4) m·s⁻²")
    assert result.production_id == "gravity"
    assert result.get("unknown") is None  # type: ignore[arg-type]
    assert result.failures == (result.criteria[2],)


def test_evaluation_is_deterministic_and_does_not_mutate_inputs() -> None:
    structural, expectation_set = _context()
    before = (structural, expectation_set)
    first = evaluate_quantity_uncertainty(structural, expectation_set)  # type: ignore[arg-type]
    second = evaluate_quantity_uncertainty(structural, expectation_set)  # type: ignore[arg-type]
    assert first == second
    assert before == (structural, expectation_set)


def test_result_contains_no_fact_diagnostic_or_score() -> None:
    result = _evaluate()
    assert not hasattr(result, "fact")
    assert not hasattr(result, "diagnostic")
    assert not hasattr(result, "score")
