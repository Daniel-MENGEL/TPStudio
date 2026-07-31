from dataclasses import FrozenInstanceError

import pytest

from tpstudio.reasoning import (
    Diagnostic,
    DiagnosticCategory,
    DiagnosticDefinition,
    DiagnosticRegistry,
    DiagnosticSet,
    DiagnosticSeverity,
    Fact,
    FactKind,
    RuleConclusion,
)


def _diagnostic(
    code: str,
    *,
    rule_id: str,
    severity: DiagnosticSeverity = DiagnosticSeverity.WARNING,
    category: DiagnosticCategory = DiagnosticCategory.MISSING_ELEMENT,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        category=category,
        severity=severity,
        message_key=f"diagnostic.{code}",
        rule_id=rule_id,
        conclusion=RuleConclusion(code),
    )


def _definition(code: str = "relation_missing") -> DiagnosticDefinition:
    return DiagnosticDefinition(
        conclusion_code=code,
        diagnostic_code=code,
        category=DiagnosticCategory.MISSING_ELEMENT,
        severity=DiagnosticSeverity.WARNING,
        message_key=f"diagnostic.{code}",
    )


def test_diagnostic_is_structured_immutable_and_keeps_evidence() -> None:
    fact = Fact("concept:laser", FactKind.CONCEPT_MENTION, "laser", "mentioned")
    conclusion = RuleConclusion("relation_missing", data=(("medium", "air"),))
    diagnostic = Diagnostic(
        code="relation_missing",
        category=DiagnosticCategory.MISSING_ELEMENT,
        severity=DiagnosticSeverity.WARNING,
        message_key="diagnostic.relation_missing",
        rule_id="R001",
        conclusion=conclusion,
        evidence=(fact,),
        subject="snell_descartes",
        metadata=(("source", "registry"),),
    )

    assert diagnostic.conclusion is conclusion
    assert diagnostic.evidence == (fact,)
    assert diagnostic.subject == "snell_descartes"
    assert diagnostic.metadata == (("source", "registry"),)
    assert diagnostic.conclusion_data == (("medium", "air"),)
    with pytest.raises(FrozenInstanceError):
        diagnostic.code = "changed"  # type: ignore[misc]


def test_empty_diagnostic_set_supports_collection_protocol() -> None:
    diagnostics = DiagnosticSet()

    assert not diagnostics
    assert len(diagnostics) == 0
    assert list(diagnostics) == []
    assert diagnostics[:] == ()


def test_diagnostic_set_preserves_order_filters_and_duplicates() -> None:
    first = _diagnostic("same", rule_id="R1")
    second = _diagnostic(
        "precision",
        rule_id="R2",
        severity=DiagnosticSeverity.INFO,
        category=DiagnosticCategory.PRECISION,
    )
    third = _diagnostic("same", rule_id="R3")
    diagnostics = DiagnosticSet((first, second, third))

    assert diagnostics[0] is first
    assert list(diagnostics) == [first, second, third]
    assert list(diagnostics.by_severity(DiagnosticSeverity.WARNING)) == [first, third]
    assert list(diagnostics.by_category(DiagnosticCategory.PRECISION)) == [second]
    assert list(diagnostics.by_code("same")) == [first, third]
    assert list(diagnostics.by_rule_id("R3")) == [third]


def test_registry_can_be_empty_and_find_a_definition() -> None:
    definition = _definition()

    assert len(DiagnosticRegistry()) == 0
    registry = DiagnosticRegistry((definition,))
    assert tuple(registry) == (definition,)
    assert registry.get("relation_missing") is definition
    assert registry.get("unknown") is None


def test_registry_rejects_ambiguous_conclusion_code() -> None:
    with pytest.raises(ValueError, match="Une seule définition"):
        DiagnosticRegistry((_definition(), _definition()))
