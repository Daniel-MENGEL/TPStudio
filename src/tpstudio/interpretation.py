"""Conservative review of explicitly marked interpretation responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from nbformat.notebooknode import NotebookNode

from tpstudio.feedback import FeedbackAudience, FeedbackPriority
from tpstudio.protocol import ProtocolStatus, is_empty_or_placeholder


class InterpretationClassification(str, Enum):
    CLEARLY_SUFFICIENT = "clearly_sufficient"
    CLEARLY_INSUFFICIENT = "clearly_insufficient"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class InterpretationContext:
    expectation_id: str
    manipulation_id: str | None = None
    local_prompt: str | None = None
    local_scientific_context: tuple[str, ...] = ()
    linked_protocol: str = ""

    @property
    def reference_text(self) -> str:
        return " ".join(filter(None, (self.local_prompt, *self.local_scientific_context, self.linked_protocol)))


@dataclass(frozen=True, slots=True)
class InterpretationEvaluation:
    expectation_id: str
    status: ProtocolStatus
    classification: InterpretationClassification | None
    cell_index: int | None = None
    cell_type: str | None = None
    requires_human_review: bool = False


@dataclass(frozen=True, slots=True)
class InterpretationDiagnostic:
    expectation_id: str
    status: ProtocolStatus
    classification: InterpretationClassification | None
    cell_index: int | None
    code: str
    message_key: str
    source: str = "interpretation-cell"


@dataclass(frozen=True, slots=True)
class InterpretationFeedbackItem:
    expectation_id: str
    text: str
    cell_index: int
    cell_type: str = "markdown"
    audience: FeedbackAudience = FeedbackAudience.STUDENT
    priority: FeedbackPriority = FeedbackPriority.NORMAL
    code: str = "INTERPRETATION_REVIEW"

    @property
    def message_key(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class InterpretationReviewTrace:
    student_answer: str
    local_context: InterpretationContext
    tpstudio_proposal: InterpretationClassification | None
    teacher_decision: str | None = None
    teacher_feedback: str | None = None


def build_interpretation_contexts(notebook: NotebookNode) -> dict[str, InterpretationContext]:
    contexts: dict[str, InterpretationContext] = {}
    for index, cell in enumerate(notebook.cells):
        tp = cell.get("metadata", {}).get("tpstudio", {})
        if not isinstance(tp, dict) or tp.get("role") != "interpretation_response":
            continue
        expectation_id = str(tp.get("expectation_id", f"interpretation-{index}"))
        manipulation_id = tp.get("manipulation_id")
        prompt: str | None = None
        if index and notebook.cells[index - 1].get("cell_type") == "markdown":
            previous = notebook.cells[index - 1]
            previous_tp = previous.get("metadata", {}).get("tpstudio", {})
            previous_role = previous_tp.get("role") if isinstance(previous_tp, dict) else None
            if previous_role is None or previous_role in {"interpretation_prompt", "prompt"}:
                prompt = str(previous.get("source", ""))
        scientific: list[str] = []
        protocol = ""
        for prior in notebook.cells[:index]:
            prior_tp = prior.get("metadata", {}).get("tpstudio", {})
            role = prior_tp.get("role") if isinstance(prior_tp, dict) else None
            if role in {"result_response", "production_response"}:
                scientific.append(str(prior.get("source", "")))
            elif role == "interpretation_response":
                linked = prior_tp.get("manipulation_id") if isinstance(prior_tp, dict) else None
                if linked and linked == manipulation_id:
                    scientific.append(str(prior.get("source", "")))
            elif role == "protocol_response":
                linked = prior_tp.get("manipulation_id") if isinstance(prior_tp, dict) else None
                linked_expectation = prior_tp.get("expectation_id") if isinstance(prior_tp, dict) else None
                if (manipulation_id and linked == manipulation_id) or linked_expectation == expectation_id:
                    protocol = str(prior.get("source", ""))
        contexts[expectation_id] = InterpretationContext(
            expectation_id, str(manipulation_id) if manipulation_id is not None else None,
            prompt, tuple(scientific[-3:]), protocol,
        )
    return contexts


def _classify(source: str, context: InterpretationContext) -> InterpretationClassification:
    text = " ".join(source.split()).strip()
    normalized = text.lower()
    if len(re.findall(r"\w+", text)) < 4:
        return InterpretationClassification.CLEARLY_INSUFFICIENT
    if re.fullmatch(r"(?:le |la |les )?(?:graphe|courbe|résultats?) (?:est|sont) (?:correct|bons?|bonnes?)\.?", normalized):
        return InterpretationClassification.CLEARLY_INSUFFICIENT
    has_link = bool(re.search(r"\b(donc|ainsi|car|compatible|cohérent|coherent|inférieur|superieur|montre|signifie|interpr|valide|théor|theor|accord)\b", normalized))
    has_observation = bool(re.search(r"\b(valeur|résultat|resultat|mesure|écart|ecart|courbe|graphe|tendance|pente|augmente|diminue)\b", normalized))
    has_context = bool(context.local_scientific_context or context.linked_protocol)
    if has_observation and has_link and has_context and not re.search(r"\b(faible|bon|bonne|bons|correct)\b", normalized):
        return InterpretationClassification.CLEARLY_SUFFICIENT
    if has_observation and re.search(r"\b(faible|bon|bonne|bons|correct)\b", normalized):
        return InterpretationClassification.AMBIGUOUS
    if has_observation and not has_link:
        return InterpretationClassification.CLEARLY_INSUFFICIENT
    return InterpretationClassification.AMBIGUOUS


def evaluate_interpretation_cells(
    notebook: NotebookNode,
    *,
    contexts: dict[str, InterpretationContext] | None = None,
) -> tuple[InterpretationEvaluation, ...]:
    values: list[InterpretationEvaluation] = []
    contexts = contexts or {}
    for index, cell in enumerate(notebook.cells):
        tp = cell.get("metadata", {}).get("tpstudio", {})
        if not isinstance(tp, dict) or tp.get("role") != "interpretation_response":
            continue
        expectation_id = str(tp.get("expectation_id", f"interpretation-{index}"))
        if cell.get("cell_type") != "markdown" or not isinstance(cell.get("source"), str):
            values.append(InterpretationEvaluation(expectation_id, ProtocolStatus.NOT_EVALUABLE, None, index, cell.get("cell_type"), True))
        elif is_empty_or_placeholder(cell["source"]):
            values.append(InterpretationEvaluation(expectation_id, ProtocolStatus.MISSING, None, index, "markdown", False))
        else:
            context = contexts.get(expectation_id, InterpretationContext(expectation_id))
            classification = _classify(cell["source"], context)
            values.append(InterpretationEvaluation(expectation_id, ProtocolStatus.PRESENT, classification, index, "markdown", classification is InterpretationClassification.AMBIGUOUS))
    return tuple(values)


def build_interpretation_diagnostics(evaluations):
    values = []
    for item in evaluations:
        if item.status is ProtocolStatus.MISSING:
            values.append(InterpretationDiagnostic(item.expectation_id, item.status, None, item.cell_index, "INTERPRETATION_MISSING", "L'interprétation n'est pas renseignée."))
        elif item.status is ProtocolStatus.NOT_EVALUABLE:
            values.append(InterpretationDiagnostic(item.expectation_id, item.status, None, item.cell_index, "INTERPRETATION_NOT_EVALUABLE", "L'interprétation ne peut pas être évaluée automatiquement."))
        elif item.classification is InterpretationClassification.AMBIGUOUS:
            values.append(InterpretationDiagnostic(item.expectation_id, item.status, item.classification, item.cell_index, "INTERPRETATION_AMBIGUOUS", "L'interprétation nécessite une revue humaine."))
        elif item.classification is InterpretationClassification.CLEARLY_INSUFFICIENT:
            values.append(InterpretationDiagnostic(item.expectation_id, item.status, item.classification, item.cell_index, "INTERPRETATION_INSUFFICIENT", "L'interprétation décrit le résultat sans l'expliquer suffisamment."))
    return tuple(values)


def build_interpretation_feedback(evaluations):
    values = []
    for item in evaluations:
        if item.cell_index is None or item.status is not ProtocolStatus.PRESENT:
            continue
        if item.classification is InterpretationClassification.CLEARLY_SUFFICIENT:
            text = "Interprétation pertinente : le résultat est relié à son contexte scientifique."
        elif item.classification is InterpretationClassification.CLEARLY_INSUFFICIENT:
            text = "Interprétation insuffisante : le résultat est décrit mais pas suffisamment expliqué."
        else:
            continue
        values.append(InterpretationFeedbackItem(item.expectation_id, text, item.cell_index))
    return tuple(values)
