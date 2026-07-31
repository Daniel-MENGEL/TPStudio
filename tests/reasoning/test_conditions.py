from dataclasses import FrozenInstanceError

import pytest

from tpstudio.reasoning import (
    AllOf,
    AnyOf,
    Fact,
    FactAbsent,
    FactExists,
    FactKind,
    FactKindExists,
    FactSet,
    Not,
    PredicateExists,
    SubjectExists,
)


def _facts() -> FactSet:
    return FactSet(
        (
            Fact(
                "concept:snell",
                FactKind.CONCEPT_MENTION,
                "snell_descartes",
                "mentioned",
            ),
            Fact(
                "relation:one",
                FactKind.RELATION,
                "angle",
                "depends_on",
                value="indice",
            ),
        )
    )


def test_conditions_are_immutable_and_inspectable() -> None:
    condition = SubjectExists("snell_descartes")

    assert condition.subject == "snell_descartes"
    with pytest.raises(FrozenInstanceError):
        condition.subject = "angle"  # type: ignore[misc]


def test_fact_kind_condition_returns_matching_facts() -> None:
    result = FactKindExists(FactKind.RELATION).evaluate(_facts())

    assert result.satisfied is True
    assert [fact.id for fact in result.contributing_facts] == ["relation:one"]
    assert result.details == (
        ("condition", "FactKindExists"),
        ("criterion", "relation"),
    )


def test_subject_and_predicate_conditions() -> None:
    facts = _facts()

    subject = SubjectExists("snell_descartes").evaluate(facts)
    predicate = PredicateExists("depends_on").evaluate(facts)

    assert subject.satisfied
    assert subject.contributing_facts[0].id == "concept:snell"
    assert predicate.satisfied
    assert predicate.contributing_facts[0].id == "relation:one"


def test_fact_exists_combines_criteria_on_the_same_fact() -> None:
    condition = FactExists(
        kind=FactKind.RELATION,
        subject="angle",
        predicate="depends_on",
    )

    assert condition.evaluate(_facts()).satisfied
    assert not FactExists(
        kind=FactKind.RELATION,
        subject="snell_descartes",
    ).evaluate(_facts()).satisfied


def test_absence_reports_facts_that_make_it_fail() -> None:
    missing = FactAbsent(kind=FactKind.NUMERIC_VALUE).evaluate(_facts())
    present = FactAbsent(kind=FactKind.RELATION).evaluate(_facts())

    assert missing.satisfied
    assert missing.contributing_facts == ()
    assert not present.satisfied
    assert [fact.id for fact in present.contributing_facts] == ["relation:one"]
    assert len(present.children) == 1


def test_fact_criteria_require_at_least_one_criterion() -> None:
    with pytest.raises(ValueError, match="critère"):
        FactExists()
    with pytest.raises(ValueError, match="critère"):
        FactAbsent()


def test_all_of_evaluates_every_child_and_keeps_stable_fact_order() -> None:
    condition = AllOf(
        SubjectExists("snell_descartes"),
        PredicateExists("depends_on"),
    )

    first = condition.evaluate(_facts())
    second = condition.evaluate(_facts())

    assert first.satisfied
    assert len(first.children) == 2
    assert [fact.id for fact in first.contributing_facts] == [
        "concept:snell",
        "relation:one",
    ]
    assert first == second


def test_any_of_and_not_keep_child_traces() -> None:
    condition = AnyOf(
        SubjectExists("absent"),
        Not(FactKindExists(FactKind.NUMERIC_VALUE)),
    )

    result = condition.evaluate(_facts())

    assert result.satisfied
    assert [child.satisfied for child in result.children] == [False, True]
    assert len(result.children[1].children) == 1


def test_conditions_on_empty_fact_set_are_deterministic() -> None:
    facts = FactSet()

    assert not SubjectExists("angle").evaluate(facts).satisfied
    assert FactAbsent(subject="angle").evaluate(facts).satisfied
    assert AllOf().evaluate(facts).satisfied
    assert not AnyOf().evaluate(facts).satisfied
