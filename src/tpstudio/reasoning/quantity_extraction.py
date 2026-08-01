"""Literal observation of simple numerical quantities in student text."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

from tpstudio.expectations import ExpectedQuantity


UNCERTAINTY_MARKERS = ("±", "+/-", r"\pm")

_NUMBER_PATTERN = (
    r"[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)(?:[eE][+-]?\d+)?"
    r"(?![\d.,eE/(])"
)
_MARKER_PATTERN = r"(?:±|\+/-|\\pm)"
_PARENTHESIZED_BODY = re.compile(
    rf"\(\s*(?P<value>{_NUMBER_PATTERN})\s*"
    rf"(?P<marker>{_MARKER_PATTERN})\s*"
    rf"(?P<uncertainty>{_NUMBER_PATTERN})\s*\)"
)
_PLAIN_BODY = re.compile(
    rf"(?P<value>{_NUMBER_PATTERN})"
    rf"(?:\s*(?P<marker>{_MARKER_PATTERN})\s*"
    rf"(?P<uncertainty>{_NUMBER_PATTERN}))?"
)
_UNIT_SEPARATOR = re.compile(r"(?:\s|\\ )*")
_UNIT_BOUNDARY_CHARACTERS = frozenset(",;:!?)]}$")


def _decimal_from_text(text: str) -> Decimal:
    try:
        return Decimal(text.replace(",", "."))
    except InvalidOperation as error:
        raise ValueError(f"Écriture numérique invalide : {text!r}.") from error


def _has_unit_boundary(text: str, unit_end: int) -> bool:
    """Return whether a declared unit ends as a complete textual token."""

    if unit_end == len(text):
        return True
    following = text[unit_end]
    if following.isspace() or following in _UNIT_BOUNDARY_CHARACTERS:
        return True
    if following != ".":
        return False
    after_period = unit_end + 1
    return (
        after_period == len(text)
        or text[after_period].isspace()
        or text[after_period] in _UNIT_BOUNDARY_CHARACTERS
    )


@dataclass(frozen=True, slots=True)
class QuantityObservation:
    """One exact, structured quantity occurrence observed in student text."""

    production_id: str
    symbol: str
    value_text: str
    value: Decimal
    uncertainty_marker: str | None = None
    uncertainty_text: str | None = None
    uncertainty: Decimal | None = None
    unit: str | None = None
    matched_text: str = ""
    start: int = 0
    end: int = 0

    def __post_init__(self) -> None:
        if not self.production_id.strip():
            raise ValueError("L'identifiant de production ne peut pas être vide.")
        if not self.symbol.strip():
            raise ValueError("Le symbole observé ne peut pas être vide.")
        if not self.value_text.strip():
            raise ValueError("Le texte de la valeur ne peut pas être vide.")
        if not self.matched_text.strip():
            raise ValueError("Le fragment observé ne peut pas être vide.")
        if self.start < 0:
            raise ValueError("La position de début ne peut pas être négative.")
        if self.end <= self.start:
            raise ValueError("La position de fin doit suivre le début.")
        if self.end - self.start != len(self.matched_text):
            raise ValueError("Les positions ne correspondent pas au fragment observé.")
        if not isinstance(self.value, Decimal):
            raise TypeError("La valeur observée doit être une Decimal.")
        if self.value != _decimal_from_text(self.value_text):
            raise ValueError("La valeur Decimal ne correspond pas à value_text.")
        if self.unit is not None and not self.unit.strip():
            raise ValueError("L'unité observée ne peut pas être vide.")

        uncertainty_fields = (
            self.uncertainty_marker,
            self.uncertainty_text,
            self.uncertainty,
        )
        if self.uncertainty is not None and not isinstance(
            self.uncertainty, Decimal
        ):
            raise TypeError("L'incertitude observée doit être une Decimal.")
        defined_count = sum(field is not None for field in uncertainty_fields)
        if defined_count not in (0, 3):
            raise ValueError(
                "Les trois champs d'incertitude doivent être définis ensemble."
            )
        if defined_count == 3:
            if self.uncertainty_marker not in UNCERTAINTY_MARKERS:
                raise ValueError("Le marqueur d'incertitude n'est pas reconnu.")
            assert self.uncertainty_text is not None
            assert self.uncertainty is not None
            if not self.uncertainty_text.strip():
                raise ValueError("Le texte de l'incertitude ne peut pas être vide.")
            if self.uncertainty != _decimal_from_text(self.uncertainty_text):
                raise ValueError(
                    "La valeur Decimal ne correspond pas à uncertainty_text."
                )


@dataclass(frozen=True, slots=True)
class QuantityDetection:
    """All observations associated with one expected quantity."""

    expectation: ExpectedQuantity
    observations: tuple[QuantityObservation, ...] = ()

    def __post_init__(self) -> None:
        unique: dict[QuantityObservation, None] = {}
        for observation in self.observations:
            if observation.production_id != self.expectation.production_id:
                raise ValueError(
                    "Chaque observation doit référencer la production attendue."
                )
            if observation.symbol not in self.expectation.symbols:
                raise ValueError("Le symbole observé n'est pas déclaré.")
            if (
                observation.unit is not None
                and observation.unit not in self.expectation.units
            ):
                raise ValueError("L'unité observée n'est pas déclarée.")
            unique.setdefault(observation, None)
        object.__setattr__(
            self,
            "observations",
            tuple(sorted(unique, key=lambda item: (item.start, item.end))),
        )

    @property
    def production_id(self) -> str:
        return self.expectation.production_id

    @property
    def found(self) -> bool:
        return bool(self.observations)

    @property
    def first_observation(self) -> QuantityObservation | None:
        return self.observations[0] if self.observations else None


class LiteralQuantityExtractor:
    """Observe one expected quantity using a deliberately limited grammar."""

    def extract(
        self,
        text: str,
        expectation: ExpectedQuantity,
    ) -> QuantityDetection:
        observations: list[QuantityObservation] = []
        units_by_precedence = tuple(
            unit
            for _, unit in sorted(
                enumerate(expectation.units),
                key=lambda item: (-len(item[1]), item[0]),
            )
        )

        for symbol in expectation.symbols:
            assignment = re.compile(rf"(?<!\w){re.escape(symbol)}\s*=\s*")
            for assignment_match in assignment.finditer(text):
                body_start = assignment_match.end()
                body_match = _PARENTHESIZED_BODY.match(text, body_start)
                if body_match is None:
                    body_match = _PLAIN_BODY.match(text, body_start)
                if body_match is None:
                    continue

                value_text = body_match.group("value")
                marker = body_match.group("marker")
                uncertainty_text = body_match.group("uncertainty")
                end = body_match.end()
                unit: str | None = None

                separator = _UNIT_SEPARATOR.match(text, end)
                assert separator is not None
                unit_start = separator.end()
                for declared_unit in units_by_precedence:
                    unit_end = unit_start + len(declared_unit)
                    if text.startswith(
                        declared_unit, unit_start
                    ) and _has_unit_boundary(text, unit_end):
                        unit = declared_unit
                        end = unit_end
                        break

                start = assignment_match.start()
                matched_text = text[start:end]
                observations.append(
                    QuantityObservation(
                        production_id=expectation.production_id,
                        symbol=symbol,
                        value_text=value_text,
                        value=_decimal_from_text(value_text),
                        uncertainty_marker=marker,
                        uncertainty_text=uncertainty_text,
                        uncertainty=(
                            _decimal_from_text(uncertainty_text)
                            if uncertainty_text is not None
                            else None
                        ),
                        unit=unit,
                        matched_text=matched_text,
                        start=start,
                        end=end,
                    )
                )

        return QuantityDetection(expectation, tuple(observations))


def extract_expected_quantity(
    text: str,
    expectation: ExpectedQuantity,
) -> QuantityDetection:
    """Convenience wrapper around :class:`LiteralQuantityExtractor`."""

    return LiteralQuantityExtractor().extract(text, expectation)
