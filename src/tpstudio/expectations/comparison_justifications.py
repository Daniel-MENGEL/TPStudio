"""Teacher-declared literal elements of comparison justifications."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from .quantity_comparisons import QuantityComparisonExpectationSet


class ComparisonJustificationElementKind(str, Enum):
    NORMALIZED_ERROR_VALUE = "normalized_error_value"
    THRESHOLD_REFERENCE = "threshold_reference"
    COHERENCE_CLASSIFICATION = "coherence_classification"
    UNCERTAINTY_REFERENCE = "uncertainty_reference"
    METHOD_LIMITATION = "method_limitation"
    EXPERIMENTAL_BIAS = "experimental_bias"
    MEASUREMENT_LIMITATION = "measurement_limitation"


class ComparisonJustificationRequirement(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    ONE_OF_GROUP = "one_of_group"


@dataclass(frozen=True, slots=True)
class ExpectedComparisonJustificationElement:
    element_id: str
    kind: ComparisonJustificationElementKind
    requirement: ComparisonJustificationRequirement
    phrases: tuple[str, ...]
    alternative_group: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.element_id, str): raise TypeError("L'identifiant doit être une chaîne.")
        if not self.element_id.strip(): raise ValueError("L'identifiant ne peut pas être vide.")
        if type(self.kind) is not ComparisonJustificationElementKind: raise TypeError("Le kind est invalide.")
        if type(self.requirement) is not ComparisonJustificationRequirement: raise TypeError("L'exigence est invalide.")
        if isinstance(self.phrases, (str, bytes)): raise TypeError("Les phrases doivent former une collection.")
        phrases = tuple(self.phrases)
        if not phrases: raise ValueError("Au moins une phrase est requise.")
        if any(not isinstance(item, str) for item in phrases): raise TypeError("Chaque phrase doit être une chaîne.")
        if any(not item.strip() for item in phrases): raise ValueError("Une phrase ne peut pas être vide.")
        if len(phrases) != len(set(phrases)): raise ValueError("Les phrases doivent être uniques.")
        object.__setattr__(self, "phrases", phrases)
        if self.requirement is ComparisonJustificationRequirement.ONE_OF_GROUP:
            if not isinstance(self.alternative_group, str): raise TypeError("Le groupe alternatif doit être une chaîne.")
            if not self.alternative_group.strip(): raise ValueError("Le groupe alternatif ne peut pas être vide.")
        elif self.alternative_group is not None:
            raise ValueError("Seul ONE_OF_GROUP accepte un groupe alternatif.")
        if not isinstance(self.description, str): raise TypeError("La description doit être une chaîne.")


@dataclass(frozen=True, slots=True)
class ExpectedComparisonJustification:
    comparison_id: str
    elements: tuple[ExpectedComparisonJustificationElement, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.comparison_id, str): raise TypeError("L'identifiant doit être une chaîne.")
        if not self.comparison_id.strip(): raise ValueError("L'identifiant ne peut pas être vide.")
        if isinstance(self.elements, (str, bytes)): raise TypeError("Les éléments doivent former une collection.")
        elements = tuple(self.elements)
        if not elements: raise ValueError("Au moins un élément est requis.")
        if any(type(item) is not ExpectedComparisonJustificationElement for item in elements): raise TypeError("Chaque élément est invalide.")
        identifiers = tuple(item.element_id for item in elements)
        if len(identifiers) != len(set(identifiers)): raise ValueError("Les identifiants doivent être uniques.")
        phrases = tuple(phrase for item in elements for phrase in item.phrases)
        if len(phrases) != len(set(phrases)): raise ValueError("Les phrases doivent être globalement uniques.")
        groups = {item.alternative_group for item in elements if item.alternative_group is not None}
        for group in groups:
            members = tuple(item for item in elements if item.alternative_group == group)
            if len(members) < 2: raise ValueError("Chaque groupe alternatif exige au moins deux éléments.")
            if any(item.requirement is not ComparisonJustificationRequirement.ONE_OF_GROUP for item in members): raise ValueError("Un groupe ne contient que des éléments ONE_OF_GROUP.")
        object.__setattr__(self, "elements", elements)
        if not isinstance(self.description, str): raise TypeError("La description doit être une chaîne.")

    def get(self, element_id: str) -> ExpectedComparisonJustificationElement | None:
        return next((item for item in self.elements if item.element_id == element_id), None)


@dataclass(frozen=True, slots=True)
class ComparisonJustificationExpectationSet:
    comparison_expectation_set: QuantityComparisonExpectationSet
    expectations: tuple[ExpectedComparisonJustification, ...]

    def __post_init__(self) -> None:
        if type(self.comparison_expectation_set) is not QuantityComparisonExpectationSet: raise TypeError("Le jeu A70a est invalide.")
        if isinstance(self.expectations, (str, bytes)): raise TypeError("Les attentes doivent former une collection.")
        expectations = tuple(self.expectations)
        if any(type(item) is not ExpectedComparisonJustification for item in expectations): raise TypeError("Chaque attente est invalide.")
        identifiers = tuple(item.comparison_id for item in expectations)
        if len(identifiers) != len(set(identifiers)): raise ValueError("Les comparaisons doivent être uniques.")
        if any(self.comparison_expectation_set.get(item) is None for item in identifiers): raise ValueError("Une comparaison est inconnue.")
        object.__setattr__(self, "expectations", expectations)

    def __iter__(self) -> Iterator[ExpectedComparisonJustification]: return iter(self.expectations)
    def __len__(self) -> int: return len(self.expectations)
    def get(self, comparison_id: str): return next((item for item in self.expectations if item.comparison_id == comparison_id), None)
    @property
    def in_evaluation_order(self):
        return tuple(expectation for comparison in self.comparison_expectation_set.in_evaluation_order if (expectation := self.get(comparison.production_id)) is not None)
