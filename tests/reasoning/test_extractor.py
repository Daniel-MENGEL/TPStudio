from tpstudio.glossary import Glossary, ScientificTerm
from tpstudio.reasoning import ConceptExtractor, FactKind, extract_concepts


def test_extracts_multiple_concepts_without_relations() -> None:
    text = "Le laser traverse le plexiglas."
    facts = list(extract_concepts(text))

    assert [fact.subject for fact in facts] == ["laser", "plexiglas"]
    assert all(fact.kind is FactKind.CONCEPT_MENTION for fact in facts)
    assert all(fact.predicate == "mentioned" for fact in facts)
    assert all(fact.value is None for fact in facts)


def test_uses_a_custom_glossary() -> None:
    glossary = Glossary(
        "electricity",
        "Électricité",
        (
            ScientificTerm(
                "conductivite",
                "conductivité",
                "quantity",
                aliases=("conductivite",),
            ),
        ),
    )

    facts = list(ConceptExtractor(glossary).extract("La CONDUCTIVITE augmente."))

    assert [fact.subject for fact in facts] == ["conductivite"]
    assert facts[0].evidence is not None
    assert facts[0].evidence.excerpt == "CONDUCTIVITE"
    assert facts[0].evidence.matched_term == "conductivite"


def test_deduplicates_repeated_concept_and_keeps_first_position() -> None:
    text = "laser puis LASER"

    facts = list(extract_concepts(text))

    assert len(facts) == 1
    assert facts[0].evidence is not None
    assert (facts[0].evidence.start, facts[0].evidence.end) == (0, 5)


def test_preserves_unicode_offsets_after_normalization() -> None:
    glossary = Glossary(
        "unicode",
        "Unicode",
        (ScientificTerm("coeur", "cœur optique", "phenomenon"),),
    )
    text = "Étudier le COEUR\n  OPTIQUE précisément."

    fact = next(iter(extract_concepts(text, glossary)))

    assert fact.evidence is not None
    assert fact.evidence.excerpt == "COEUR\n  OPTIQUE"
    assert text[fact.evidence.start : fact.evidence.end] == "COEUR\n  OPTIQUE"


def test_returns_an_empty_fact_set_when_nothing_matches() -> None:
    assert not extract_concepts("Une phrase sans vocabulaire reconnu.")
