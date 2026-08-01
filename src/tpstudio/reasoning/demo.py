"""Generic end-to-end orchestration and development rendering."""

from __future__ import annotations

from dataclasses import dataclass

from .diagnostic_builder import DiagnosticBuilder
from .diagnostics import DiagnosticSet
from .enums import FactKind
from .extractor import ConceptExtractor
from .facts import Fact
from .inference import InferenceEngine, InferenceResult
from .rule_set import RuleSet


@dataclass(frozen=True, slots=True)
class EndToEndCase:
    """One immutable student-answer scenario for integration development."""

    case_id: str
    student_answer: str
    description: str | None = None
    expected_diagnostic_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EndToEndReport:
    """Immutable snapshot of every stage after text extraction."""

    case: EndToEndCase
    facts: tuple[Fact, ...]
    inference_result: InferenceResult
    diagnostics: DiagnosticSet

    @property
    def detected_concepts(self) -> tuple[str, ...]:
        return tuple(
            fact.subject
            for fact in self.facts
            if fact.kind is FactKind.CONCEPT_MENTION
        )


def run_end_to_end_case(
    case: EndToEndCase,
    *,
    extractor: ConceptExtractor,
    rules: RuleSet,
    diagnostic_builder: DiagnosticBuilder,
) -> EndToEndReport:
    """Run the existing deterministic pipeline without adding any facts."""

    fact_set = extractor.extract(case.student_answer)
    inference_result = InferenceEngine().evaluate(fact_set, rules)
    diagnostics = diagnostic_builder.build(inference_result)
    return EndToEndReport(
        case=case,
        facts=tuple(fact_set),
        inference_result=inference_result,
        diagnostics=diagnostics,
    )


def format_end_to_end_report(report: EndToEndReport) -> str:
    """Return a stable, ANSI-free development view of an end-to-end report."""

    lines = [
        f"Case: {report.case.case_id}",
        f"Description: {report.case.description or '-'}",
        f"Student answer: {report.case.student_answer}",
        "Detected facts:",
    ]
    if report.facts:
        for fact in report.facts:
            excerpt = fact.evidence.excerpt if fact.evidence is not None else "-"
            lines.append(
                f"  - {fact.id} | {fact.kind.value} | subject={fact.subject} "
                f"| evidence={excerpt!r}"
            )
    else:
        lines.append("  - none")

    lines.append("Triggered rules:")
    if report.inference_result.triggered:
        lines.extend(
            f"  - {evaluation.rule_id}"
            for evaluation in report.inference_result.triggered
        )
    else:
        lines.append("  - none")

    lines.append("Not triggered rules:")
    if report.inference_result.not_triggered:
        lines.extend(
            f"  - {evaluation.rule_id}"
            for evaluation in report.inference_result.not_triggered
        )
    else:
        lines.append("  - none")

    lines.append("Diagnostics:")
    if report.diagnostics:
        for diagnostic in report.diagnostics:
            lines.append(
                f"  - {diagnostic.code} | {diagnostic.severity.value} "
                f"| rule={diagnostic.rule_id} | key={diagnostic.message_key}"
            )
            if diagnostic.evidence:
                for fact in diagnostic.evidence:
                    excerpt = fact.evidence.excerpt if fact.evidence is not None else "-"
                    lines.append(
                        f"    evidence: subject={fact.subject} excerpt={excerpt!r}"
                    )
            else:
                lines.append("    evidence: none")
    else:
        lines.append("  - none")

    return "\n".join(lines)
