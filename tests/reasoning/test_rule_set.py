import pytest

from tpstudio.reasoning import (
    FactKind,
    FactKindExists,
    Rule,
    RuleConclusion,
    RuleSet,
)


def _rule(
    identifier: str,
    *,
    priority: int = 0,
    metadata: frozenset[str] = frozenset(),
) -> Rule:
    return Rule(
        identifier,
        FactKindExists(FactKind.RELATION),
        RuleConclusion(f"conclusion:{identifier}"),
        priority=priority,
        metadata=metadata,
    )


def test_rule_set_is_ordered_and_searchable() -> None:
    first = _rule("R1")
    second = _rule("R2")
    rules = RuleSet((first, second))

    assert list(rules) == [first, second]
    assert len(rules) == 2
    assert rules.get("R2") is second
    assert rules.get("absent") is None


def test_rule_set_rejects_even_an_identical_duplicate() -> None:
    rule = _rule("R1")
    rules = RuleSet((rule,))

    with pytest.raises(ValueError, match="existe déjà"):
        rules.add(rule)


def test_rule_set_filters_without_reordering() -> None:
    first = _rule("R1", priority=10, metadata=frozenset(("optics",)))
    second = _rule("R2", priority=2, metadata=frozenset(("mechanics",)))
    third = _rule("R3", priority=10, metadata=frozenset(("optics", "protocol")))
    rules = RuleSet((first, second, third))

    assert list(rules.by_priority(10)) == [first, third]
    assert list(rules.with_metadata("optics")) == [first, third]


def test_empty_rule_set_is_false_and_iterable() -> None:
    rules = RuleSet()

    assert not rules
    assert list(rules) == []
