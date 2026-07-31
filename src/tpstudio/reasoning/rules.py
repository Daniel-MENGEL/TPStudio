"""Immutable pedagogical rules and their individual evaluation traces."""

from __future__ import annotations

from dataclasses import dataclass

from .conditions import AllOf, Condition, ConditionResult
from .fact_set import FactSet


StructuredValue = str | int | float | bool | None
StructuredData = tuple[tuple[str, StructuredValue], ...]


@dataclass(frozen=True, slots=True)
class RuleConclusion:
    """A machine-readable outcome, separate from future student wording."""

    code: str
    category: str | None = None
    data: StructuredData = ()

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("Le code d'une conclusion ne peut pas être vide.")
        if len({key for key, _ in self.data}) != len(self.data):
            raise ValueError(
                "Les clés des données d'une conclusion doivent être uniques."
            )


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    """The complete immutable trace of one rule evaluation."""

    rule_id: str
    triggered: bool
    condition_result: ConditionResult
    conclusion: RuleConclusion | None = None

    def __post_init__(self) -> None:
        if self.triggered != (self.conclusion is not None):
            raise ValueError(
                "Une conclusion doit être présente si et seulement si la règle "
                "est déclenchée."
            )


@dataclass(frozen=True, slots=True)
class Rule:
    """One declarative pedagogical rule evaluated independently."""

    id: str
    condition: Condition
    conclusion: RuleConclusion
    label: str = ""
    priority: int = 0
    metadata: frozenset[str] = frozenset()
    _legacy_conditions: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        # Compatibility with the short-lived pre-A64 shape
        # ``Rule(id, description, conditions)``.
        if isinstance(self.condition, str) and isinstance(self.conclusion, list):
            object.__setattr__(self, "label", self.condition)
            object.__setattr__(self, "_legacy_conditions", tuple(self.conclusion))
            object.__setattr__(self, "condition", AllOf())
            object.__setattr__(
                self,
                "conclusion",
                RuleConclusion(code=f"legacy:{self.id}"),
            )

        if not self.id:
            raise ValueError("L'identifiant d'une règle ne peut pas être vide.")
        if not isinstance(self.condition, Condition):
            raise TypeError("La condition d'une règle doit être une Condition.")
        if not isinstance(self.conclusion, RuleConclusion):
            raise TypeError("La conclusion d'une règle doit être structurée.")
        object.__setattr__(self, "metadata", frozenset(self.metadata))

    @property
    def conditions(self) -> tuple[object, ...]:
        """Legacy view retained for the pre-A64 public prototype."""

        return self._legacy_conditions

    def evaluate(self, facts: FactSet) -> RuleEvaluation:
        if self._legacy_conditions:
            raise NotImplementedError(
                "Les règles antérieures à A64 doivent être migrées avant "
                "leur évaluation."
            )

        condition_result = self.condition.evaluate(facts)
        return RuleEvaluation(
            rule_id=self.id,
            triggered=condition_result.satisfied,
            condition_result=condition_result,
            conclusion=self.conclusion if condition_result.satisfied else None,
        )
