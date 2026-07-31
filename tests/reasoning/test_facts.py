from dataclasses import FrozenInstanceError

import pytest

from tpstudio.reasoning import Evidence, Fact, FactKind


def test_evidence_preserves_original_span_and_recognized_term() -> None:
    text = "Le laser traverse le plexiglas."
    evidence = Evidence(text, 3, 8, matched_term="laser")

    assert evidence.excerpt == "laser"
    assert evidence.source_text[evidence.start : evidence.end] == "laser"
    assert evidence.matched_term == "laser"


@pytest.mark.parametrize(
    ("start", "end"),
    [(-1, 1), (2, 1), (0, 4)],
)
def test_evidence_rejects_invalid_spans(start: int, end: int) -> None:
    with pytest.raises(ValueError):
        Evidence("abc", start, end)


def test_fact_is_immutable_and_validates_confidence() -> None:
    fact = Fact("concept:laser", FactKind.CONCEPT_MENTION, "laser", "mentioned")

    with pytest.raises(FrozenInstanceError):
        fact.subject = "plexiglas"  # type: ignore[misc]

    with pytest.raises(ValueError, match="confiance"):
        Fact("invalid", FactKind.RELATION, "laser", "crosses", confidence=1.1)


def test_fact_requires_a_fact_kind() -> None:
    with pytest.raises(TypeError, match="FactKind"):
        Fact(
            id="invalid",
            kind="concept_mention",  # type: ignore[arg-type]
            subject="laser",
            predicate="mentioned",
        )
