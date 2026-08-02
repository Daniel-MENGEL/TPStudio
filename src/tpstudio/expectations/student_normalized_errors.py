"""Teacher-declared expectations for a student's normalized error."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

from .quantity_comparisons import QuantityComparisonExpectationSet


@dataclass(frozen=True, slots=True)
class ExpectedStudentNormalizedError:
    """Literal labels and explicit tolerance expected for one comparison."""

    comparison_id: str
    labels: tuple[str, ...]
    absolute_tolerance: Decimal
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.comparison_id, str):
            raise TypeError("L'identifiant de comparaison doit être une chaîne.")
        if not self.comparison_id.strip():
            raise ValueError("L'identifiant de comparaison ne peut pas être vide.")
        if isinstance(self.labels, (str, bytes)):
            raise TypeError("Les labels doivent former une collection ordonnée.")
        labels = tuple(self.labels)
        if not labels:
            raise ValueError("Au moins un label de En doit être déclaré.")
        if any(not isinstance(label, str) for label in labels):
            raise TypeError("Chaque label doit être une chaîne.")
        if any(not label.strip() for label in labels):
            raise ValueError("Un label de En ne peut pas être vide.")
        if len(labels) != len(set(labels)):
            raise ValueError("Les labels de En doivent être uniques.")
        object.__setattr__(self, "labels", labels)
        if type(self.absolute_tolerance) is not Decimal:
            raise TypeError("La tolérance doit être exactement un Decimal.")
        if not self.absolute_tolerance.is_finite():
            raise ValueError("La tolérance doit être finie.")
        if self.absolute_tolerance < 0:
            raise ValueError("La tolérance ne peut pas être négative.")
        if not isinstance(self.description, str):
            raise TypeError("La description doit être une chaîne.")


@dataclass(frozen=True, slots=True)
class StudentNormalizedErrorExpectationSet:
    """Ordered student-En expectations attached to A70a comparisons."""

    comparison_expectation_set: QuantityComparisonExpectationSet
    expectations: tuple[ExpectedStudentNormalizedError, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.comparison_expectation_set, QuantityComparisonExpectationSet):
            raise TypeError("Les comparaisons doivent former un QuantityComparisonExpectationSet.")
        expectations = tuple(self.expectations)
        if not expectations:
            raise ValueError("Au moins une attente de En étudiant est requise.")
        if any(not isinstance(item, ExpectedStudentNormalizedError) for item in expectations):
            raise TypeError("Chaque attente doit être un ExpectedStudentNormalizedError.")
        identifiers = tuple(item.comparison_id for item in expectations)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Les identifiants de comparaison doivent être uniques.")
        for identifier in identifiers:
            if self.comparison_expectation_set.get(identifier) is None:
                raise ValueError(f"Comparaison inconnue : {identifier!r}.")
        object.__setattr__(self, "expectations", expectations)

    def __iter__(self) -> Iterator[ExpectedStudentNormalizedError]:
        return iter(self.expectations)

    def __len__(self) -> int:
        return len(self.expectations)

    def get(self, comparison_id: str) -> ExpectedStudentNormalizedError | None:
        return next((item for item in self.expectations if item.comparison_id == comparison_id), None)

    @property
    def in_evaluation_order(self) -> tuple[ExpectedStudentNormalizedError, ...]:
        return tuple(
            expectation
            for comparison in self.comparison_expectation_set.in_evaluation_order
            if (expectation := self.get(comparison.production_id)) is not None
        )
