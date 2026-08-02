"""Literal extraction of a student's normalized-error value."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

from tpstudio.expectations.student_normalized_errors import (
    ExpectedStudentNormalizedError,
)


_NUMBER = r"[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)(?:[eE][+-]?\d+)?"
_MAX_NUMERIC_COEFFICIENT_DIGITS = 1000
_MAX_NUMERIC_ABS_EXPONENT = 10000


def _safe_decimal(raw_value: str) -> Decimal | None:
    """Convert one bounded finite literal without trusting student text."""

    normalized = raw_value.replace(",", ".")
    coefficient_text, separator, exponent_text = normalized.lower().partition("e")
    coefficient_digits = sum(character.isdigit() for character in coefficient_text)
    if coefficient_digits > _MAX_NUMERIC_COEFFICIENT_DIGITS:
        return None
    if separator:
        unsigned_exponent = exponent_text.lstrip("+-").lstrip("0") or "0"
        if len(unsigned_exponent) > len(str(_MAX_NUMERIC_ABS_EXPONENT)):
            return None
        try:
            exponent = int(exponent_text)
        except (ValueError, OverflowError):
            return None
        if abs(exponent) > _MAX_NUMERIC_ABS_EXPONENT:
            return None
    try:
        value = Decimal(normalized)
    except (InvalidOperation, ValueError, OverflowError):
        return None
    if (
        not value.is_finite()
        or abs(value.as_tuple().exponent) > _MAX_NUMERIC_ABS_EXPONENT
        or abs(value.adjusted()) > _MAX_NUMERIC_ABS_EXPONENT
    ):
        return None
    return value


@dataclass(frozen=True, slots=True)
class StudentNormalizedErrorObservation:
    """One exact textual occurrence of a student's En value."""

    expectation: ExpectedStudentNormalizedError
    label: str
    operator: str
    raw_value: str
    value: Decimal
    start: int
    end: int
    value_start: int
    value_end: int

    def __post_init__(self) -> None:
        if not isinstance(self.expectation, ExpectedStudentNormalizedError):
            raise TypeError("L'attente doit être un ExpectedStudentNormalizedError.")
        if self.label not in self.expectation.labels:
            raise ValueError("Le label observé n'est pas déclaré.")
        if self.operator not in ("=", "≈"):
            raise ValueError("L'opérateur observé doit être '=' ou '≈'.")
        if not isinstance(self.raw_value, str) or not self.raw_value:
            raise ValueError("La valeur brute doit être une chaîne non vide.")
        if type(self.value) is not Decimal:
            raise TypeError("La valeur observée doit être exactement un Decimal.")
        if not self.value.is_finite():
            raise ValueError("La valeur observée doit être finie.")
        for offset in (self.start, self.end, self.value_start, self.value_end):
            if type(offset) is not int:
                raise TypeError("Les offsets doivent être des entiers non booléens.")
        if not (0 <= self.start <= self.value_start < self.value_end <= self.end):
            raise ValueError("Les offsets de l'observation sont incohérents.")
        try:
            parsed = Decimal(self.raw_value.replace(",", "."))
        except InvalidOperation as error:
            raise ValueError("La valeur brute n'est pas un Decimal valide.") from error
        if parsed != self.value:
            raise ValueError("La valeur Decimal ne correspond pas au texte brut.")


@dataclass(frozen=True, slots=True)
class StudentNormalizedErrorDetection:
    """All literal student-En observations for one expectation."""

    expectation: ExpectedStudentNormalizedError
    observations: tuple[StudentNormalizedErrorObservation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.expectation, ExpectedStudentNormalizedError):
            raise TypeError("L'attente doit être un ExpectedStudentNormalizedError.")
        observations = tuple(self.observations)
        if any(not isinstance(item, StudentNormalizedErrorObservation) for item in observations):
            raise TypeError("Chaque observation doit être un StudentNormalizedErrorObservation.")
        if any(item.expectation is not self.expectation for item in observations):
            raise ValueError("Chaque observation doit réutiliser exactement l'attente.")
        if any(left.start >= right.start for left, right in zip(observations, observations[1:])):
            raise ValueError("Les observations doivent suivre un ordre strictement croissant.")
        if len(observations) != len(set(observations)):
            raise ValueError("Une observation ne peut pas être dupliquée.")
        object.__setattr__(self, "observations", observations)

    @property
    def absent(self) -> bool:
        return not self.observations

    @property
    def unique(self) -> bool:
        return len(self.observations) == 1

    @property
    def ambiguous(self) -> bool:
        return len(self.observations) > 1

    @property
    def selected_observation(self) -> StudentNormalizedErrorObservation | None:
        return self.observations[0] if self.unique else None


class LiteralStudentNormalizedErrorExtractor:
    """Extract final literal En values without evaluating expressions."""

    def extract(
        self, text: str, expectation: ExpectedStudentNormalizedError
    ) -> StudentNormalizedErrorDetection:
        if not isinstance(text, str):
            raise TypeError("Le texte doit être une chaîne.")
        if not isinstance(expectation, ExpectedStudentNormalizedError):
            raise TypeError("L'attente doit être un ExpectedStudentNormalizedError.")
        by_span: dict[tuple[int, int], StudentNormalizedErrorObservation] = {}
        for label in expectation.labels:
            pattern = re.compile(
                rf"(?<!\w)(?P<label>{re.escape(label)})(?!\w)"
                rf"\s*(?P<operator>=|≈)\s*(?P<value>{_NUMBER})"
                rf"(?!\w|[.,](?=[\w.,]))(?!\()"
                rf"(?!\s*[*\/\-+^×·÷%√=−])"
            )
            for match in pattern.finditer(text):
                raw_value = match.group("value")
                value = _safe_decimal(raw_value)
                if value is None:
                    continue
                observation = StudentNormalizedErrorObservation(
                    expectation,
                    match.group("label"),
                    match.group("operator"),
                    raw_value,
                    value,
                    match.start(),
                    match.end(),
                    match.start("value"),
                    match.end("value"),
                )
                by_span.setdefault((match.start(), match.end()), observation)
        observations = tuple(sorted(by_span.values(), key=lambda item: item.start))
        return StudentNormalizedErrorDetection(expectation, observations)


def extract_student_normalized_error(
    text: str, expectation: ExpectedStudentNormalizedError
) -> StudentNormalizedErrorDetection:
    """Delegate to the literal student normalized-error extractor."""

    return LiteralStudentNormalizedErrorExtractor().extract(text, expectation)
