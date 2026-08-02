from dataclasses import FrozenInstanceError, fields
from decimal import Decimal, getcontext

import pytest

from tpstudio.expectations import ExpectedStudentNormalizedError
from tpstudio.reasoning import (
    LiteralStudentNormalizedErrorExtractor,
    StudentNormalizedErrorDetection,
    StudentNormalizedErrorObservation,
    extract_student_normalized_error,
)


def _expectation(labels=("E_n", "En", "Eₙ")):
    return ExpectedStudentNormalizedError("comparison", labels, Decimal("0.1"))


@pytest.mark.parametrize(
    ("text", "label", "operator", "raw", "value"),
    [
        ("E_n = 2,3", "E_n", "=", "2,3", Decimal("2.3")),
        ("E_n = 2.3", "E_n", "=", "2.3", Decimal("2.3")),
        ("En≈2,30", "En", "≈", "2,30", Decimal("2.30")),
        ("Eₙ = +2.3", "Eₙ", "=", "+2.3", Decimal("2.3")),
        ("E_n = -2,3", "E_n", "=", "-2,3", Decimal("-2.3")),
        ("E_n = 2.3e0", "E_n", "=", "2.3e0", Decimal("2.3")),
        ("E_n = 2,3E+0", "E_n", "=", "2,3E+0", Decimal("2.3")),
    ],
)
def test_literal_grammar(text, label, operator, raw, value) -> None:
    detection = extract_student_normalized_error(text, _expectation())
    observation = detection.selected_observation
    assert observation is not None
    assert (observation.label, observation.operator, observation.raw_value, observation.value) == (label, operator, raw, value)
    assert text[observation.start:observation.end] == text
    assert text[observation.value_start:observation.value_end] == raw


@pytest.mark.parametrize(
    "text",
    [
        "en = 2.3",
        "XEn = 2.3",
        "EnX = 2.3",
        "En = abs(g1-g2)/sqrt(u1**2+u2**2)",
        "En = 2.3.4",
        "En = NaN",
        "En = Infinity",
        "En = 2*x",
        "En = 2 * x",
        "En = 2/3",
        "En = 2 / 3",
        "En = 2+3",
        "En = 2 - 3",
        "En = 2abc",
        "En = 2m",
        "En = 2..3",
        "éEn = 2",
        "Enβ = 2",
        "En = 2.e3",
        "En = 2.E+3",
        "En = 2,e3",
        "En = 2,E+3",
        "En = 2.e",
        "En = 2.abc",
        "En = 2×x",
        "En = 2 × x",
        "En = 2·x",
        "En = 2 · x",
        "En = 2÷3",
        "En = 2 ÷ 3",
        "En = 2%3",
        "En = 2 % 3",
        "En = 2(x)",
        "En = 2√3",
        "En = 2 √3",
        "En = 2 = 3",
        "En = 2 − 3",
    ],
)
def test_non_matching_or_malformed_forms_are_absent(text) -> None:
    assert extract_student_normalized_error(text, _expectation()).absent


def test_offsets_preserve_surrounding_spaces_and_source_is_not_stored() -> None:
    text = "Calcul :  E_n   =   2,20 puis conclusion"
    observation = extract_student_normalized_error(text, _expectation()).selected_observation
    assert observation is not None
    assert text[observation.start:observation.end] == "E_n   =   2,20"
    assert observation.raw_value == "2,20"
    assert all(field.name not in ("text", "source", "source_text") for field in fields(observation))


@pytest.mark.parametrize(
    ("text", "raw"),
    [
        ("En = 2.", "2"),
        ("En = 2. Puis conclusion.", "2"),
        ("En = 2,3.", "2,3"),
        ("En = 2,3, puis conclusion.", "2,3"),
        ("En = 2,3 ;", "2,3"),
        ("En = 2,3 puis conclusion", "2,3"),
        ("En = 2,3\nLa conclusion suit.", "2,3"),
        ("En = 2 (valeur arrondie).", "2"),
        ("En = 2,3 ; la méthode est peu fiable.", "2,3"),
    ],
)
def test_complete_value_allows_sentence_punctuation_and_following_text(text, raw) -> None:
    observation = extract_student_normalized_error(text, _expectation()).selected_observation
    assert observation is not None and observation.raw_value == raw
    assert text[observation.value_start:observation.value_end] == raw


@pytest.mark.parametrize(
    ("text", "raw", "value"),
    [
        ("En = 2e3", "2e3", Decimal("2e3")),
        ("En = 2E+3", "2E+3", Decimal("2E+3")),
        ("En = 2.3e-2", "2.3e-2", Decimal("2.3e-2")),
        ("En = 2,3E+2", "2,3E+2", Decimal("2.3E+2")),
    ],
)
def test_complete_scientific_notation_remains_valid(text, raw, value) -> None:
    observation = extract_student_normalized_error(text, _expectation()).selected_observation
    assert observation is not None
    assert observation.raw_value == raw and observation.value == value
    assert text[observation.value_start:observation.value_end] == raw


def test_pathological_exponent_is_ignored_without_losing_normal_occurrence() -> None:
    expectation = _expectation()
    before = getcontext().copy()
    detection = extract_student_normalized_error(
        "En = 1e999999999 puis E_n = 2,3", expectation
    )
    assert detection.unique
    assert detection.selected_observation is not None
    assert detection.selected_observation.value == Decimal("2.3")
    assert getcontext().prec == before.prec
    assert getcontext().rounding == before.rounding
    assert getcontext().traps == before.traps
    assert getcontext().flags == before.flags


def test_detection_absent_unique_ambiguous_and_order() -> None:
    expectation = _expectation()
    absent = extract_student_normalized_error("rien", expectation)
    unique = extract_student_normalized_error("En=1", expectation)
    ambiguous = extract_student_normalized_error("En=1 puis E_n=2", expectation)
    assert absent.absent and absent.selected_observation is None
    assert unique.unique and unique.selected_observation is unique.observations[0]
    assert ambiguous.ambiguous and ambiguous.selected_observation is None
    assert tuple(item.value for item in ambiguous.observations) == (Decimal("1"), Decimal("2"))


def test_models_are_immutable_and_validate_identity_and_offsets() -> None:
    expectation = _expectation()
    observation = extract_student_normalized_error("En=2", expectation).observations[0]
    detection = StudentNormalizedErrorDetection(expectation, [observation])
    with pytest.raises(FrozenInstanceError):
        observation.value = Decimal("3")
    with pytest.raises(FrozenInstanceError):
        detection.observations = ()
    foreign = _expectation()
    with pytest.raises(ValueError):
        StudentNormalizedErrorDetection(foreign, (observation,))
    with pytest.raises(ValueError):
        StudentNormalizedErrorObservation(expectation, "En", "=", "2", Decimal("2"), 2, 1, 0, 1)


def test_convenience_function_delegates_equivalently() -> None:
    expectation = _expectation()
    assert extract_student_normalized_error("En=2", expectation) == LiteralStudentNormalizedErrorExtractor().extract("En=2", expectation)
