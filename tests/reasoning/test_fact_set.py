import pytest

from tpstudio.reasoning import Fact, FactKind, FactSet


def _fact(identifier: str, kind: FactKind, subject: str) -> Fact:
    return Fact(identifier, kind, subject, "mentioned")


def test_fact_set_adds_iterates_and_filters_in_insertion_order() -> None:
    laser = _fact("laser", FactKind.CONCEPT_MENTION, "laser")
    value = _fact("value", FactKind.NUMERIC_VALUE, "angle")
    facts = FactSet((laser, value))

    assert list(facts) == [laser, value]
    assert len(facts) == 2
    assert list(facts.by_kind(FactKind.CONCEPT_MENTION)) == [laser]
    assert list(facts.by_subject("angle")) == [value]
    assert list(facts.filter(kind=FactKind.NUMERIC_VALUE, subject="angle")) == [
        value
    ]


def test_fact_set_deduplicates_equal_facts() -> None:
    fact = _fact("laser", FactKind.CONCEPT_MENTION, "laser")
    facts = FactSet()

    facts.add(fact)
    facts.add(fact)

    assert len(facts) == 1


def test_fact_set_rejects_identifier_collision() -> None:
    facts = FactSet((_fact("same", FactKind.CONCEPT_MENTION, "laser"),))

    with pytest.raises(ValueError, match="déjà utilisé"):
        facts.add(_fact("same", FactKind.CONCEPT_MENTION, "plexiglas"))
