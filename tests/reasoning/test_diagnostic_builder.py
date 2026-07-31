from tpstudio.reasoning import (
    Condition,
    ConditionResult,
    DiagnosticBuilder,
    DiagnosticCategory,
    DiagnosticDefinition,
    DiagnosticRegistry,
    DiagnosticSeverity,
    Fact,
    FactKind,
    FactSet,
    InferenceEngine,
    Rule,
    RuleConclusion,
    RuleSet,
    SubjectExists,
    UnknownDiagnosticDefinitionError,
)

import pytest


def _definition(
    conclusion_code: str,
    *,
    diagnostic_code: str | None = None,
) -> DiagnosticDefinition:
    return DiagnosticDefinition(
        conclusion_code=conclusion_code,
        diagnostic_code=diagnostic_code or conclusion_code,
        category=DiagnosticCategory.MISSING_ELEMENT,
        severity=DiagnosticSeverity.WARNING,
        message_key=f"diagnostic.{conclusion_code}",
        subject="optics",
        metadata=(("source", "registry"),),
    )


def _rule(identifier: str, subject: str, conclusion_code: str) -> Rule:
    return Rule(
        identifier,
        SubjectExists(subject),
        RuleConclusion(conclusion_code, data=(("source", subject),)),
    )


def _facts() -> FactSet:
    return FactSet(
        (
            Fact("concept:laser", FactKind.CONCEPT_MENTION, "laser", "mentioned"),
            Fact(
                "concept:plexiglas",
                FactKind.CONCEPT_MENTION,
                "plexiglas",
                "mentioned",
            ),
        )
    )


def test_builder_only_transforms_triggered_rules_in_order() -> None:
    rules = RuleSet(
        (
            _rule("R1", "laser", "first"),
            _rule("R2", "absent", "not_produced"),
            _rule("R3", "plexiglas", "third"),
        )
    )
    inference = InferenceEngine().evaluate(_facts(), rules)
    registry = DiagnosticRegistry((_definition("first"), _definition("third")))

    diagnostics = DiagnosticBuilder(registry).build(inference)

    assert [item.code for item in diagnostics] == ["first", "third"]
    assert [item.rule_id for item in diagnostics] == ["R1", "R3"]
    assert [item.conclusion.code for item in diagnostics] == ["first", "third"]


def test_builder_preserves_payload_defaults_and_contributing_facts() -> None:
    facts = _facts()
    inference = InferenceEngine().evaluate(
        facts,
        RuleSet((_rule("R1", "laser", "relation_missing"),)),
    )

    diagnostic = DiagnosticBuilder(
        DiagnosticRegistry((_definition("relation_missing"),))
    ).build(inference)[0]

    assert diagnostic.subject == "optics"
    assert diagnostic.metadata == (("source", "registry"),)
    assert diagnostic.conclusion_data == (("source", "laser"),)
    assert [fact.subject for fact in diagnostic.evidence] == ["laser"]
    assert diagnostic.evidence == inference.triggered[0].condition_result.contributing_facts


def test_unknown_conclusion_raises_a_dedicated_error() -> None:
    inference = InferenceEngine().evaluate(
        _facts(),
        RuleSet((_rule("R1", "laser", "unknown"),)),
    )

    with pytest.raises(UnknownDiagnosticDefinitionError) as raised:
        DiagnosticBuilder(DiagnosticRegistry()).build(inference)

    assert raised.value.conclusion_code == "unknown"


class _CountingCondition(Condition):
    __slots__ = ("calls",)

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def evaluate(self, facts: FactSet) -> ConditionResult:
        self.calls += 1
        return ConditionResult(True, tuple(facts))


def test_builder_does_not_reevaluate_rules_or_mutate_inference() -> None:
    condition = _CountingCondition()
    rule = Rule("R1", condition, RuleConclusion("known"))
    inference = InferenceEngine().evaluate(_facts(), RuleSet((rule,)))
    evaluations_before = inference.evaluations
    builder = DiagnosticBuilder(DiagnosticRegistry((_definition("known"),)))

    first = builder.build(inference)
    second = builder.build(inference)

    assert condition.calls == 1
    assert inference.evaluations is evaluations_before
    assert first == second


def test_non_triggered_rule_needs_no_registry_definition() -> None:
    inference = InferenceEngine().evaluate(
        FactSet(),
        RuleSet((_rule("R1", "absent", "unregistered"),)),
    )

    assert not DiagnosticBuilder(DiagnosticRegistry()).build(inference)
