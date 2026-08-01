from dataclasses import FrozenInstanceError, fields
import inspect

import pytest

import tpstudio.expectations.quantities as quantity_models
from tpstudio.expectations import (
    EvaluationBasis,
    ExpectedQuantity,
    PresenceRequirement,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
)


def _production(
    identifier: str,
    kind: ScientificProductionKind = ScientificProductionKind.QUANTITY,
    *,
    depends_on: tuple[str, ...] = (),
) -> ScientificProductionSpec:
    return ScientificProductionSpec(
        identifier,
        f"Production {identifier}",
        kind,
        (EvaluationBasis.SUBMISSION_DERIVED,),
        depends_on=depends_on,
    )


def _plan() -> ScientificProductionPlan:
    return ScientificProductionPlan(
        "pendulum",
        "Pendulum",
        (
            _production("period_plot", ScientificProductionKind.PLOT),
            _production("gravity_dynamic", depends_on=("period_plot",)),
            _production("gravity_static"),
            _production(
                "gravity_comparison",
                ScientificProductionKind.COMPARISON,
                depends_on=("gravity_dynamic", "gravity_static"),
            ),
        ),
    )


def _quantity(production_id: str) -> ExpectedQuantity:
    return ExpectedQuantity(
        production_id,
        "g",
        canonical_unit="m·s⁻²",
        uncertainty_requirement=PresenceRequirement.REQUIRED,
    )


def test_presence_requirement_values_are_stable() -> None:
    assert tuple(item.value for item in PresenceRequirement) == (
        "ignore",
        "optional",
        "required",
    )


def test_expected_quantity_is_immutable_and_converts_collections_to_tuples() -> None:
    quantity = ExpectedQuantity(
        "gravity_dynamic",
        "g",
        accepted_symbols=["g_exp"],  # type: ignore[arg-type]
        canonical_unit="m·s⁻²",
        accepted_units=["m.s^-2"],  # type: ignore[arg-type]
    )

    assert quantity.accepted_symbols == ("g_exp",)
    assert quantity.accepted_units == ("m.s^-2",)
    with pytest.raises(FrozenInstanceError):
        quantity.canonical_symbol = "G"  # type: ignore[misc]


def test_symbols_put_canonical_first_and_deduplicate_stably() -> None:
    quantity = ExpectedQuantity(
        "gravity",
        "g",
        accepted_symbols=("g_exp", "g", "g_exp", "g_mes"),
        canonical_unit="m/s²",
    )

    assert quantity.accepted_symbols == ("g_exp", "g", "g_mes")
    assert quantity.symbols == ("g", "g_exp", "g_mes")


def test_units_put_canonical_first_and_deduplicate_stably() -> None:
    quantity = ExpectedQuantity(
        "gravity",
        "g",
        canonical_unit="m·s⁻²",
        accepted_units=("m.s^-2", "m·s⁻²", "m/s²", "m.s^-2"),
    )

    assert quantity.accepted_units == ("m.s^-2", "m·s⁻²", "m/s²")
    assert quantity.units == ("m·s⁻²", "m.s^-2", "m/s²")


def test_significant_spaces_and_description_are_preserved_exactly() -> None:
    quantity = ExpectedQuantity(
        "  gravity  ",
        "  g  ",
        accepted_symbols=(" g_exp ",),
        canonical_unit=" m·s⁻² ",
        accepted_units=(" m/s² ",),
        description="  valeur issue du poste  ",
    )

    assert quantity.production_id == "  gravity  "
    assert quantity.canonical_symbol == "  g  "
    assert quantity.symbols == ("  g  ", " g_exp ")
    assert quantity.units == (" m·s⁻² ", " m/s² ")
    assert quantity.description == "  valeur issue du poste  "


@pytest.mark.parametrize("production_id", ("", "   "))
def test_blank_production_id_is_rejected(production_id: str) -> None:
    with pytest.raises(ValueError, match="production_id"):
        ExpectedQuantity(production_id, "g", canonical_unit="m/s²")


@pytest.mark.parametrize("symbol", ("", "   "))
def test_blank_canonical_symbol_is_rejected(symbol: str) -> None:
    with pytest.raises(ValueError, match="canonical_symbol"):
        ExpectedQuantity("gravity", symbol, canonical_unit="m/s²")


def test_blank_accepted_symbol_is_rejected() -> None:
    with pytest.raises(ValueError, match="symbole accepté"):
        ExpectedQuantity(
            "gravity",
            "g",
            accepted_symbols=("  ",),
            canonical_unit="m/s²",
        )


@pytest.mark.parametrize("unit", ("", "   "))
def test_blank_canonical_unit_is_rejected(unit: str) -> None:
    with pytest.raises(ValueError, match="canonical_unit"):
        ExpectedQuantity("gravity", "g", canonical_unit=unit)


def test_blank_accepted_unit_is_rejected() -> None:
    with pytest.raises(ValueError, match="unité acceptée"):
        ExpectedQuantity(
            "gravity",
            "g",
            canonical_unit="m/s²",
            accepted_units=(" ",),
        )


def test_required_unit_without_canonical_unit_is_rejected() -> None:
    with pytest.raises(ValueError, match="unité obligatoire"):
        ExpectedQuantity("gravity", "g")


def test_accepted_units_without_canonical_unit_are_rejected() -> None:
    with pytest.raises(ValueError, match="unités acceptées"):
        ExpectedQuantity(
            "gravity",
            "g",
            accepted_units=("m/s²",),
            unit_requirement=PresenceRequirement.OPTIONAL,
        )


def test_ignored_unit_may_still_be_documented() -> None:
    documented = ExpectedQuantity(
        "gravity",
        "g",
        canonical_unit="m/s²",
        unit_requirement=PresenceRequirement.IGNORE,
    )
    undocumented = ExpectedQuantity(
        "ratio",
        "r",
        canonical_unit=None,
        unit_requirement=PresenceRequirement.IGNORE,
    )

    assert documented.units == ("m/s²",)
    assert undocumented.units == ()


def test_required_justification_needs_required_uncertainty() -> None:
    with pytest.raises(ValueError, match="incertitude obligatoire"):
        ExpectedQuantity(
            "gravity",
            "g",
            canonical_unit="m/s²",
            uncertainty_requirement=PresenceRequirement.OPTIONAL,
            uncertainty_justification_requirement=PresenceRequirement.REQUIRED,
        )


def test_optional_justification_is_invalid_when_uncertainty_is_ignored() -> None:
    with pytest.raises(ValueError, match="incertitude contrôlée"):
        ExpectedQuantity(
            "gravity",
            "g",
            canonical_unit="m/s²",
            uncertainty_requirement=PresenceRequirement.IGNORE,
            uncertainty_justification_requirement=PresenceRequirement.OPTIONAL,
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "unit_requirement",
        "uncertainty_requirement",
        "uncertainty_justification_requirement",
    ),
)
def test_presence_requirements_must_use_the_enum(field_name: str) -> None:
    arguments = {field_name: "required"}

    with pytest.raises(TypeError, match="PresenceRequirement"):
        ExpectedQuantity(  # type: ignore[arg-type]
            "gravity", "g", canonical_unit="m/s²", **arguments
        )


def test_quantity_expectation_set_is_immutable_ordered_and_tuple_backed() -> None:
    dynamic = _quantity("gravity_dynamic")
    static = _quantity("gravity_static")
    quantity_set = QuantityExpectationSet(
        _plan(),
        [static, dynamic],  # type: ignore[arg-type]
    )

    assert quantity_set.quantities == (static, dynamic)
    assert tuple(quantity_set) == (static, dynamic)
    assert len(quantity_set) == 2
    with pytest.raises(FrozenInstanceError):
        quantity_set.quantities = ()  # type: ignore[misc]


def test_empty_or_duplicate_quantity_set_is_rejected() -> None:
    with pytest.raises(ValueError, match="ne peut pas être vide"):
        QuantityExpectationSet(_plan(), ())
    quantity = _quantity("gravity_dynamic")
    with pytest.raises(ValueError, match="doivent être uniques"):
        QuantityExpectationSet(_plan(), (quantity, quantity))


def test_unknown_or_non_quantity_production_is_rejected() -> None:
    with pytest.raises(ValueError, match="Production inconnue"):
        QuantityExpectationSet(_plan(), (_quantity("unknown"),))
    with pytest.raises(ValueError, match="QUANTITY"):
        QuantityExpectationSet(_plan(), (_quantity("period_plot"),))


def test_get_returns_known_quantity_or_none() -> None:
    quantity = _quantity("gravity_dynamic")
    quantity_set = QuantityExpectationSet(_plan(), (quantity,))

    assert quantity_set.get("gravity_dynamic") is quantity
    assert quantity_set.get("unknown") is None


def test_in_evaluation_order_is_induced_by_plan_and_ignores_other_productions() -> None:
    dynamic = _quantity("gravity_dynamic")
    static = _quantity("gravity_static")
    quantity_set = QuantityExpectationSet(_plan(), (static, dynamic))

    assert quantity_set.in_evaluation_order == (dynamic, static)
    assert quantity_set.quantities == (static, dynamic)


def test_model_contains_no_student_value_uncertainty_or_tolerance_fields() -> None:
    field_names = {field.name for field in fields(ExpectedQuantity)}

    assert "value" not in field_names
    assert "uncertainty" not in field_names
    assert "tolerance" not in field_names


def test_quantity_models_have_no_reasoning_or_external_dependency() -> None:
    source = inspect.getsource(quantity_models).lower()

    assert "tpstudio.reasoning" not in source
    assert "numpy" not in source
    assert "sympy" not in source
    assert "pint" not in source
    assert "matplotlib" not in source
    assert "openai" not in source
