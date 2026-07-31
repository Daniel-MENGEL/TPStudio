from dataclasses import FrozenInstanceError

import pytest

from tpstudio.glossary import Glossary, ScientificTerm
from tpstudio.reasoning import (
    ConceptExtractor,
    Condition,
    Fact,
    FactKind,
    FactKindExists,
    FactSet,
    InferenceEngine,
    InferenceResult,
    Rule,
    RuleConclusion,
    RuleSet,
    SubjectExists,
)


def _fact(subject: str = "laser") -> Fact:
    return Fact(
        id=f"concept:{subject}",
        kind=FactKind.CONCEPT_MENTION,
        subject=subject,
        predicate="mentioned",
    )


def _rule(
    identifier: str,
    subject: str,
    *,
    code: str | None = None,
    priority: int = 0,
) -> Rule:
    return Rule(
        id=identifier,
        label=identifier,
        condition=SubjectExists(subject),
        conclusion=RuleConclusion(code or f"conclusion:{identifier}"),
        priority=priority,
    )


def test_empty_rule_set_produces_an_empty_immutable_result() -> None:
    result = InferenceEngine().evaluate(FactSet(), RuleSet())

    assert result == InferenceResult(())
    assert result.evaluations == ()
    assert result.triggered == ()
    assert result.not_triggered == ()
    assert result.conclusions == ()
    assert result.total == result.total_evaluated == 0
    with pytest.raises(FrozenInstanceError):
        result.evaluations = ()  # type: ignore[misc]


def test_result_normalizes_its_evaluation_collection_to_a_tuple() -> None:
    result = InferenceResult([])  # type: ignore[arg-type]

    assert result.evaluations == ()
    assert isinstance(result.evaluations, tuple)


def test_empty_fact_set_records_a_non_triggered_rule_without_conclusion() -> None:
    result = InferenceEngine().evaluate(
        FactSet(),
        RuleSet((_rule("R1", "laser"),)),
    )

    assert result.total == 1
    assert result.triggered == ()
    assert [evaluation.rule_id for evaluation in result.not_triggered] == ["R1"]
    assert result.evaluations[0].conclusion is None
    assert result.conclusions == ()


def test_all_rules_are_evaluated_in_ruleset_order_after_a_trigger() -> None:
    rules = RuleSet(
        (
            _rule("R1", "laser", priority=-5),
            _rule("R2", "absent", priority=100),
            _rule("R3", "laser", priority=0),
        )
    )

    result = InferenceEngine().evaluate(FactSet((_fact(),)), rules)

    assert [evaluation.rule_id for evaluation in result.evaluations] == [
        "R1",
        "R2",
        "R3",
    ]
    assert [evaluation.rule_id for evaluation in result.triggered] == ["R1", "R3"]
    assert [evaluation.rule_id for evaluation in result.not_triggered] == ["R2"]
    assert result.total == 3


def test_conclusions_keep_order_and_duplicate_codes() -> None:
    rules = RuleSet(
        (
            _rule("R1", "laser", code="same"),
            _rule("R2", "absent", code="not-produced"),
            _rule("R3", "laser", code="same"),
        )
    )

    result = InferenceEngine().evaluate(FactSet((_fact(),)), rules)

    assert [conclusion.code for conclusion in result.conclusions] == ["same", "same"]


class _ExplodingCondition(Condition):
    def evaluate(self, facts: FactSet):  # type: ignore[no-untyped-def]
        raise RuntimeError("condition failure")


def test_rule_exception_is_propagated_and_later_rules_are_not_evaluated() -> None:
    exploding = Rule(
        "BROKEN",
        _ExplodingCondition(),
        RuleConclusion("never-produced"),
    )
    rules = RuleSet((exploding, _rule("LATER", "laser")))

    with pytest.raises(RuntimeError, match="condition failure"):
        InferenceEngine().evaluate(FactSet((_fact(),)), rules)


def test_legacy_rule_not_implemented_error_is_propagated() -> None:
    legacy = Rule("LEGACY", "Ancienne règle", [object()])  # type: ignore[arg-type]

    with pytest.raises(NotImplementedError, match="migrées avant leur évaluation"):
        InferenceEngine().evaluate(FactSet(), RuleSet((legacy,)))


def test_two_identical_evaluations_are_deterministic() -> None:
    facts = FactSet((_fact(),))
    rules = RuleSet((_rule("R1", "laser"), _rule("R2", "absent")))
    engine = InferenceEngine()

    assert engine.evaluate(facts, rules) == engine.evaluate(facts, rules)


def test_inputs_are_not_mutated() -> None:
    fact = _fact()
    rule = _rule("R1", "laser")
    facts = FactSet((fact,))
    rules = RuleSet((rule,))

    InferenceEngine().evaluate(facts, rules)

    assert tuple(facts) == (fact,)
    assert tuple(rules) == (rule,)


def test_engine_accepts_facts_produced_by_concept_extractor() -> None:
    glossary = Glossary(
        "custom",
        "Personnalisé",
        (ScientificTerm("laser", "laser", "instrument"),),
    )
    facts = ConceptExtractor(glossary).extract("Utiliser le laser.")
    rules = RuleSet((_rule("R1", "laser"),))

    result = InferenceEngine().evaluate(facts, rules)

    assert [evaluation.rule_id for evaluation in result.triggered] == ["R1"]
    assert result.conclusions == (RuleConclusion("conclusion:R1"),)


def test_rule_kind_condition_can_be_evaluated_globally() -> None:
    rule = Rule(
        "RELATION",
        FactKindExists(FactKind.RELATION),
        RuleConclusion("relation_present"),
    )

    result = InferenceEngine().evaluate(FactSet((_fact(),)), RuleSet((rule,)))

    assert not result.evaluations[0].triggered
