"""Literal extraction of explicitly declared comparison interpretations."""

from __future__ import annotations

from dataclasses import dataclass

from tpstudio.expectations.comparison_interpretations import (
    ComparisonInterpretationKind,
    ExpectedComparisonInterpretation,
)


@dataclass(frozen=True, slots=True)
class ComparisonInterpretationObservation:
    expectation: ExpectedComparisonInterpretation
    kind: ComparisonInterpretationKind
    phrase: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if type(self.expectation) is not ExpectedComparisonInterpretation:
            raise TypeError("L'attente doit être exactement une attente d'interprétation.")
        if type(self.kind) is not ComparisonInterpretationKind:
            raise TypeError("Le type observé est invalide.")
        if (self.kind, self.phrase) not in self.expectation.phrases:
            raise ValueError("Le couple observé n'est pas déclaré.")
        if type(self.start) is not int or type(self.end) is not int:
            raise TypeError("Les offsets doivent être des entiers non booléens.")
        if not (0 <= self.start < self.end):
            raise ValueError("Les offsets de l'observation sont incohérents.")


@dataclass(frozen=True, slots=True)
class ComparisonInterpretationDetection:
    expectation: ExpectedComparisonInterpretation
    observations: tuple[ComparisonInterpretationObservation, ...]

    def __post_init__(self) -> None:
        if type(self.expectation) is not ExpectedComparisonInterpretation:
            raise TypeError("L'attente doit être exactement une attente d'interprétation.")
        if isinstance(self.observations, (str, bytes)):
            raise TypeError("Les observations doivent former une collection ordonnée.")
        observations = tuple(self.observations)
        if any(type(item) is not ComparisonInterpretationObservation for item in observations):
            raise TypeError("Chaque élément doit être une observation d'interprétation.")
        if any(item.expectation is not self.expectation for item in observations):
            raise ValueError("Chaque observation doit réutiliser l'attente par identité.")
        if any(left.start >= right.start for left, right in zip(observations, observations[1:])):
            raise ValueError("Les observations doivent suivre des offsets strictement croissants.")
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
    def selected_observation(self) -> ComparisonInterpretationObservation | None:
        return self.observations[0] if self.unique else None

    @property
    def observed_kinds(self) -> tuple[ComparisonInterpretationKind, ...]:
        return tuple(item.kind for item in self.observations)


class LiteralComparisonInterpretationExtractor:
    """Find exact, case-sensitive occurrences without normalization."""

    def extract(self, text: str, expectation: ExpectedComparisonInterpretation) -> ComparisonInterpretationDetection:
        if not isinstance(text, str):
            raise TypeError("Le texte doit être une chaîne.")
        if type(expectation) is not ExpectedComparisonInterpretation:
            raise TypeError("L'attente doit être exactement une attente d'interprétation.")
        matches: list[tuple[int, int, int, ComparisonInterpretationKind, str]] = []
        for declaration_order, (kind, phrase) in enumerate(expectation.phrases):
            start = text.find(phrase)
            while start != -1:
                matches.append((start, -len(phrase), declaration_order, kind, phrase))
                start = text.find(phrase, start + 1)
        matches.sort(key=lambda item: (item[0], item[1], item[2]))
        by_start: dict[int, tuple[int, int, int, ComparisonInterpretationKind, str]] = {}
        for match in matches:
            by_start.setdefault(match[0], match)
        observations = tuple(
            ComparisonInterpretationObservation(expectation, kind, phrase, start, start + len(phrase))
            for start, _, _, kind, phrase in by_start.values()
        )
        return ComparisonInterpretationDetection(expectation, observations)


def extract_comparison_interpretation(text: str, expectation: ExpectedComparisonInterpretation) -> ComparisonInterpretationDetection:
    """Delegate to the literal interpretation extractor."""

    return LiteralComparisonInterpretationExtractor().extract(text, expectation)
