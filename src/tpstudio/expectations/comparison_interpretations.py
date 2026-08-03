"""Teacher-declared literal interpretations of quantity comparisons."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from .quantity_comparisons import QuantityComparisonExpectationSet


class ComparisonInterpretationKind(str, Enum):
    """Literal meaning explicitly attached to a declared phrase."""

    COHERENT = "coherent"
    INCOHERENT = "incoherent"
    STRONGLY_INCOHERENT = "strongly_incoherent"
    METHOD_LIMITATION = "method_limitation"


@dataclass(frozen=True, slots=True)
class ExpectedComparisonInterpretation:
    """Literal phrases accepted for one declared comparison."""

    comparison_id: str
    phrases: tuple[tuple[ComparisonInterpretationKind, str], ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.comparison_id, str):
            raise TypeError("L'identifiant de comparaison doit être une chaîne.")
        if not self.comparison_id.strip():
            raise ValueError("L'identifiant de comparaison ne peut pas être vide.")
        if isinstance(self.phrases, (str, bytes)):
            raise TypeError("Les phrases doivent former une collection ordonnée.")
        phrases = tuple(self.phrases)
        if not phrases:
            raise ValueError("Au moins une phrase d'interprétation est requise.")
        for entry in phrases:
            if type(entry) is not tuple or len(entry) != 2:
                raise TypeError("Chaque entrée doit être un tuple de longueur deux.")
            kind, phrase = entry
            if type(kind) is not ComparisonInterpretationKind:
                raise TypeError("Le type d'interprétation est invalide.")
            if not isinstance(phrase, str):
                raise TypeError("La phrase littérale doit être une chaîne.")
            if not phrase.strip():
                raise ValueError("Une phrase littérale ne peut pas être vide.")
        literals = tuple(phrase for _, phrase in phrases)
        if len(literals) != len(set(literals)):
            raise ValueError("Les phrases littérales doivent être uniques.")
        if not isinstance(self.description, str):
            raise TypeError("La description doit être une chaîne.")
        object.__setattr__(self, "phrases", phrases)


@dataclass(frozen=True, slots=True)
class ComparisonInterpretationExpectationSet:
    """Ordered interpretation expectations attached to A70a comparisons."""

    comparison_expectation_set: QuantityComparisonExpectationSet
    expectations: tuple[ExpectedComparisonInterpretation, ...]

    def __post_init__(self) -> None:
        if type(self.comparison_expectation_set) is not QuantityComparisonExpectationSet:
            raise TypeError("Les comparaisons doivent former exactement un jeu A70a.")
        if isinstance(self.expectations, (str, bytes)):
            raise TypeError("Les attentes doivent former une collection ordonnée.")
        expectations = tuple(self.expectations)
        if not expectations:
            raise ValueError("Au moins une attente d'interprétation est requise.")
        if any(type(item) is not ExpectedComparisonInterpretation for item in expectations):
            raise TypeError("Chaque attente doit être une ExpectedComparisonInterpretation.")
        identifiers = tuple(item.comparison_id for item in expectations)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Les identifiants de comparaison doivent être uniques.")
        for identifier in identifiers:
            if self.comparison_expectation_set.get(identifier) is None:
                raise ValueError(f"Comparaison inconnue : {identifier!r}.")
        object.__setattr__(self, "expectations", expectations)

    def __iter__(self) -> Iterator[ExpectedComparisonInterpretation]:
        return iter(self.expectations)

    def __len__(self) -> int:
        return len(self.expectations)

    def get(self, comparison_id: str) -> ExpectedComparisonInterpretation | None:
        return next((item for item in self.expectations if item.comparison_id == comparison_id), None)

    @property
    def in_evaluation_order(self) -> tuple[ExpectedComparisonInterpretation, ...]:
        return tuple(
            expectation
            for comparison in self.comparison_expectation_set.in_evaluation_order
            if (expectation := self.get(comparison.production_id)) is not None
        )
