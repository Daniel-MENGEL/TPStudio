"""Declarative, inspectable conditions over collections of facts."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import FactKind
from .fact_set import FactSet
from .facts import Fact


@dataclass(frozen=True, slots=True)
class ConditionResult:
    """Immutable trace produced by evaluating one condition."""

    satisfied: bool
    contributing_facts: tuple[Fact, ...] = ()
    children: tuple[ConditionResult, ...] = ()
    details: tuple[tuple[str, str], ...] = ()


class Condition:
    """Base class for every declarative fact condition."""

    __slots__ = ("fact", "operator", "expected_value")

    def __init__(
        self,
        fact: str | None = None,
        operator: str | None = None,
        expected_value: object | None = None,
    ) -> None:
        # The optional fields preserve construction of the pre-A64 placeholder
        # while concrete A64 conditions remain frozen dataclasses.
        self.fact = fact
        self.operator = operator
        self.expected_value = expected_value

    def evaluate(self, facts: FactSet) -> ConditionResult:
        """Evaluate the condition and return an explainable trace."""

        raise NotImplementedError("Utiliser une condition A64 concrète.")


def _matching_result(
    condition_name: str,
    criterion: str,
    matches: tuple[Fact, ...],
) -> ConditionResult:
    return ConditionResult(
        satisfied=bool(matches),
        contributing_facts=matches,
        details=(("condition", condition_name), ("criterion", criterion)),
    )


def _unique_facts(results: tuple[ConditionResult, ...]) -> tuple[Fact, ...]:
    """Collect contributing facts once, preserving evaluation order."""

    unique: dict[str, Fact] = {}
    for result in results:
        for fact in result.contributing_facts:
            unique.setdefault(fact.id, fact)
    return tuple(unique.values())


@dataclass(frozen=True, slots=True)
class FactKindExists(Condition):
    kind: FactKind

    def evaluate(self, facts: FactSet) -> ConditionResult:
        matches = tuple(fact for fact in facts if fact.kind is self.kind)
        return _matching_result(type(self).__name__, self.kind.value, matches)


@dataclass(frozen=True, slots=True)
class SubjectExists(Condition):
    subject: str

    def evaluate(self, facts: FactSet) -> ConditionResult:
        matches = tuple(fact for fact in facts if fact.subject == self.subject)
        return _matching_result(type(self).__name__, self.subject, matches)


@dataclass(frozen=True, slots=True)
class PredicateExists(Condition):
    predicate: str

    def evaluate(self, facts: FactSet) -> ConditionResult:
        matches = tuple(fact for fact in facts if fact.predicate == self.predicate)
        return _matching_result(type(self).__name__, self.predicate, matches)


@dataclass(frozen=True, slots=True)
class FactExists(Condition):
    """Test a conjunction of optional criteria against individual facts."""

    kind: FactKind | None = None
    subject: str | None = None
    predicate: str | None = None

    def __post_init__(self) -> None:
        if self.kind is None and self.subject is None and self.predicate is None:
            raise ValueError("FactExists requiert au moins un critère.")

    def evaluate(self, facts: FactSet) -> ConditionResult:
        matches = tuple(
            fact
            for fact in facts
            if (self.kind is None or fact.kind is self.kind)
            and (self.subject is None or fact.subject == self.subject)
            and (self.predicate is None or fact.predicate == self.predicate)
        )
        criteria = (
            f"kind={self.kind.value if self.kind else '*'},"
            f"subject={self.subject or '*'},"
            f"predicate={self.predicate or '*'}"
        )
        return _matching_result(type(self).__name__, criteria, matches)


@dataclass(frozen=True, slots=True)
class Not(Condition):
    condition: Condition

    def evaluate(self, facts: FactSet) -> ConditionResult:
        child = self.condition.evaluate(facts)
        return ConditionResult(
            satisfied=not child.satisfied,
            contributing_facts=child.contributing_facts,
            children=(child,),
            details=(("condition", type(self).__name__),),
        )


@dataclass(frozen=True, slots=True)
class FactAbsent(Condition):
    """Test that no single fact matches all supplied criteria."""

    kind: FactKind | None = None
    subject: str | None = None
    predicate: str | None = None

    def __post_init__(self) -> None:
        if self.kind is None and self.subject is None and self.predicate is None:
            raise ValueError("FactAbsent requiert au moins un critère.")

    def evaluate(self, facts: FactSet) -> ConditionResult:
        child = FactExists(
            kind=self.kind,
            subject=self.subject,
            predicate=self.predicate,
        ).evaluate(facts)
        return ConditionResult(
            satisfied=not child.satisfied,
            contributing_facts=child.contributing_facts,
            children=(child,),
            details=(("condition", type(self).__name__),),
        )


@dataclass(frozen=True, slots=True, init=False)
class AllOf(Condition):
    conditions: tuple[Condition, ...]

    def __init__(self, *conditions: Condition) -> None:
        object.__setattr__(self, "conditions", tuple(conditions))

    def evaluate(self, facts: FactSet) -> ConditionResult:
        children = tuple(condition.evaluate(facts) for condition in self.conditions)
        return ConditionResult(
            satisfied=all(child.satisfied for child in children),
            contributing_facts=_unique_facts(children),
            children=children,
            details=(("condition", type(self).__name__),),
        )


@dataclass(frozen=True, slots=True, init=False)
class AnyOf(Condition):
    conditions: tuple[Condition, ...]

    def __init__(self, *conditions: Condition) -> None:
        object.__setattr__(self, "conditions", tuple(conditions))

    def evaluate(self, facts: FactSet) -> ConditionResult:
        children = tuple(condition.evaluate(facts) for condition in self.conditions)
        return ConditionResult(
            satisfied=any(child.satisfied for child in children),
            contributing_facts=_unique_facts(children),
            children=children,
            details=(("condition", type(self).__name__),),
        )


Or = AnyOf
And = AllOf
