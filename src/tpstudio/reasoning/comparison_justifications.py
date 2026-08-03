"""Literal extraction of declared comparison justification elements."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from tpstudio.expectations.comparison_justifications import (
    ComparisonJustificationElementKind, ComparisonJustificationRequirement,
    ExpectedComparisonJustification, ExpectedComparisonJustificationElement,
)


@dataclass(frozen=True, slots=True)
class ComparisonJustificationObservation:
    expectation: ExpectedComparisonJustification
    element: ExpectedComparisonJustificationElement
    phrase: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if type(self.expectation) is not ExpectedComparisonJustification: raise TypeError("L'attente est invalide.")
        if type(self.element) is not ExpectedComparisonJustificationElement: raise TypeError("L'élément est invalide.")
        if not any(self.element is item for item in self.expectation.elements): raise ValueError("L'élément est étranger.")
        if self.phrase not in self.element.phrases: raise ValueError("La phrase n'est pas déclarée.")
        if type(self.start) is not int or type(self.end) is not int: raise TypeError("Les offsets doivent être des entiers non booléens.")
        if not 0 <= self.start < self.end: raise ValueError("Les offsets sont invalides.")

    @property
    def comparison_id(self): return self.expectation.comparison_id
    @property
    def element_id(self): return self.element.element_id
    @property
    def kind(self): return self.element.kind
    @property
    def requirement(self): return self.element.requirement
    @property
    def alternative_group(self): return self.element.alternative_group


def _order_key(expectation, observation):
    element_order = next(index for index, item in enumerate(expectation.elements) if item is observation.element)
    phrase_order = observation.element.phrases.index(observation.phrase)
    return observation.start, observation.end, element_order, phrase_order


@dataclass(frozen=True, slots=True)
class ComparisonJustificationDetection:
    expectation: ExpectedComparisonJustification
    observations: tuple[ComparisonJustificationObservation, ...]

    def __post_init__(self) -> None:
        if type(self.expectation) is not ExpectedComparisonJustification: raise TypeError("L'attente est invalide.")
        if isinstance(self.observations, (str, bytes)): raise TypeError("Les observations doivent former une collection.")
        observations = tuple(self.observations)
        if any(type(item) is not ComparisonJustificationObservation for item in observations): raise TypeError("Une observation est invalide.")
        if any(item.expectation is not self.expectation for item in observations): raise ValueError("Une observation est étrangère.")
        keys = tuple(_order_key(self.expectation, item) for item in observations)
        if keys != tuple(sorted(keys)) or any(a >= b for a, b in zip(keys, keys[1:])): raise ValueError("L'ordre des observations est invalide.")
        if len(observations) != len(set(observations)): raise ValueError("Une observation est dupliquée.")
        object.__setattr__(self, "observations", observations)

    def __iter__(self) -> Iterator[ComparisonJustificationObservation]: return iter(self.observations)
    def __len__(self): return len(self.observations)
    def for_element(self, element_id): return tuple(item for item in self.observations if item.element_id == element_id)
    def for_kind(self, kind):
        if type(kind) is not ComparisonJustificationElementKind: raise TypeError("Le kind est invalide.")
        return tuple(item for item in self.observations if item.kind is kind)
    @property
    def observed_element_ids(self): return tuple(dict.fromkeys(item.element_id for item in self.observations))
    @property
    def observed_kinds(self): return tuple(dict.fromkeys(item.kind for item in self.observations))
    @property
    def has_observations(self): return bool(self.observations)
    def is_element_observed(self, element_id): return bool(self.for_element(element_id))


class LiteralComparisonJustificationExtractor:
    def extract(self, text, expectation):
        if not isinstance(text, str): raise TypeError("Le texte doit être une chaîne.")
        if type(expectation) is not ExpectedComparisonJustification: raise TypeError("L'attente est invalide.")
        matches = []
        for element_order, element in enumerate(expectation.elements):
            for phrase_order, phrase in enumerate(element.phrases):
                start = text.find(phrase)
                while start != -1:
                    matches.append((start, -len(phrase), element_order, phrase_order, element, phrase))
                    start = text.find(phrase, start + 1)
        matches.sort(key=lambda item: (item[0], item[2], item[1], item[3]))
        selected = {}
        for match in matches:
            selected.setdefault((match[0], match[2]), match)
        observations = tuple(ComparisonJustificationObservation(expectation, element, phrase, start, start + len(phrase)) for start, _, _, _, element, phrase in selected.values())
        observations = tuple(sorted(observations, key=lambda item: _order_key(expectation, item)))
        return ComparisonJustificationDetection(expectation, observations)


def extract_comparison_justification(text, expectation):
    """Delegate to the literal justification extractor."""
    return LiteralComparisonJustificationExtractor().extract(text, expectation)
