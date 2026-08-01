from dataclasses import FrozenInstanceError

import pytest

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


def _quantity_set(*, ignored: bool = False) -> QuantityExpectationSet:
    comparison = ScientificProductionSpec(
        "comparison",
        "Comparaison",
        ScientificProductionKind.COMPARISON,
        (EvaluationBasis.CROSS_PRODUCTION,),
        depends_on=("dynamic", "static"),
    )
    dynamic = ScientificProductionSpec(
        "dynamic",
        "g dynamique",
        ScientificProductionKind.QUANTITY,
        (EvaluationBasis.STRUCTURAL,),
    )
    static = ScientificProductionSpec(
        "static",
        "g statique",
        ScientificProductionKind.QUANTITY,
        (EvaluationBasis.STRUCTURAL,),
    )
    plan = ScientificProductionPlan(
        "pendulum", "Pendule", (comparison, dynamic, static)
    )
    requirement = (
        PresenceRequirement.IGNORE if ignored else PresenceRequirement.REQUIRED
    )
    quantities = (
        ExpectedQuantity(
            "dynamic",
            "g_d",
            canonical_unit="m·s⁻²",
            uncertainty_requirement=requirement,
        ),
        ExpectedQuantity(
            "static",
            "g_s",
            canonical_unit="m·s⁻²",
            uncertainty_requirement=PresenceRequirement.OPTIONAL,
        ),
    )
    return QuantityExpectationSet(plan, quantities)


def test_spec_defaults_and_immutability() -> None:
    specification = UncertaintyQualitySpec("dynamic")
    assert specification.allowed_significant_digits == (1, 2)
    with pytest.raises(FrozenInstanceError):
        specification.production_id = "other"  # type: ignore[misc]


def test_expectation_set_is_immutable_and_converts_to_tuple() -> None:
    quantity_set = _quantity_set()
    specification = UncertaintyQualitySpec("dynamic")
    expectation_set = UncertaintyQualityExpectationSet(
        quantity_set, [specification]  # type: ignore[arg-type]
    )
    assert expectation_set.specifications == (specification,)
    with pytest.raises(FrozenInstanceError):
        expectation_set.specifications = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    "field",
    ["require_strictly_positive", "require_matching_decimal_place"],
)
@pytest.mark.parametrize("value", [1, 0, "yes", None])
def test_boolean_controls_require_exact_bool(field: str, value: object) -> None:
    with pytest.raises(TypeError):
        UncertaintyQualitySpec("dynamic", **{field: value})  # type: ignore[arg-type]


def test_significant_digits_are_converted_and_stably_deduplicated() -> None:
    specification = UncertaintyQualitySpec(
        "dynamic", allowed_significant_digits=[2, 1, 2, 3]  # type: ignore[arg-type]
    )
    assert specification.allowed_significant_digits == (2, 1, 3)


@pytest.mark.parametrize("digits", [(True,), (1.0,), ("1",)])
def test_significant_digits_reject_non_exact_integers(
    digits: tuple[object, ...],
) -> None:
    with pytest.raises(TypeError):
        UncertaintyQualitySpec(
            "dynamic", allowed_significant_digits=digits  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("digits", [(), (0,), (-1,), (1, 0)])
def test_significant_digits_must_be_non_empty_and_positive(
    digits: tuple[int, ...],
) -> None:
    with pytest.raises(ValueError):
        UncertaintyQualitySpec("dynamic", allowed_significant_digits=digits)


def test_policy_must_enable_at_least_one_control() -> None:
    with pytest.raises(ValueError):
        UncertaintyQualitySpec(
            "dynamic",
            require_strictly_positive=False,
            allowed_significant_digits=None,
            require_matching_decimal_place=False,
        )


@pytest.mark.parametrize("production_id", ["", "   "])
def test_production_id_must_not_be_blank(production_id: str) -> None:
    with pytest.raises(ValueError):
        UncertaintyQualitySpec(production_id)


def test_description_is_preserved_exactly() -> None:
    specification = UncertaintyQualitySpec(" dynamic ", description="  libre  ")
    assert specification.production_id == " dynamic "
    assert specification.description == "  libre  "


def test_expectation_set_rejects_empty_and_duplicate_specs() -> None:
    quantity_set = _quantity_set()
    with pytest.raises(ValueError):
        UncertaintyQualityExpectationSet(quantity_set, ())
    specification = UncertaintyQualitySpec("dynamic")
    with pytest.raises(ValueError):
        UncertaintyQualityExpectationSet(
            quantity_set, (specification, specification)
        )


def test_expectation_set_rejects_unknown_quantity() -> None:
    with pytest.raises(ValueError):
        UncertaintyQualityExpectationSet(
            _quantity_set(), (UncertaintyQualitySpec("unknown"),)
        )


def test_expectation_set_rejects_ignored_uncertainty() -> None:
    with pytest.raises(ValueError):
        UncertaintyQualityExpectationSet(
            _quantity_set(ignored=True), (UncertaintyQualitySpec("dynamic"),)
        )


def test_lookup_iteration_and_length_preserve_declaration_order() -> None:
    specifications = (
        UncertaintyQualitySpec("static"),
        UncertaintyQualitySpec("dynamic"),
    )
    expectation_set = UncertaintyQualityExpectationSet(
        _quantity_set(), specifications
    )
    assert tuple(expectation_set) == specifications
    assert len(expectation_set) == 2
    assert expectation_set.get("static") is specifications[0]
    assert expectation_set.get("unknown") is None


def test_in_evaluation_order_follows_the_plan() -> None:
    static = UncertaintyQualitySpec("static")
    dynamic = UncertaintyQualitySpec("dynamic")
    expectation_set = UncertaintyQualityExpectationSet(
        _quantity_set(), (static, dynamic)
    )
    assert expectation_set.in_evaluation_order == (dynamic, static)
