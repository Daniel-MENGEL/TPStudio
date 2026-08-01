"""Generic contracts for scientific productions expected from students."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum


class ScientificProductionKind(str, Enum):
    """Broad family of a scientific production."""

    RELATION = "relation"
    INTERPRETATION = "interpretation"
    QUANTITY = "quantity"
    PLOT = "plot"
    COMPARISON = "comparison"
    JUSTIFICATION = "justification"


class EvaluationBasis(str, Enum):
    """Basis on which a future evaluator will assess a production."""

    DECLARED_CONTENT = "declared_content"
    FIXED_REFERENCE = "fixed_reference"
    SUBMISSION_DERIVED = "submission_derived"
    CROSS_PRODUCTION = "cross_production"
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"


@dataclass(frozen=True, slots=True)
class ScientificProductionSpec:
    """Teacher-declared nature and future evaluation bases of a production."""

    id: str
    label: str
    kind: ScientificProductionKind
    evaluation_bases: tuple[EvaluationBasis, ...]
    depends_on: tuple[str, ...] = ()
    required: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("L'identifiant d'une production ne peut pas être vide.")
        if not self.label.strip():
            raise ValueError("Le libellé d'une production ne peut pas être vide.")
        if not isinstance(self.kind, ScientificProductionKind):
            raise TypeError(
                "Le type d'une production doit être un ScientificProductionKind."
            )

        bases = tuple(self.evaluation_bases)
        if not bases:
            raise ValueError(
                "Une production doit avoir au moins une base d'évaluation."
            )
        if any(not isinstance(basis, EvaluationBasis) for basis in bases):
            raise TypeError(
                "Chaque base d'évaluation doit être une EvaluationBasis."
            )
        object.__setattr__(self, "evaluation_bases", tuple(dict.fromkeys(bases)))

        dependencies = tuple(self.depends_on)
        if any(not dependency.strip() for dependency in dependencies):
            raise ValueError("Un identifiant de dépendance ne peut pas être vide.")
        unique_dependencies = tuple(dict.fromkeys(dependencies))
        if self.id in unique_dependencies:
            raise ValueError("Une production ne peut pas dépendre d'elle-même.")
        object.__setattr__(self, "depends_on", unique_dependencies)


def _stable_topological_order(
    productions: tuple[ScientificProductionSpec, ...],
) -> tuple[ScientificProductionSpec, ...]:
    """Order dependencies first while favoring declaration order."""

    remaining = {production.id for production in productions}
    completed: set[str] = set()
    ordered: list[ScientificProductionSpec] = []

    while remaining:
        next_production = next(
            (
                production
                for production in productions
                if production.id in remaining
                and set(production.depends_on).issubset(completed)
            ),
            None,
        )
        if next_production is None:
            raise ValueError("Le plan de productions contient un cycle.")
        ordered.append(next_production)
        completed.add(next_production.id)
        remaining.remove(next_production.id)

    return tuple(ordered)


@dataclass(frozen=True, slots=True)
class ScientificProductionPlan:
    """An immutable dependency plan for expected scientific productions."""

    id: str
    title: str
    productions: tuple[ScientificProductionSpec, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("L'identifiant d'un plan ne peut pas être vide.")
        if not self.title.strip():
            raise ValueError("Le titre d'un plan ne peut pas être vide.")

        productions = tuple(self.productions)
        if not productions:
            raise ValueError("Un plan de productions ne peut pas être vide.")
        if any(
            not isinstance(production, ScientificProductionSpec)
            for production in productions
        ):
            raise TypeError(
                "Chaque élément du plan doit être une ScientificProductionSpec."
            )
        object.__setattr__(self, "productions", productions)

        identifiers = [production.id for production in productions]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Les identifiants des productions doivent être uniques.")

        known_ids = set(identifiers)
        unknown_dependencies = {
            dependency
            for production in productions
            for dependency in production.depends_on
            if dependency not in known_ids
        }
        if unknown_dependencies:
            unknown = sorted(unknown_dependencies)[0]
            raise ValueError(f"Dépendance de production inconnue : {unknown!r}.")

        _stable_topological_order(productions)

    def __iter__(self) -> Iterator[ScientificProductionSpec]:
        return iter(self.productions)

    def __len__(self) -> int:
        return len(self.productions)

    def get(self, production_id: str) -> ScientificProductionSpec | None:
        for production in self.productions:
            if production.id == production_id:
                return production
        return None

    @property
    def evaluation_order(self) -> tuple[ScientificProductionSpec, ...]:
        """Stable topological order, with dependencies before consumers."""

        return _stable_topological_order(self.productions)
