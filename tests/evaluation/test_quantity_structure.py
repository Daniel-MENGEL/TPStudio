from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from tpstudio.evaluation import (
    EvaluationStatus,
    QuantityCriterionEvaluation,
    QuantityStructuralCriterion,
    QuantityStructuralEvaluation,
    QuantityStructuralEvaluator,
    evaluate_quantity_structure,
)
from tpstudio.expectations import (
    EvaluationBasis,
    ExpectedQuantity,
    PresenceRequirement,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
)
from tpstudio.reasoning import (
    QuantityDetection,
    QuantityObservation,
    extract_expected_quantity,
)


def _context(
    *,
    required: bool = True,
    unit: PresenceRequirement = PresenceRequirement.REQUIRED,
    uncertainty: PresenceRequirement = PresenceRequirement.REQUIRED,
    justification: PresenceRequirement = PresenceRequirement.IGNORE,
) -> tuple[ExpectedQuantity, QuantityExpectationSet]:
    production = ScientificProductionSpec(
        id="gravity_dynamic",
        label="Valeur dynamique de g",
        kind=ScientificProductionKind.QUANTITY,
        evaluation_bases=(EvaluationBasis.STRUCTURAL,),
        required=required,
    )
    plan = ScientificProductionPlan("pendulum", "Pendule", (production,))
    expectation = ExpectedQuantity(
        production_id=production.id,
        canonical_symbol="g",
        canonical_unit="m·s⁻²",
        unit_requirement=unit,
        uncertainty_requirement=uncertainty,
        uncertainty_justification_requirement=justification,
    )
    return expectation, QuantityExpectationSet(plan, (expectation,))


def _evaluate(
    text: str,
    *,
    required: bool = True,
    unit: PresenceRequirement = PresenceRequirement.REQUIRED,
    uncertainty: PresenceRequirement = PresenceRequirement.REQUIRED,
    justification: PresenceRequirement = PresenceRequirement.IGNORE,
) -> QuantityStructuralEvaluation:
    expectation, expectation_set = _context(
        required=required,
        unit=unit,
        uncertainty=uncertainty,
        justification=justification,
    )
    detection = extract_expected_quantity(text, expectation)
    return evaluate_quantity_structure(detection, expectation_set)


def _observation(
    *, start: int = 0, unit: str | None = None, uncertainty: bool = False
) -> QuantityObservation:
    text = "g=9"
    return QuantityObservation(
        production_id="gravity_dynamic",
        symbol="g",
        value_text="9",
        value=Decimal("9"),
        uncertainty_marker="±" if uncertainty else None,
        uncertainty_text="1" if uncertainty else None,
        uncertainty=Decimal("1") if uncertainty else None,
        unit=unit,
        matched_text=text,
        start=start,
        end=start + len(text),
    )


def test_enum_values() -> None:
    assert [item.value for item in EvaluationStatus] == [
        "satisfied", "unsatisfied", "not_applicable", "deferred"
    ]
    assert [item.value for item in QuantityStructuralCriterion] == [
        "quantity_present",
        "unit_present",
        "uncertainty_present",
        "uncertainty_justification_present",
    ]


def test_models_are_immutable() -> None:
    result = _evaluate("g=9 m·s⁻²")
    with pytest.raises(FrozenInstanceError):
        result.selected_observation = None  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.criteria[0].status = EvaluationStatus.DEFERRED  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"criterion": "quantity_present"},
        {"requirement": "required"},
        {"status": "satisfied"},
        {"observation": object()},
    ],
)
def test_criterion_rejects_wrong_field_types(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "criterion": QuantityStructuralCriterion.QUANTITY_PRESENT,
        "requirement": PresenceRequirement.REQUIRED,
        "status": EvaluationStatus.SATISFIED,
        "observation": _observation(),
    }
    values.update(kwargs)
    with pytest.raises(TypeError):
        QuantityCriterionEvaluation(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("requirement", "status", "has_observation"),
    [
        (PresenceRequirement.IGNORE, EvaluationStatus.SATISFIED, True),
        (PresenceRequirement.REQUIRED, EvaluationStatus.DEFERRED, True),
        (PresenceRequirement.REQUIRED, EvaluationStatus.NOT_APPLICABLE, False),
        (PresenceRequirement.REQUIRED, EvaluationStatus.SATISFIED, False),
        (PresenceRequirement.OPTIONAL, EvaluationStatus.UNSATISFIED, False),
        (PresenceRequirement.REQUIRED, EvaluationStatus.UNSATISFIED, True),
    ],
)
def test_quantity_criterion_rejects_incoherent_states(
    requirement: PresenceRequirement,
    status: EvaluationStatus,
    has_observation: bool,
) -> None:
    with pytest.raises(ValueError):
        QuantityCriterionEvaluation(
            QuantityStructuralCriterion.QUANTITY_PRESENT,
            requirement,
            status,
            _observation() if has_observation else None,
        )


@pytest.mark.parametrize(
    ("criterion", "requirement", "status", "observation"),
    [
        (
            QuantityStructuralCriterion.UNIT_PRESENT,
            PresenceRequirement.REQUIRED,
            EvaluationStatus.DEFERRED,
            None,
        ),
        (
            QuantityStructuralCriterion.UNIT_PRESENT,
            PresenceRequirement.IGNORE,
            EvaluationStatus.NOT_APPLICABLE,
            _observation(unit="m·s⁻²"),
        ),
        (
            QuantityStructuralCriterion.UNCERTAINTY_PRESENT,
            PresenceRequirement.OPTIONAL,
            EvaluationStatus.UNSATISFIED,
            _observation(),
        ),
        (
            QuantityStructuralCriterion.UNCERTAINTY_PRESENT,
            PresenceRequirement.REQUIRED,
            EvaluationStatus.SATISFIED,
            _observation(),
        ),
    ],
)
def test_component_criterion_rejects_incoherent_states(
    criterion: QuantityStructuralCriterion,
    requirement: PresenceRequirement,
    status: EvaluationStatus,
    observation: QuantityObservation | None,
) -> None:
    with pytest.raises(ValueError):
        QuantityCriterionEvaluation(criterion, requirement, status, observation)


def test_justification_criterion_rejects_evidence_and_invalid_status() -> None:
    with pytest.raises(ValueError):
        QuantityCriterionEvaluation(
            QuantityStructuralCriterion.UNCERTAINTY_JUSTIFICATION_PRESENT,
            PresenceRequirement.REQUIRED,
            EvaluationStatus.DEFERRED,
            _observation(),
        )
    with pytest.raises(ValueError):
        QuantityCriterionEvaluation(
            QuantityStructuralCriterion.UNCERTAINTY_JUSTIFICATION_PRESENT,
            PresenceRequirement.REQUIRED,
            EvaluationStatus.SATISFIED,
        )


def test_complete_observation_with_required_justification() -> None:
    result = _evaluate(
        "g = (9,7 ± 0,4) m·s⁻²",
        justification=PresenceRequirement.REQUIRED,
    )
    assert [item.status for item in result.criteria] == [
        EvaluationStatus.SATISFIED,
        EvaluationStatus.SATISFIED,
        EvaluationStatus.SATISFIED,
        EvaluationStatus.DEFERRED,
    ]
    assert result.failures == ()
    assert result.required_deferred == (result.criteria[3],)
    assert not result.satisfied
    assert not result.is_complete
    assert not result.is_required_complete


def test_complete_observation_with_ignored_justification_is_satisfied() -> None:
    result = _evaluate("g = (9,7 ± 0,4) m·s⁻²")
    assert result.criteria[3].status is EvaluationStatus.NOT_APPLICABLE
    assert result.satisfied
    assert result.is_complete
    assert result.is_required_complete


@pytest.mark.parametrize(
    ("text", "failed", "satisfied"),
    [
        (
            "g = 9,7 ± 0,4",
            QuantityStructuralCriterion.UNIT_PRESENT,
            QuantityStructuralCriterion.UNCERTAINTY_PRESENT,
        ),
        (
            "g = 9,7 m·s⁻²",
            QuantityStructuralCriterion.UNCERTAINTY_PRESENT,
            QuantityStructuralCriterion.UNIT_PRESENT,
        ),
    ],
)
def test_required_component_presence(
    text: str,
    failed: QuantityStructuralCriterion,
    satisfied: QuantityStructuralCriterion,
) -> None:
    result = _evaluate(text)
    assert result.get(failed).status is EvaluationStatus.UNSATISFIED  # type: ignore[union-attr]
    assert result.get(satisfied).status is EvaluationStatus.SATISFIED  # type: ignore[union-attr]


def test_required_quantity_absent_makes_components_not_applicable() -> None:
    result = _evaluate("")
    assert result.get(QuantityStructuralCriterion.QUANTITY_PRESENT).status is EvaluationStatus.UNSATISFIED  # type: ignore[union-attr]
    assert all(
        item.status is EvaluationStatus.NOT_APPLICABLE
        for item in result.criteria[1:]
    )
    assert not result.satisfied


def test_optional_quantity_absent_is_satisfied() -> None:
    result = _evaluate("", required=False)
    assert result.criteria[0].status is EvaluationStatus.SATISFIED
    assert result.criteria[0].observed is False
    assert all(
        item.status is EvaluationStatus.NOT_APPLICABLE
        for item in result.criteria[1:]
    )
    assert result.satisfied


@pytest.mark.parametrize(
    ("criterion", "requirement", "text", "observed"),
    [
        (
            QuantityStructuralCriterion.UNIT_PRESENT,
            PresenceRequirement.OPTIONAL,
            "g=9",
            False,
        ),
        (
            QuantityStructuralCriterion.UNIT_PRESENT,
            PresenceRequirement.OPTIONAL,
            "g=9 m·s⁻²",
            True,
        ),
        (
            QuantityStructuralCriterion.UNCERTAINTY_PRESENT,
            PresenceRequirement.OPTIONAL,
            "g=9",
            False,
        ),
    ],
)
def test_optional_component_is_satisfied_even_when_absent(
    criterion: QuantityStructuralCriterion,
    requirement: PresenceRequirement,
    text: str,
    observed: bool,
) -> None:
    kwargs = {"unit": PresenceRequirement.REQUIRED, "uncertainty": PresenceRequirement.REQUIRED}
    kwargs["unit" if criterion is QuantityStructuralCriterion.UNIT_PRESENT else "uncertainty"] = requirement
    result = _evaluate(text, **kwargs)
    evaluation = result.get(criterion)
    assert evaluation is not None
    assert evaluation.status is EvaluationStatus.SATISFIED
    assert evaluation.observed is observed


@pytest.mark.parametrize(
    "criterion",
    [
        QuantityStructuralCriterion.UNIT_PRESENT,
        QuantityStructuralCriterion.UNCERTAINTY_PRESENT,
    ],
)
def test_ignored_component_has_no_observation(
    criterion: QuantityStructuralCriterion,
) -> None:
    kwargs = {"unit": PresenceRequirement.REQUIRED, "uncertainty": PresenceRequirement.REQUIRED}
    kwargs["unit" if criterion is QuantityStructuralCriterion.UNIT_PRESENT else "uncertainty"] = PresenceRequirement.IGNORE
    result = _evaluate("g=(9 ± 1) m·s⁻²", **kwargs)
    evaluation = result.get(criterion)
    assert evaluation is not None
    assert evaluation.status is EvaluationStatus.NOT_APPLICABLE
    assert evaluation.observation is None
    assert evaluation.observed is None


def test_optional_justification_is_deferred_but_does_not_fail_satisfaction() -> None:
    result = _evaluate(
        "g=(9 ± 1) m·s⁻²",
        justification=PresenceRequirement.OPTIONAL,
    )
    assert result.deferred == (result.criteria[3],)
    assert result.required_deferred == ()
    assert not result.is_complete
    assert result.is_required_complete
    assert result.satisfied


def test_selection_maximizes_required_components() -> None:
    result = _evaluate("g=9 m·s⁻² puis g=10 ± 1 m·s⁻²")
    assert result.selected_observation is result.detection.observations[1]


def test_selection_maximizes_optional_components_after_required() -> None:
    result = _evaluate(
        "g=9 puis g=10 ± 1",
        unit=PresenceRequirement.IGNORE,
        uncertainty=PresenceRequirement.OPTIONAL,
    )
    assert result.selected_observation is result.detection.observations[1]


def test_equal_quality_is_tied_by_first_position() -> None:
    result = _evaluate("g=9 m·s⁻² puis g=10 m·s⁻²")
    assert result.selected_observation is result.detection.observations[0]


def test_complementary_observations_are_not_merged() -> None:
    result = _evaluate("g=9 m·s⁻² puis g=10 ± 1")
    statuses = {
        item.criterion: item.status
        for item in result.criteria
    }
    assert EvaluationStatus.UNSATISFIED in (
        statuses[QuantityStructuralCriterion.UNIT_PRESENT],
        statuses[QuantityStructuralCriterion.UNCERTAINTY_PRESENT],
    )


def test_criteria_collection_is_converted_to_tuple() -> None:
    result = _evaluate("g=9 m·s⁻²")
    rebuilt = QuantityStructuralEvaluation(
        result.expectation_set,
        result.detection,
        result.selected_observation,
        list(result.criteria),  # type: ignore[arg-type]
    )
    assert isinstance(rebuilt.criteria, tuple)


def test_evaluation_rejects_non_criterion_items() -> None:
    result = _evaluate("g=9 m·s⁻²")
    with pytest.raises(TypeError):
        QuantityStructuralEvaluation(
            result.expectation_set,
            result.detection,
            result.selected_observation,
            [*result.criteria[:3], object()],  # type: ignore[list-item]
        )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reordered"])
def test_evaluation_requires_exact_ordered_criteria(mutation: str) -> None:
    result = _evaluate("g=9 m·s⁻²")
    criteria = list(result.criteria)
    if mutation == "missing":
        criteria.pop()
    elif mutation == "duplicate":
        criteria[-1] = criteria[0]
    else:
        criteria[0], criteria[1] = criteria[1], criteria[0]
    with pytest.raises(ValueError):
        QuantityStructuralEvaluation(
            result.expectation_set,
            result.detection,
            result.selected_observation,
            criteria,  # type: ignore[arg-type]
        )


def test_detection_must_belong_to_expectation_set() -> None:
    expectation, expectation_set = _context()
    foreign = ExpectedQuantity(
        "other", "x", canonical_unit="m", uncertainty_requirement=PresenceRequirement.IGNORE
    )
    detection = QuantityDetection(foreign)
    with pytest.raises(ValueError):
        QuantityStructuralEvaluator().evaluate(detection, expectation_set)


def test_equal_production_id_with_different_expectation_is_rejected() -> None:
    _, expectation_set = _context()
    different = ExpectedQuantity(
        "gravity_dynamic",
        "G",
        canonical_unit="m·s⁻²",
        uncertainty_requirement=PresenceRequirement.REQUIRED,
    )
    with pytest.raises(ValueError):
        evaluate_quantity_structure(QuantityDetection(different), expectation_set)


def test_selected_observation_must_come_from_detection() -> None:
    result = _evaluate("g=9 m·s⁻²")
    foreign = _observation(start=100)
    with pytest.raises(ValueError):
        QuantityStructuralEvaluation(
            result.expectation_set,
            result.detection,
            foreign,
            result.criteria,
        )


def test_get_unknown_value_returns_none() -> None:
    result = _evaluate("g=9 m·s⁻²")
    assert result.get("unknown") is None  # type: ignore[arg-type]


def test_evaluator_does_not_mutate_inputs_and_is_deterministic() -> None:
    expectation, expectation_set = _context()
    detection = extract_expected_quantity("g=(9 ± 1) m·s⁻²", expectation)
    before = (expectation_set, detection)
    first = evaluate_quantity_structure(detection, expectation_set)
    second = evaluate_quantity_structure(detection, expectation_set)
    assert first == second
    assert before == (expectation_set, detection)


def test_evaluation_produces_no_fact_diagnostic_or_score() -> None:
    result = _evaluate("g=9 m·s⁻²")
    assert not hasattr(result, "fact")
    assert not hasattr(result, "diagnostic")
    assert not hasattr(result, "score")
