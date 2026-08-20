"""Teacher-declared expectations for comparisons between quantities."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from .quantities import QuantityExpectationSet
from .scientific_productions import ScientificProductionKind, ScientificProductionPlan


class QuantityComparisonMethod(str, Enum):
    """Declared method for a future quantity comparison."""

    NORMALIZED_ERROR = "normalized_error"


class ComparisonPedagogicalContext(str, Enum):
    """Teacher-declared context for interpreting a future comparison."""

    OPEN = "open"
    COHERENCE_EXPECTED = "coherence_expected"
    INCOHERENCE_POSSIBLE = "incoherence_possible"
    METHOD_LIMITATION_EXPECTED = "method_limitation_expected"


@dataclass(frozen=True, slots=True)
class NormalizedErrorThresholds:
    """Objective thresholds declared for a future normalized error."""

    coherence_limit: Decimal = Decimal("2")
    strong_incoherence_limit: Decimal = Decimal("4")

    def __post_init__(self) -> None:
        values = (self.coherence_limit, self.strong_incoherence_limit)
        if any(type(value) is not Decimal for value in values):
            raise TypeError("Les seuils doivent être exactement des Decimal.")
        if any(not value.is_finite() for value in values):
            raise ValueError("Les seuils doivent être finis.")
        if any(value <= 0 for value in values):
            raise ValueError("Les seuils doivent être strictement positifs.")
        if self.coherence_limit >= self.strong_incoherence_limit:
            raise ValueError(
                "Le seuil de cohérence doit précéder l'incohérence forte."
            )


@dataclass(frozen=True, slots=True)
class ExpectedQuantityComparison:
    """One explicitly declared comparison between two quantity productions."""

    production_id: str
    left_quantity_id: str
    right_quantity_id: str
    method: QuantityComparisonMethod = QuantityComparisonMethod.NORMALIZED_ERROR
    thresholds: NormalizedErrorThresholds = field(
        default_factory=NormalizedErrorThresholds
    )
    pedagogical_context: ComparisonPedagogicalContext = (
        ComparisonPedagogicalContext.OPEN
    )
    context_note: str = ""

    def __post_init__(self) -> None:
        identifiers = (
            (self.production_id, "production_id"),
            (self.left_quantity_id, "left_quantity_id"),
            (self.right_quantity_id, "right_quantity_id"),
        )
        for value, field_name in identifiers:
            if not isinstance(value, str):
                raise TypeError(f"Le champ {field_name!r} doit être une chaîne.")
            if not value.strip():
                raise ValueError(f"Le champ {field_name!r} ne peut pas être vide.")
        if self.left_quantity_id == self.right_quantity_id:
            raise ValueError("Une comparaison exige deux productions distinctes.")
        if not isinstance(self.method, QuantityComparisonMethod):
            raise TypeError("La méthode doit être une QuantityComparisonMethod.")
        if not isinstance(self.thresholds, NormalizedErrorThresholds):
            raise TypeError("Les seuils doivent être des NormalizedErrorThresholds.")
        if not isinstance(self.pedagogical_context, ComparisonPedagogicalContext):
            raise TypeError(
                "Le contexte doit être un ComparisonPedagogicalContext."
            )
        if not isinstance(self.context_note, str):
            raise TypeError("La note de contexte doit être une chaîne.")


@dataclass(frozen=True, slots=True)
class QuantityComparisonExpectationSet:
    """Ordered quantity comparison declarations for one production plan."""

    production_plan: ScientificProductionPlan
    quantity_expectation_set: QuantityExpectationSet
    comparisons: tuple[ExpectedQuantityComparison, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.production_plan, ScientificProductionPlan):
            raise TypeError("Le plan doit être un ScientificProductionPlan.")
        if not isinstance(self.quantity_expectation_set, QuantityExpectationSet):
            raise TypeError("Les quantités doivent former un QuantityExpectationSet.")
        if self.quantity_expectation_set.plan is not self.production_plan:
            raise ValueError("Les comparaisons et les quantités doivent partager le plan.")
        comparisons = tuple(self.comparisons)
        if any(
            not isinstance(comparison, ExpectedQuantityComparison)
            for comparison in comparisons
        ):
            raise TypeError(
                "Chaque comparaison doit être une ExpectedQuantityComparison."
            )
        object.__setattr__(self, "comparisons", comparisons)

        production_ids = [comparison.production_id for comparison in comparisons]
        if len(production_ids) != len(set(production_ids)):
            raise ValueError("Les identifiants des comparaisons doivent être uniques.")

        for comparison in comparisons:
            comparison_production = self.production_plan.get(
                comparison.production_id
            )
            if comparison_production is None:
                raise ValueError(
                    f"Production de comparaison inconnue : {comparison.production_id!r}."
                )
            if comparison_production.kind is not ScientificProductionKind.COMPARISON:
                raise ValueError("La production déclarée doit être de type COMPARISON.")

            for side, quantity_id in (
                ("gauche", comparison.left_quantity_id),
                ("droite", comparison.right_quantity_id),
            ):
                production = self.production_plan.get(quantity_id)
                if production is None:
                    raise ValueError(
                        f"Production quantitative {side} inconnue : {quantity_id!r}."
                    )
                if production.kind is not ScientificProductionKind.QUANTITY:
                    raise ValueError(
                        f"La production {side} doit être de type QUANTITY."
                    )
                if self.quantity_expectation_set.get(quantity_id) is None:
                    raise ValueError(
                        f"La quantité {side} est absente du jeu d'attendus : "
                        f"{quantity_id!r}."
                    )

            required_dependencies = {
                comparison.left_quantity_id,
                comparison.right_quantity_id,
            }
            if not required_dependencies.issubset(comparison_production.depends_on):
                raise ValueError(
                    "La production COMPARISON doit dépendre des deux quantités."
                )

    def __iter__(self) -> Iterator[ExpectedQuantityComparison]:
        return iter(self.comparisons)

    def __len__(self) -> int:
        return len(self.comparisons)

    def get(self, production_id: str) -> ExpectedQuantityComparison | None:
        for comparison in self.comparisons:
            if comparison.production_id == production_id:
                return comparison
        return None

    def for_quantity(
        self, quantity_production_id: str
    ) -> tuple[ExpectedQuantityComparison, ...]:
        """Return comparisons using one known quantity production."""

        production = self.production_plan.get(quantity_production_id)
        if production is None:
            raise ValueError(f"Production inconnue : {quantity_production_id!r}.")
        if production.kind is not ScientificProductionKind.QUANTITY:
            return ()
        return tuple(
            comparison
            for comparison in self.comparisons
            if quantity_production_id
            in (comparison.left_quantity_id, comparison.right_quantity_id)
        )

    def for_context(
        self, context: ComparisonPedagogicalContext
    ) -> tuple[ExpectedQuantityComparison, ...]:
        """Return comparisons having one exact pedagogical context."""

        if not isinstance(context, ComparisonPedagogicalContext):
            raise TypeError("Le contexte doit être un ComparisonPedagogicalContext.")
        return tuple(
            comparison
            for comparison in self.comparisons
            if comparison.pedagogical_context is context
        )

    @property
    def in_evaluation_order(self) -> tuple[ExpectedQuantityComparison, ...]:
        """Declared comparisons ordered by the scientific production plan."""

        by_production_id = {
            comparison.production_id: comparison
            for comparison in self.comparisons
        }
        return tuple(
            by_production_id[production.id]
            for production in self.production_plan.evaluation_order
            if production.id in by_production_id
        )
