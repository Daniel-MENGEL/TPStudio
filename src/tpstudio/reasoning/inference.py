"""Deterministic evaluation of rule collections."""

from __future__ import annotations

from dataclasses import dataclass

from .fact_set import FactSet
from .rule_set import RuleSet
from .rules import RuleConclusion, RuleEvaluation


@dataclass(frozen=True, slots=True)
class InferenceResult:
    """Immutable result of evaluating a complete :class:`RuleSet`.

    ``evaluations`` is the single stored sequence. All other views are
    calculated from it and preserve its order.
    """

    evaluations: tuple[RuleEvaluation, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluations", tuple(self.evaluations))

    @property
    def triggered(self) -> tuple[RuleEvaluation, ...]:
        """Evaluations whose rules fired, in RuleSet order."""

        return tuple(
            evaluation for evaluation in self.evaluations if evaluation.triggered
        )

    @property
    def not_triggered(self) -> tuple[RuleEvaluation, ...]:
        """Evaluations whose rules did not fire, in RuleSet order."""

        return tuple(
            evaluation for evaluation in self.evaluations if not evaluation.triggered
        )

    @property
    def conclusions(self) -> tuple[RuleConclusion, ...]:
        """Every produced conclusion, without merging duplicate codes."""

        return tuple(
            evaluation.conclusion
            for evaluation in self.evaluations
            if evaluation.conclusion is not None
        )

    @property
    def total(self) -> int:
        """Number of evaluated rules."""

        return len(self.evaluations)

    @property
    def total_evaluated(self) -> int:
        """Explicit alias for callers displaying evaluation statistics."""

        return self.total


class InferenceEngine:
    """Evaluate every rule once, in collection order.

    Exceptions from individual rules deliberately propagate to the caller.
    The engine performs no conflict resolution and no forward chaining.
    """

    def evaluate(self, facts: FactSet, rules: RuleSet) -> InferenceResult:
        evaluations = tuple(rule.evaluate(facts) for rule in rules)
        return InferenceResult(evaluations=evaluations)
