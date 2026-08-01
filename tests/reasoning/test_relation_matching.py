from dataclasses import FrozenInstanceError
import inspect

import pytest

import tpstudio.reasoning.relation_matching as relation_matching
from tpstudio.expectations import (
    ExpectedConclusion,
    ExpectedRelation,
    ExpectationSet,
)
from tpstudio.reasoning import (
    FactKind,
    LiteralRelationMatcher,
    RelationDetection,
    RelationDetectionSet,
    RelationMatch,
    match_declared_relations,
)


def _relation(
    identifier: str = "relation",
    expression: str = "a = b",
    *,
    variants: tuple[str, ...] = (),
    required: bool = True,
) -> ExpectedRelation:
    return ExpectedRelation(
        identifier,
        f"Relation {identifier}",
        expression,
        accepted_expressions=variants,
        required=required,
    )


def _expectations(*relations: ExpectedRelation) -> ExpectationSet:
    return ExpectationSet("set", "Set", relations=relations)


def test_relation_match_is_immutable_and_validates_exact_span() -> None:
    match = RelationMatch("r", "a = b", "a = b", 4, 9, True)

    assert match.start == 4
    with pytest.raises(FrozenInstanceError):
        match.start = 0  # type: ignore[misc]


@pytest.mark.parametrize(
    "arguments",
    (
        ("", "a", "a", 0, 1, True),
        ("   ", "a", "a", 0, 1, True),
        ("r", "", "a", 0, 1, True),
        ("r", "   ", "   ", 0, 3, True),
        ("r", "a", "", 0, 1, True),
        ("r", "a", "   ", 0, 3, False),
        ("r", "a", "a", -1, 0, True),
        ("r", "a", "a", 1, 1, True),
        ("r", "abc", "abc", 0, 2, True),
        ("r", "abc", "abd", 0, 3, True),
    ),
)
def test_relation_match_rejects_invalid_data(arguments) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError):
        RelationMatch(*arguments)


def test_detection_normalizes_matches_to_tuple_and_removes_exact_duplicates() -> None:
    relation = _relation()
    match = RelationMatch("relation", "a = b", "a = b", 0, 5, True)
    detection = RelationDetection(  # type: ignore[arg-type]
        relation,
        [match, match],
    )

    assert detection.matches == (match,)
    assert detection.relation_id == "relation"
    assert detection.found
    assert detection.first_match is match
    with pytest.raises(FrozenInstanceError):
        detection.matches = ()  # type: ignore[misc]


def test_negative_detection_has_no_first_match() -> None:
    detection = RelationDetection(_relation())

    assert not detection.found
    assert detection.first_match is None


def test_detection_rejects_match_for_another_relation() -> None:
    foreign = RelationMatch("other", "a = b", "a = b", 0, 5, True)

    with pytest.raises(ValueError, match="référencer"):
        RelationDetection(_relation(), (foreign,))


def test_detection_rejects_an_undeclared_expression() -> None:
    undeclared = RelationMatch("relation", "b = a", "b = a", 0, 5, False)

    with pytest.raises(ValueError, match="expression déclarée"):
        RelationDetection(_relation(), (undeclared,))


@pytest.mark.parametrize(
    ("declared_expression", "is_canonical"),
    (("a = b", False), ("b = a", True)),
)
def test_detection_rejects_incoherent_canonical_status(
    declared_expression: str,
    is_canonical: bool,
) -> None:
    relation = _relation(variants=("b = a",))
    match = RelationMatch(
        "relation",
        declared_expression,
        declared_expression,
        0,
        len(declared_expression),
        is_canonical,
    )

    with pytest.raises(ValueError, match="statut canonique"):
        RelationDetection(relation, (match,))


def test_direct_detection_orders_same_start_by_declared_expression_order() -> None:
    relation = _relation(expression="a", variants=("ab",))
    canonical = RelationMatch("relation", "a", "a", 0, 1, True)
    variant = RelationMatch("relation", "ab", "ab", 0, 2, False)

    detection = RelationDetection(relation, (variant, canonical))

    assert detection.matches == (canonical, variant)


def test_significant_outer_spaces_are_preserved_exactly() -> None:
    expression = "  a = b  "
    relation = _relation(expression=expression)

    match = match_declared_relations(
        f"avant{expression}après", _expectations(relation)
    ).found[0].first_match

    assert relation.canonical_expression == expression
    assert match is not None
    assert match.declared_expression == expression
    assert match.matched_text == expression


def test_detection_set_is_immutable_ordered_and_searchable() -> None:
    first = RelationDetection(_relation("first", "a"))
    second_match = RelationMatch("second", "b", "b", 0, 1, True)
    second = RelationDetection(_relation("second", "b"), (second_match,))
    detections = RelationDetectionSet("set", [first, second])  # type: ignore[arg-type]

    assert tuple(detections) == (first, second)
    assert len(detections) == 2
    assert detections.get("second") is second
    assert detections.relation_detection_by_id("first") is first
    assert detections.get("unknown") is None
    assert detections.found == (second,)
    assert detections.missing == (first,)
    with pytest.raises(FrozenInstanceError):
        detections.detections = ()  # type: ignore[misc]


def test_detection_set_rejects_duplicate_relation_ids() -> None:
    detection = RelationDetection(_relation())

    with pytest.raises(ValueError, match="uniques"):
        RelationDetectionSet("set", (detection, detection))


def test_canonical_match_has_exact_offsets_and_text_invariant() -> None:
    expression = r"n_1 \sin(i_1) = n_2 \sin(i_2)"
    text = f"La relation est ${expression}$."

    match = LiteralRelationMatcher().match(
        text, _expectations(_relation(expression=expression))
    ).found[0].first_match

    assert match is not None
    assert match.is_canonical
    assert match.declared_expression == expression
    assert (match.start, match.end) == (17, 46)
    assert text[match.start : match.end] == match.matched_text == expression


def test_declared_variant_is_found_but_not_canonical() -> None:
    relation = _relation(variants=("b = a",))

    match = match_declared_relations("Donc b = a.", _expectations(relation)).found[
        0
    ].first_match

    assert match is not None
    assert match.declared_expression == "b = a"
    assert not match.is_canonical


@pytest.mark.parametrize(
    "text",
    (
        "A = b",
        "a  = b",
        "a=b",
        "b = a",
        "a =\nb",
    ),
)
def test_undeclared_case_spacing_order_and_newline_variants_are_not_found(
    text: str,
) -> None:
    detection = match_declared_relations(text, _expectations(_relation()))

    assert not detection.found
    assert detection.missing == detection.detections


def test_unicode_matching_is_exact() -> None:
    relation = _relation(expression="n₂ sin(i₂) = n₁ sin(i₁)")

    exact = match_declared_relations(
        "n₂ sin(i₂) = n₁ sin(i₁)", _expectations(relation)
    )
    ascii_text = match_declared_relations(
        "n2 sin(i2) = n1 sin(i1)", _expectations(relation)
    )

    assert exact.found
    assert not ascii_text.found


def test_all_occurrences_are_kept_and_first_match_is_earliest() -> None:
    text = "a = b puis a = b et a = b"
    detection = match_declared_relations(text, _expectations(_relation())).found[0]

    assert [match.start for match in detection.matches] == [0, 11, 20]
    assert detection.first_match == detection.matches[0]


def test_multiple_variants_are_sorted_by_position_then_declaration_order() -> None:
    relation = _relation(expression="canonical", variants=("variant", "other"))
    text = "variant then canonical then other"

    matches = match_declared_relations(text, _expectations(relation)).found[0].matches

    assert [match.declared_expression for match in matches] == [
        "variant",
        "canonical",
        "other",
    ]
    assert [match.start for match in matches] == sorted(match.start for match in matches)


def test_relation_order_is_declaration_order_even_when_text_order_differs() -> None:
    expectations = _expectations(
        _relation("first", "first expression"),
        _relation("second", "second expression"),
    )

    detections = match_declared_relations(
        "second expression, then first expression", expectations
    )

    assert [item.relation_id for item in detections] == ["first", "second"]
    assert [item.relation_id for item in detections.found] == ["first", "second"]


def test_empty_text_returns_one_negative_detection_per_relation() -> None:
    detections = match_declared_relations(
        "", _expectations(_relation("r1"), _relation("r2", "c = d"))
    )

    assert len(detections) == 2
    assert detections.found == ()
    assert detections.missing == detections.detections


def test_conclusions_are_ignored() -> None:
    expectations = ExpectationSet(
        "conclusions-only",
        "Conclusions",
        conclusions=(ExpectedConclusion("c", "Conclusion", "a = b"),),
    )

    detections = match_declared_relations("a = b", expectations)

    assert len(detections) == 0
    assert detections.found == detections.missing == ()


def test_required_flag_has_no_effect_on_matching() -> None:
    expectations = _expectations(
        _relation("required", "a", required=True),
        _relation("optional", "b", required=False),
    )

    detections = match_declared_relations("a b", expectations)

    assert [item.relation.required for item in detections.found] == [True, False]


def test_matcher_creates_neither_facts_nor_ai_calls_and_leaves_factkind_unchanged() -> None:
    fact_kinds_before = tuple(FactKind)
    detections = match_declared_relations("a = b", _expectations(_relation()))
    source = inspect.getsource(relation_matching)

    assert all(isinstance(item, RelationDetection) for item in detections)
    assert tuple(FactKind) == fact_kinds_before
    assert "Fact(" not in source
    assert "openai" not in source.lower()
    assert "import re" not in source
