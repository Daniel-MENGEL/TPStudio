from dataclasses import FrozenInstanceError, replace

import pytest

from tpstudio.diagnostics import (
    QuantityDiagnostic,
    QuantityDiagnosticBuilder,
    QuantityDiagnosticCode,
    QuantityDiagnosticSet,
    QuantityDiagnosticSource,
    build_quantity_diagnostics,
)
from tpstudio.evaluation import (
    EvaluationStatus,
    QuantityStructuralCriterion,
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
from tpstudio.reasoning import extract_expected_quantity
from tpstudio.reasoning.diagnostics import Diagnostic as RuleDiagnostic


def _evaluations(
    text: str,
    *,
    production_required: bool = True,
    unit: PresenceRequirement = PresenceRequirement.REQUIRED,
    uncertainty: PresenceRequirement = PresenceRequirement.REQUIRED,
    justification: PresenceRequirement = PresenceRequirement.IGNORE,
    significant_digits: tuple[int, ...] | None = (1, 2),
    positive: bool = True,
    alignment: bool = True,
):
    production = ScientificProductionSpec(
        "gravity",
        "Valeur de g",
        ScientificProductionKind.QUANTITY,
        (EvaluationBasis.STRUCTURAL,),
        required=production_required,
    )
    plan = ScientificProductionPlan("pendulum", "Pendule", (production,))
    quantity = ExpectedQuantity(
        "gravity",
        "g",
        canonical_unit="m·s⁻²",
        unit_requirement=unit,
        uncertainty_requirement=uncertainty,
        uncertainty_justification_requirement=justification,
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
    uncertainty_set = UncertaintyQualityExpectationSet(
        quantity_set, (specification,)
    )
    quality = evaluate_quantity_uncertainty(structural, uncertainty_set)
    return structural, quality


def _build(text: str, **kwargs: object) -> QuantityDiagnosticSet:
    structural, quality = _evaluations(text, **kwargs)
    return build_quantity_diagnostics(structural, quality)


def test_enum_values() -> None:
    assert [item.value for item in QuantityDiagnosticSource] == [
        "structure", "uncertainty_quality"
    ]
    assert [item.value for item in QuantityDiagnosticCode] == [
        "quantity_missing",
        "unit_missing",
        "uncertainty_missing",
        "uncertainty_justification_deferred",
        "uncertainty_not_strictly_positive",
        "uncertainty_significant_digits_invalid",
        "uncertainty_decimal_place_mismatch",
    ]


@pytest.mark.parametrize(
    ("code", "source", "criterion", "status", "message_key"),
    [
        (
            QuantityDiagnosticCode.QUANTITY_MISSING,
            QuantityDiagnosticSource.STRUCTURE,
            QuantityStructuralCriterion.QUANTITY_PRESENT,
            EvaluationStatus.UNSATISFIED,
            "diagnostic.quantity.missing",
        ),
        (
            QuantityDiagnosticCode.UNIT_MISSING,
            QuantityDiagnosticSource.STRUCTURE,
            QuantityStructuralCriterion.UNIT_PRESENT,
            EvaluationStatus.UNSATISFIED,
            "diagnostic.quantity.unit_missing",
        ),
        (
            QuantityDiagnosticCode.UNCERTAINTY_MISSING,
            QuantityDiagnosticSource.STRUCTURE,
            QuantityStructuralCriterion.UNCERTAINTY_PRESENT,
            EvaluationStatus.UNSATISFIED,
            "diagnostic.quantity.uncertainty_missing",
        ),
        (
            QuantityDiagnosticCode.UNCERTAINTY_JUSTIFICATION_DEFERRED,
            QuantityDiagnosticSource.STRUCTURE,
            QuantityStructuralCriterion.UNCERTAINTY_JUSTIFICATION_PRESENT,
            EvaluationStatus.DEFERRED,
            "diagnostic.quantity.uncertainty_justification_deferred",
        ),
        (
            QuantityDiagnosticCode.UNCERTAINTY_NOT_STRICTLY_POSITIVE,
            QuantityDiagnosticSource.UNCERTAINTY_QUALITY,
            UncertaintyQualityCriterion.STRICTLY_POSITIVE,
            EvaluationStatus.UNSATISFIED,
            "diagnostic.quantity.uncertainty_not_strictly_positive",
        ),
        (
            QuantityDiagnosticCode.UNCERTAINTY_SIGNIFICANT_DIGITS_INVALID,
            QuantityDiagnosticSource.UNCERTAINTY_QUALITY,
            UncertaintyQualityCriterion.SIGNIFICANT_DIGITS,
            EvaluationStatus.UNSATISFIED,
            "diagnostic.quantity.uncertainty_significant_digits_invalid",
        ),
        (
            QuantityDiagnosticCode.UNCERTAINTY_DECIMAL_PLACE_MISMATCH,
            QuantityDiagnosticSource.UNCERTAINTY_QUALITY,
            UncertaintyQualityCriterion.DECIMAL_PLACE_ALIGNMENT,
            EvaluationStatus.UNSATISFIED,
            "diagnostic.quantity.uncertainty_decimal_place_mismatch",
        ),
    ],
)
def test_code_has_stable_derived_properties(
    code: QuantityDiagnosticCode,
    source: QuantityDiagnosticSource,
    criterion: QuantityStructuralCriterion | UncertaintyQualityCriterion,
    status: EvaluationStatus,
    message_key: str,
) -> None:
    diagnostic = (
        QuantityDiagnostic(code, "gravity")
        if code is QuantityDiagnosticCode.QUANTITY_MISSING
        else QuantityDiagnostic(code, "gravity", _evaluations("g=9 ± 1")[0].selected_observation)
    )
    assert diagnostic.source is source
    assert diagnostic.criterion is criterion
    assert diagnostic.status is status
    assert diagnostic.message_key == message_key


def test_diagnostic_and_set_are_immutable() -> None:
    result = _build("g=(9,70 ± 0,4) m·s⁻²")
    with pytest.raises(FrozenInstanceError):
        result.diagnostics = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.diagnostics[0].code = QuantityDiagnosticCode.UNIT_MISSING  # type: ignore[misc]


@pytest.mark.parametrize("production_id", ["", "   "])
def test_diagnostic_rejects_blank_production_id(production_id: str) -> None:
    with pytest.raises(ValueError):
        QuantityDiagnostic(QuantityDiagnosticCode.QUANTITY_MISSING, production_id)


def test_diagnostic_rejects_wrong_code_type() -> None:
    with pytest.raises(TypeError):
        QuantityDiagnostic("quantity_missing", "gravity")  # type: ignore[arg-type]


def test_diagnostic_rejects_observation_for_other_production() -> None:
    observation = _evaluations("g=9 ± 1")[0].selected_observation
    assert observation is not None
    with pytest.raises(ValueError):
        QuantityDiagnostic(
            QuantityDiagnosticCode.UNIT_MISSING, "other", observation
        )


def test_quantity_missing_requires_no_observation() -> None:
    observation = _evaluations("g=9 ± 1")[0].selected_observation
    with pytest.raises(ValueError):
        QuantityDiagnostic(
            QuantityDiagnosticCode.QUANTITY_MISSING, "gravity", observation
        )


@pytest.mark.parametrize(
    "code",
    [code for code in QuantityDiagnosticCode if code is not QuantityDiagnosticCode.QUANTITY_MISSING],
)
def test_other_codes_require_observation(code: QuantityDiagnosticCode) -> None:
    with pytest.raises(ValueError):
        QuantityDiagnostic(code, "gravity")


def test_no_diagnostic_when_everything_is_satisfied() -> None:
    result = _build("g=(9,7 ± 0,4) m·s⁻²")
    assert result.is_empty
    assert len(result) == 0
    assert not result.has_failures
    assert not result.has_deferred
    assert tuple(result) == ()


def test_required_quantity_missing() -> None:
    result = _build("")
    assert [item.code for item in result] == [
        QuantityDiagnosticCode.QUANTITY_MISSING
    ]
    assert result.diagnostics[0].observation is None
    assert result.failures == result.diagnostics


def test_optional_quantity_missing_has_no_diagnostic() -> None:
    assert _build("", production_required=False).is_empty


@pytest.mark.parametrize(
    ("text", "codes"),
    [
        ("g=9 ± 1", [QuantityDiagnosticCode.UNIT_MISSING]),
        ("g=9 m·s⁻²", [QuantityDiagnosticCode.UNCERTAINTY_MISSING]),
        (
            "g=9",
            [
                QuantityDiagnosticCode.UNIT_MISSING,
                QuantityDiagnosticCode.UNCERTAINTY_MISSING,
            ],
        ),
    ],
)
def test_structural_failures_are_translated_in_order(
    text: str, codes: list[QuantityDiagnosticCode]
) -> None:
    result = _build(text)
    assert [item.code for item in result] == codes
    assert all(item.observation is result.selected_observation for item in result)


def test_missing_uncertainty_is_not_penalized_twice() -> None:
    result = _build("g=9 m·s⁻²")
    assert [item.code for item in result] == [
        QuantityDiagnosticCode.UNCERTAINTY_MISSING
    ]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        (
            "g=(9 ± 0) m·s⁻²",
            QuantityDiagnosticCode.UNCERTAINTY_NOT_STRICTLY_POSITIVE,
        ),
        (
            "g=(9,700 ± 0,456) m·s⁻²",
            QuantityDiagnosticCode.UNCERTAINTY_SIGNIFICANT_DIGITS_INVALID,
        ),
        (
            "g=(9,70 ± 0,4) m·s⁻²",
            QuantityDiagnosticCode.UNCERTAINTY_DECIMAL_PLACE_MISMATCH,
        ),
    ],
)
def test_uncertainty_quality_failure_is_translated(
    text: str, code: QuantityDiagnosticCode
) -> None:
    result = _build(text)
    assert [item.code for item in result] == [code]
    assert result.diagnostics[0].source is QuantityDiagnosticSource.UNCERTAINTY_QUALITY


def test_multiple_quality_failures_follow_criterion_order() -> None:
    result = _build("g=(9,70 ± -0,456) m·s⁻²")
    assert [item.code for item in result] == [
        QuantityDiagnosticCode.UNCERTAINTY_NOT_STRICTLY_POSITIVE,
        QuantityDiagnosticCode.UNCERTAINTY_SIGNIFICANT_DIGITS_INVALID,
        QuantityDiagnosticCode.UNCERTAINTY_DECIMAL_PLACE_MISMATCH,
    ]


def test_required_deferred_justification_produces_contextual_diagnostic() -> None:
    result = _build(
        "g=(9,7 ± 0,4) m·s⁻²",
        justification=PresenceRequirement.REQUIRED,
    )
    assert [item.code for item in result] == [
        QuantityDiagnosticCode.UNCERTAINTY_JUSTIFICATION_DEFERRED
    ]
    assert result.diagnostics[0].observation is result.selected_observation
    assert result.failures == ()
    assert result.deferred == result.diagnostics
    assert not result.has_failures
    assert result.has_deferred


@pytest.mark.parametrize(
    "requirement",
    [PresenceRequirement.OPTIONAL, PresenceRequirement.IGNORE],
)
def test_non_required_justification_produces_no_diagnostic(
    requirement: PresenceRequirement,
) -> None:
    assert _build(
        "g=(9,7 ± 0,4) m·s⁻²", justification=requirement
    ).is_empty


def test_global_order_places_deferred_after_all_failures() -> None:
    result = _build(
        "g=(9,70 ± -0,456)",
        justification=PresenceRequirement.REQUIRED,
    )
    assert [item.code for item in result] == [
        QuantityDiagnosticCode.UNIT_MISSING,
        QuantityDiagnosticCode.UNCERTAINTY_NOT_STRICTLY_POSITIVE,
        QuantityDiagnosticCode.UNCERTAINTY_SIGNIFICANT_DIGITS_INVALID,
        QuantityDiagnosticCode.UNCERTAINTY_DECIMAL_PLACE_MISMATCH,
        QuantityDiagnosticCode.UNCERTAINTY_JUSTIFICATION_DEFERRED,
    ]


def test_builder_works_without_uncertainty_evaluation() -> None:
    structural, _ = _evaluations(
        "g=(9,70 ± -0,456)", justification=PresenceRequirement.REQUIRED
    )
    result = QuantityDiagnosticBuilder().build(structural)
    assert [item.code for item in result] == [
        QuantityDiagnosticCode.UNIT_MISSING,
        QuantityDiagnosticCode.UNCERTAINTY_JUSTIFICATION_DEFERRED,
    ]
    assert result.uncertainty_evaluation is None


def test_uncertainty_evaluation_must_share_structural_instance() -> None:
    structural, quality = _evaluations("g=(9,7 ± 0,4) m·s⁻²")
    equal_structural = replace(structural)
    assert equal_structural == structural and equal_structural is not structural
    with pytest.raises(ValueError):
        build_quantity_diagnostics(equal_structural, quality)


def test_set_converts_diagnostics_to_tuple() -> None:
    result = _build("g=9")
    rebuilt = QuantityDiagnosticSet(
        result.structural_evaluation,
        result.uncertainty_evaluation,
        list(result.diagnostics),  # type: ignore[arg-type]
    )
    assert isinstance(rebuilt.diagnostics, tuple)


def test_set_rejects_duplicate_missing_extra_and_wrong_diagnostics() -> None:
    result = _build("g=9")
    with pytest.raises(ValueError):
        QuantityDiagnosticSet(
            result.structural_evaluation,
            result.uncertainty_evaluation,
            (*result.diagnostics, result.diagnostics[0]),
        )
    with pytest.raises(ValueError):
        QuantityDiagnosticSet(
            result.structural_evaluation,
            result.uncertainty_evaluation,
            result.diagnostics[:-1],
        )
    extra = QuantityDiagnostic(
        QuantityDiagnosticCode.UNCERTAINTY_NOT_STRICTLY_POSITIVE,
        result.production_id,
        result.selected_observation,
    )
    with pytest.raises(ValueError):
        QuantityDiagnosticSet(
            result.structural_evaluation,
            result.uncertainty_evaluation,
            (*result.diagnostics, extra),
        )
    wrong = QuantityDiagnostic(
        QuantityDiagnosticCode.UNCERTAINTY_MISSING,
        result.production_id,
        result.selected_observation,
    )
    with pytest.raises(ValueError):
        QuantityDiagnosticSet(
            result.structural_evaluation,
            result.uncertainty_evaluation,
            (wrong, result.diagnostics[1]),
        )


def test_set_rejects_equal_copy_of_selected_observation() -> None:
    result = _build("g=9")
    observation = result.selected_observation
    assert observation is not None
    copied = replace(observation)
    diagnostics = tuple(replace(item, observation=copied) for item in result)
    with pytest.raises(ValueError):
        QuantityDiagnosticSet(
            result.structural_evaluation,
            result.uncertainty_evaluation,
            diagnostics,
        )


def test_get_known_and_unknown_code() -> None:
    result = _build("g=9")
    assert result.get(QuantityDiagnosticCode.UNIT_MISSING) is result.diagnostics[0]
    assert result.get(QuantityDiagnosticCode.QUANTITY_MISSING) is None


def test_builder_is_deterministic_and_does_not_mutate_evaluations() -> None:
    structural, quality = _evaluations("g=(9,70 ± -0,456)")
    before = (structural, quality)
    first = build_quantity_diagnostics(structural, quality)
    second = build_quantity_diagnostics(structural, quality)
    assert first == second
    assert before == (structural, quality)


def test_new_diagnostic_has_no_student_message_severity_fact_rule_or_score() -> None:
    diagnostic = _build("g=9").diagnostics[0]
    assert not isinstance(diagnostic, RuleDiagnostic)
    assert not hasattr(diagnostic, "message")
    assert not hasattr(diagnostic, "severity")
    assert not hasattr(diagnostic, "fact")
    assert not hasattr(diagnostic, "rule_id")
    assert not hasattr(diagnostic, "score")
