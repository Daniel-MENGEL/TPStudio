from dataclasses import FrozenInstanceError
from decimal import Decimal
import inspect

import pytest

import tpstudio.reasoning.quantity_extraction as quantity_extraction
from tpstudio.expectations import ExpectedQuantity, PresenceRequirement
from tpstudio.reasoning import (
    LiteralQuantityExtractor,
    QuantityDetection,
    QuantityObservation,
    extract_expected_quantity,
)


def _expectation(
    *,
    unit_requirement: PresenceRequirement = PresenceRequirement.REQUIRED,
    uncertainty_requirement: PresenceRequirement = PresenceRequirement.REQUIRED,
) -> ExpectedQuantity:
    return ExpectedQuantity(
        "gravity_dynamic",
        "g",
        accepted_symbols=("g_exp",),
        canonical_unit="m·s⁻²",
        accepted_units=("m.s^-2", "m/s²", r"\mathrm{m\,s^{-2}}"),
        unit_requirement=unit_requirement,
        uncertainty_requirement=uncertainty_requirement,
        uncertainty_justification_requirement=PresenceRequirement.IGNORE,
    )


def _observation(**overrides: object) -> QuantityObservation:
    arguments: dict[str, object] = {
        "production_id": "gravity_dynamic",
        "symbol": "g",
        "value_text": "9,7",
        "value": Decimal("9.7"),
        "unit": "m·s⁻²",
        "matched_text": "g = 9,7 m·s⁻²",
        "start": 0,
        "end": 13,
    }
    arguments.update(overrides)
    return QuantityObservation(**arguments)  # type: ignore[arg-type]


def test_observation_is_immutable_and_keeps_exact_text() -> None:
    observation = _observation()

    assert observation.value == Decimal("9.7")
    assert observation.matched_text == "g = 9,7 m·s⁻²"
    with pytest.raises(FrozenInstanceError):
        observation.symbol = "G"  # type: ignore[misc]


@pytest.mark.parametrize(
    "overrides",
    (
        {"production_id": " "},
        {"symbol": " "},
        {"value_text": " "},
        {"matched_text": " "},
        {"start": -1},
        {"end": 0},
        {"end": 12},
        {"value": Decimal("9.8")},
        {"unit": " "},
    ),
)
def test_observation_rejects_invalid_identity_text_offsets_or_value(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        _observation(**overrides)


@pytest.mark.parametrize("value", (9, 9.0, True))
def test_observation_requires_decimal_value(value: object) -> None:
    with pytest.raises(TypeError, match="Decimal"):
        _observation(value=value)


@pytest.mark.parametrize(
    "overrides",
    (
        {"uncertainty_marker": "±"},
        {"uncertainty_text": "0,4"},
        {"uncertainty": Decimal("0.4")},
        {
            "uncertainty_marker": "unknown",
            "uncertainty_text": "0,4",
            "uncertainty": Decimal("0.4"),
        },
        {
            "uncertainty_marker": "±",
            "uncertainty_text": " ",
            "uncertainty": Decimal("0.4"),
        },
        {
            "uncertainty_marker": "±",
            "uncertainty_text": "0,4",
            "uncertainty": Decimal("0.5"),
        },
    ),
)
def test_observation_rejects_partial_or_incoherent_uncertainty(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        _observation(**overrides)


@pytest.mark.parametrize("uncertainty", (1, 0.4))
def test_observation_requires_decimal_uncertainty(uncertainty: object) -> None:
    with pytest.raises(TypeError, match="Decimal"):
        _observation(
            uncertainty_marker="±",
            uncertainty_text="0,4",
            uncertainty=uncertainty,
        )


def test_detection_is_immutable_tuple_backed_deduplicated_and_sorted() -> None:
    later = _observation(start=20, end=33)
    earlier = _observation(start=0, end=13)
    detection = QuantityDetection(
        _expectation(),
        [later, earlier, earlier],  # type: ignore[arg-type]
    )

    assert detection.observations == (earlier, later)
    assert detection.production_id == "gravity_dynamic"
    assert detection.found
    assert detection.first_observation is earlier
    with pytest.raises(FrozenInstanceError):
        detection.observations = ()  # type: ignore[misc]


def test_empty_detection_is_valid() -> None:
    detection = QuantityDetection(_expectation())

    assert not detection.found
    assert detection.first_observation is None


def test_detection_validates_production_symbol_and_unit_before_deduplication() -> None:
    valid = _observation()
    with pytest.raises(ValueError, match="production"):
        QuantityDetection(
            _expectation(),
            (valid, _observation(production_id="other")),
        )
    with pytest.raises(ValueError, match="symbole"):
        QuantityDetection(_expectation(), (_observation(symbol="G"),))
    with pytest.raises(ValueError, match="unité"):
        QuantityDetection(_expectation(), (_observation(unit="km"),))


@pytest.mark.parametrize(
    ("value_text", "expected"),
    (
        ("9", Decimal("9")),
        ("9.7", Decimal("9.7")),
        ("9,7", Decimal("9.7")),
        ("+9.7", Decimal("9.7")),
        ("-0,25", Decimal("-0.25")),
        (".5", Decimal("0.5")),
        (",5", Decimal("0.5")),
        ("1.2e-3", Decimal("0.0012")),
        ("1,2E+4", Decimal("1.2E+4")),
    ),
)
def test_limited_numeric_grammar(value_text: str, expected: Decimal) -> None:
    detection = extract_expected_quantity(
        f"g={value_text}",
        _expectation(),
    )

    observation = detection.first_observation
    assert observation is not None
    assert observation.value_text == value_text
    assert observation.value == expected


def test_value_and_canonical_unit_are_observed() -> None:
    text = "Résultat : g = 9,7 m·s⁻²."

    observation = extract_expected_quantity(text, _expectation()).first_observation

    assert observation is not None
    assert observation.symbol == "g"
    assert observation.unit == "m·s⁻²"
    assert observation.matched_text == "g = 9,7 m·s⁻²"
    assert (observation.start, observation.end) == (11, 24)
    assert text[observation.start : observation.end] == observation.matched_text


@pytest.mark.parametrize(
    ("text", "marker", "uncertainty_text", "unit"),
    (
        ("g = 9,7 ± 0,4 m·s⁻²", "±", "0,4", "m·s⁻²"),
        ("g = 9.7 +/- 0.4 m.s^-2", "+/-", "0.4", "m.s^-2"),
        (r"g = 9.7 \pm 0.4 m/s²", r"\pm", "0.4", "m/s²"),
    ),
)
def test_three_uncertainty_markers_are_observed(
    text: str,
    marker: str,
    uncertainty_text: str,
    unit: str,
) -> None:
    observation = extract_expected_quantity(text, _expectation()).first_observation

    assert observation is not None
    assert observation.uncertainty_marker == marker
    assert observation.uncertainty_text == uncertainty_text
    assert observation.uncertainty == Decimal(uncertainty_text.replace(",", "."))
    assert observation.unit == unit


def test_parenthesized_value_and_uncertainty_are_observed() -> None:
    text = "g = (9,7 ± 0,4) m·s⁻²"

    observation = extract_expected_quantity(text, _expectation()).first_observation

    assert observation is not None
    assert observation.value == Decimal("9.7")
    assert observation.uncertainty == Decimal("0.4")
    assert observation.matched_text == text


def test_latex_spacing_and_declared_latex_unit_are_observed() -> None:
    text = r"$g = 9.7 \pm 0.4\ \mathrm{m\,s^{-2}}$"

    observation = extract_expected_quantity(text, _expectation()).first_observation

    assert observation is not None
    assert observation.unit == r"\mathrm{m\,s^{-2}}"
    assert observation.matched_text == text[1:-1]
    assert (observation.start, observation.end) == (1, len(text) - 1)


def test_accepted_symbol_is_observed_but_undeclared_or_wrong_case_is_not() -> None:
    expectation = _expectation()

    accepted = extract_expected_quantity("g_exp = 9,7 m/s²", expectation)
    undeclared = extract_expected_quantity("gravity = 9,7 m·s⁻²", expectation)
    wrong_case = extract_expected_quantity("G = 9,7 m·s⁻²", expectation)

    assert accepted.first_observation is not None
    assert accepted.first_observation.symbol == "g_exp"
    assert not undeclared.found
    assert not wrong_case.found


def test_short_symbol_is_not_found_inside_a_longer_identifier() -> None:
    expectation = ExpectedQuantity(
        "gravity",
        "g",
        canonical_unit=None,
        unit_requirement=PresenceRequirement.IGNORE,
    )

    assert not extract_expected_quantity("ag = 9,7", expectation).found
    assert not extract_expected_quantity("g_exp = 9,7", expectation).found


def test_longest_declared_unit_wins_at_the_same_position() -> None:
    expectation = ExpectedQuantity(
        "speed",
        "v",
        canonical_unit="m",
        accepted_units=("m/s", "m/s²"),
    )

    observation = extract_expected_quantity("v=2 m/s²", expectation).first_observation

    assert observation is not None
    assert observation.unit == "m/s²"


@pytest.mark.parametrize(
    ("declared_unit", "unknown_token"),
    (("m", "mol"), ("m", "m·s⁻¹"), ("m/s", "m/s²"), ("Hz", "Hz_extra")),
)
def test_declared_unit_is_not_recognized_as_a_longer_token_prefix(
    declared_unit: str,
    unknown_token: str,
) -> None:
    expectation = ExpectedQuantity(
        "quantity",
        "q",
        canonical_unit=declared_unit,
    )
    text = f"q = 2 {unknown_token}"

    observation = extract_expected_quantity(text, expectation).first_observation

    assert observation is not None
    assert observation.unit is None
    assert observation.matched_text == "q = 2"
    assert text[observation.start : observation.end] == "q = 2"


def test_exact_unit_followed_by_final_period_is_recognized() -> None:
    expectation = ExpectedQuantity("length", "L", canonical_unit="m")

    observation = extract_expected_quantity(
        "L = 2 m.", expectation
    ).first_observation

    assert observation is not None
    assert observation.unit == "m"
    assert observation.matched_text == "L = 2 m"


@pytest.mark.parametrize("punctuation", (",", ")"))
def test_exact_unit_followed_by_separator_or_closing_delimiter_is_recognized(
    punctuation: str,
) -> None:
    expectation = ExpectedQuantity("length", "L", canonical_unit="m")

    observation = extract_expected_quantity(
        f"L = 2 m{punctuation}", expectation
    ).first_observation

    assert observation is not None
    assert observation.unit == "m"
    assert observation.matched_text == "L = 2 m"


def test_unknown_or_absent_unit_leaves_observation_at_understood_value() -> None:
    unknown_text = "g = 9,7 km"
    unknown = extract_expected_quantity(unknown_text, _expectation()).first_observation
    absent = extract_expected_quantity("g = 9,7", _expectation()).first_observation

    assert unknown is not None
    assert unknown.unit is None
    assert unknown.matched_text == "g = 9,7"
    assert unknown_text[unknown.start : unknown.end] == unknown.matched_text
    assert absent is not None
    assert absent.unit is None


def test_negative_uncertainty_is_observed_without_judgment() -> None:
    observation = extract_expected_quantity(
        "g = 9,7 ± -0,4 m·s⁻²", _expectation()
    ).first_observation

    assert observation is not None
    assert observation.uncertainty_text == "-0,4"
    assert observation.uncertainty == Decimal("-0.4")


def test_multiple_occurrences_are_kept_in_text_order() -> None:
    text = "g = 9,7 m·s⁻² puis g = 9,8 m·s⁻²"

    detection = LiteralQuantityExtractor().extract(text, _expectation())

    assert [item.value for item in detection.observations] == [
        Decimal("9.7"),
        Decimal("9.8"),
    ]
    assert [item.start for item in detection.observations] == sorted(
        item.start for item in detection.observations
    )


def test_empty_text_produces_negative_detection() -> None:
    detection = extract_expected_quantity("", _expectation())

    assert not detection.found
    assert detection.observations == ()


@pytest.mark.parametrize(
    "text",
    ("g = 9,7(4) m·s⁻²", "g = 97/10 m·s⁻²", "g = 1,234.5 m·s⁻²"),
)
def test_unrecognized_numeric_notations_produce_no_observation(text: str) -> None:
    assert not extract_expected_quantity(text, _expectation()).found


def test_partially_understood_times_ten_notation_stops_before_unknown_suffix() -> None:
    text = "g = 9,7 × 10^0 m·s⁻²"

    observation = extract_expected_quantity(text, _expectation()).first_observation

    assert observation is not None
    assert observation.matched_text == "g = 9,7"
    assert observation.unit is None


@pytest.mark.parametrize(
    ("unit_requirement", "uncertainty_requirement"),
    (
        (PresenceRequirement.REQUIRED, PresenceRequirement.REQUIRED),
        (PresenceRequirement.OPTIONAL, PresenceRequirement.OPTIONAL),
        (PresenceRequirement.IGNORE, PresenceRequirement.IGNORE),
    ),
)
def test_presence_requirements_do_not_affect_extraction(
    unit_requirement: PresenceRequirement,
    uncertainty_requirement: PresenceRequirement,
) -> None:
    expectation = _expectation(
        unit_requirement=unit_requirement,
        uncertainty_requirement=uncertainty_requirement,
    )

    observation = extract_expected_quantity("g = 9,7", expectation).first_observation

    assert observation is not None
    assert observation.unit is None
    assert observation.uncertainty is None


def test_extractor_produces_no_fact_diagnostic_or_ai_dependency() -> None:
    source = inspect.getsource(quantity_extraction).lower()
    detection = extract_expected_quantity("g = 9,7", _expectation())

    assert isinstance(detection, QuantityDetection)
    assert "fact(" not in source
    assert "diagnostic(" not in source
    assert "openai" not in source
    assert "numpy" not in source
    assert "sympy" not in source
    assert "pint" not in source


def test_extractor_always_builds_decimal_values() -> None:
    observation = extract_expected_quantity(
        "g = 9,7 ± 0,4 m·s⁻²", _expectation()
    ).first_observation

    assert observation is not None
    assert isinstance(observation.value, Decimal)
    assert isinstance(observation.uncertainty, Decimal)
