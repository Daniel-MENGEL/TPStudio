from dataclasses import FrozenInstanceError

import pytest

from tpstudio.expectations import (
    ExpectedConclusion,
    ExpectedRelation,
    ExpectationSet,
)


def _relation(identifier: str = "relation") -> ExpectedRelation:
    return ExpectedRelation(identifier, "Relation", "a = b")


def _conclusion(identifier: str = "conclusion") -> ExpectedConclusion:
    return ExpectedConclusion(identifier, "Conclusion", "A dépend de B.")


def test_relation_is_immutable_and_preserves_exact_expression_order() -> None:
    relation = ExpectedRelation(
        "snell",
        "Snell-Descartes",
        r"n_1 \sin(i_1) = n_2 \sin(i_2)",
        accepted_expressions=(
            "n1 sin(i1) = n2 sin(i2)",
            r"n_1 \sin(i_1) = n_2 \sin(i_2)",
            "n₂ sin(i₂) = n₁ sin(i₁)",
            "n1 sin(i1) = n2 sin(i2)",
        ),
    )

    assert relation.expressions == (
        r"n_1 \sin(i_1) = n_2 \sin(i_2)",
        "n1 sin(i1) = n2 sin(i2)",
        "n₂ sin(i₂) = n₁ sin(i₁)",
    )
    with pytest.raises(FrozenInstanceError):
        relation.label = "Changed"  # type: ignore[misc]


def test_conclusion_is_immutable_and_stably_deduplicates_statements() -> None:
    conclusion = ExpectedConclusion(
        "meaning",
        "Sens physique",
        "A dépend de B.",
        accepted_statements=("B agit sur A.", "A dépend de B.", "B agit sur A."),
    )

    assert conclusion.statements == ("A dépend de B.", "B agit sur A.")
    with pytest.raises(FrozenInstanceError):
        conclusion.required = False  # type: ignore[misc]


@pytest.mark.parametrize(
    "factory",
    (
        lambda: ExpectedRelation("", "Label", "a = b"),
        lambda: ExpectedRelation("id", " ", "a = b"),
        lambda: ExpectedRelation("id", "Label", ""),
        lambda: ExpectedConclusion("", "Label", "Statement"),
        lambda: ExpectedConclusion("id", "", "Statement"),
        lambda: ExpectedConclusion("id", "Label", "  "),
        lambda: ExpectationSet("", "Title", relations=(_relation(),)),
        lambda: ExpectationSet("id", " ", conclusions=(_conclusion(),)),
    ),
)
def test_required_text_fields_reject_empty_values(factory) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="ne peut pas être vide"):
        factory()


def test_expectation_set_is_immutable_ordered_and_searchable() -> None:
    first_relation = _relation("r1")
    second_relation = _relation("r2")
    conclusion = _conclusion("c1")
    expectation_set = ExpectationSet(
        "set",
        "Set",
        relations=(first_relation, second_relation),
        conclusions=(conclusion,),
    )

    assert expectation_set.relations == (first_relation, second_relation)
    assert expectation_set.conclusions == (conclusion,)
    assert expectation_set.relation_by_id("r2") is second_relation
    assert expectation_set.conclusion_by_id("c1") is conclusion
    assert expectation_set.expectation_by_id("r1") is first_relation
    assert expectation_set.expectation_by_id("unknown") is None
    with pytest.raises(FrozenInstanceError):
        expectation_set.title = "Changed"  # type: ignore[misc]


def test_expectation_set_rejects_duplicate_and_shared_identifiers() -> None:
    with pytest.raises(ValueError, match="relations.*uniques"):
        ExpectationSet("set", "Set", relations=(_relation(), _relation()))
    with pytest.raises(ValueError, match="conclusions.*uniques"):
        ExpectationSet("set", "Set", conclusions=(_conclusion(), _conclusion()))
    with pytest.raises(ValueError, match="partager"):
        ExpectationSet(
            "set",
            "Set",
            relations=(_relation("shared"),),
            conclusions=(_conclusion("shared"),),
        )


def test_expectation_set_allows_an_empty_declaration() -> None:
    assert ExpectationSet("set", "Set").relations == ()
