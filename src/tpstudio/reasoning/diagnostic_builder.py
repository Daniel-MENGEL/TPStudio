"""Transformation of inference traces into pedagogical diagnostics."""

from __future__ import annotations

from .diagnostics import (
    Diagnostic,
    DiagnosticRegistry,
    DiagnosticSet,
    UnknownDiagnosticDefinitionError,
)
from .inference import InferenceResult


class DiagnosticBuilder:
    """Build diagnostics from already evaluated, triggered rules only."""

    def __init__(self, registry: DiagnosticRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> DiagnosticRegistry:
        return self._registry

    def build(self, inference_result: InferenceResult) -> DiagnosticSet:
        diagnostics: list[Diagnostic] = []
        for evaluation in inference_result.triggered:
            conclusion = evaluation.conclusion
            if conclusion is None:  # Protected by RuleEvaluation's invariant.
                continue
            definition = self._registry.get(conclusion.code)
            if definition is None:
                raise UnknownDiagnosticDefinitionError(conclusion.code)
            diagnostics.append(
                Diagnostic(
                    code=definition.diagnostic_code,
                    category=definition.category,
                    severity=definition.severity,
                    message_key=definition.message_key,
                    rule_id=evaluation.rule_id,
                    conclusion=conclusion,
                    evidence=evaluation.condition_result.contributing_facts,
                    subject=definition.subject,
                    metadata=definition.metadata,
                    conclusion_data=conclusion.data,
                )
            )
        return DiagnosticSet(tuple(diagnostics))
