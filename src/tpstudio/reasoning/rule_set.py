"""Ordered storage for declarative rules."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .rules import Rule


class RuleSet:
    """An insertion-ordered collection with unique rule identifiers."""

    def __init__(self, rules: Iterable[Rule] = ()) -> None:
        self._rules: dict[str, Rule] = {}
        for rule in rules:
            self.add(rule)

    def add(self, rule: Rule) -> None:
        """Add ``rule`` and reject every duplicate identifier."""

        if rule.id in self._rules:
            raise ValueError(f"L'identifiant de règle {rule.id!r} existe déjà.")
        self._rules[rule.id] = rule

    def __iter__(self) -> Iterator[Rule]:
        return iter(self._rules.values())

    def __len__(self) -> int:
        return len(self._rules)

    def __bool__(self) -> bool:
        return bool(self._rules)

    def get(self, rule_id: str) -> Rule | None:
        return self._rules.get(rule_id)

    by_id = get

    def by_priority(self, priority: int) -> RuleSet:
        return RuleSet(rule for rule in self if rule.priority == priority)

    def with_metadata(self, metadata: str) -> RuleSet:
        return RuleSet(rule for rule in self if metadata in rule.metadata)
