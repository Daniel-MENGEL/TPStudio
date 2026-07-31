from dataclasses import FrozenInstanceError

import pytest

from tpstudio.glossary import Glossary, ScientificTerm
from tpstudio.reasoning import (
    AllOf,
    ConceptExtractor,
    Fact,
    FactKind,
    FactKindExists,
    FactSet,
    Not,
    Rule,
    RuleConclusion,
    RuleEvaluation,
    SubjectExists,
)


def _rule() -> Rule:
    return Rule(
        id="R001",
        label="Relation de Snell-Descartes manquante",
        condition=AllOf(
            SubjectExists("snell_descartes"),
            Not(FactKindExists(FactKind.RELATION)),
        ),
        conclusion=RuleConclusion(
            code="relation_missing",
            category="scientific_relation",
            data=(("concept", "snell_descartes"),),
        ),
        priority=10,
        metadata=frozenset(("optics", "protocol")),
    )


def test_rule_models_are_immutable_and_structured() -> None:
    rule = _rule()

    assert rule.conclusion.code == "relation_missing"
    assert rule.conclusion.data == (("concept", "snell_descartes"),)
    with pytest.raises(FrozenInstanceError):
        rule.priority = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        rule.conclusion.code = "changed"  # type: ignore[misc]


def test_triggered_rule_returns_its_structured_conclusion_and_trace() -> None:
    facts = FactSet(
        (
            Fact(
                "concept:snell",
                FactKind.CONCEPT_MENTION,
                "snell_descartes",
                "mentioned",
            ),
        )
    )

    result = _rule().evaluate(facts)

    assert result.triggered
    assert result.rule_id == "R001"
    assert result.conclusion == _rule().conclusion
    assert result.condition_result.satisfied
    assert len(result.condition_result.children) == 2


def test_non_triggered_rule_has_no_conclusion() -> None:
    facts = FactSet(
        (
            Fact(
                "concept:snell",
                FactKind.CONCEPT_MENTION,
                "snell_descartes",
                "mentioned",
            ),
            Fact(
                "relation:snell",
                FactKind.RELATION,
                "angle",
                "related_to",
                value="indice",
            ),
        )
    )

    result = _rule().evaluate(facts)

    assert not result.triggered
    assert result.conclusion is None
    assert not result.condition_result.satisfied


def test_rule_evaluation_rejects_inconsistent_conclusion_state() -> None:
    condition_result = SubjectExists("x").evaluate(FactSet())

    with pytest.raises(ValueError, match="si et seulement"):
        RuleEvaluation("R", False, condition_result, RuleConclusion("unexpected"))


def test_custom_rule_works_with_concept_extractor_output() -> None:
    glossary = Glossary(
        "custom",
        "Personnalisé",
        (ScientificTerm("oscilloscope", "oscilloscope", "instrument"),),
    )
    facts = ConceptExtractor(glossary).extract("Observer avec l'oscilloscope.")
    rule = Rule(
        id="CUSTOM",
        label="Instrument cité",
        condition=SubjectExists("oscilloscope"),
        conclusion=RuleConclusion("instrument_mentioned"),
    )

    result = rule.evaluate(facts)

    assert result.triggered
    assert result.condition_result.contributing_facts == tuple(facts)


def test_rule_on_empty_fact_set_does_not_trigger() -> None:
    result = _rule().evaluate(FactSet())

    assert not result.triggered
    assert result.conclusion is None


def test_legacy_rule_stays_constructible_but_cannot_be_evaluated() -> None:
    legacy_condition = object()
    legacy_rule = Rule("LEGACY", "Ancienne règle", [legacy_condition])  # type: ignore[arg-type]

    assert legacy_rule.conditions == (legacy_condition,)
    with pytest.raises(NotImplementedError, match="migrées avant leur évaluation"):
        legacy_rule.evaluate(FactSet())

    current_rule = _rule()
    current_result = current_rule.evaluate(FactSet())
    assert current_result.triggered is False
    assert current_result.conclusion is None
