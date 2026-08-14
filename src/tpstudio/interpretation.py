"""Conservative review of explicitly marked interpretation responses."""

from __future__ import annotations

import hashlib
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

    def to_dict(self) -> dict[str, object]:
        return {
            "expectation_id": self.expectation_id,
            "manipulation_id": self.manipulation_id,
            "local_prompt": self.local_prompt,
            "local_scientific_context": list(self.local_scientific_context),
            "linked_protocol": self.linked_protocol,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "InterpretationContext":
        return cls(
            str(payload["expectation_id"]),
            str(payload["manipulation_id"]) if payload.get("manipulation_id") is not None else None,
            str(payload["local_prompt"]) if payload.get("local_prompt") is not None else None,
            tuple(str(item) for item in payload.get("local_scientific_context", ())),
            str(payload.get("linked_protocol", "")),
        )


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
    schema_version: int
    copy_id: str
    copy_sha256: str
    expectation_id: str
    cell_id: str
    cell_index_snapshot: int | None
    student_answer: str
    local_context: InterpretationContext
    tpstudio_proposal: InterpretationClassification | None
    tpstudio_feedback: str | None
    teacher_decision: InterpretationClassification | None = None
    teacher_feedback: str | None = None
    reviewed_at: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Version de trace d'interprétation non prise en charge.")
        for name in ("copy_id", "copy_sha256", "expectation_id", "cell_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} ne peut pas être vide.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.copy_sha256):
            raise ValueError("copy_sha256 doit être un SHA-256 hexadécimal.")
        if self.cell_index_snapshot is not None and (not isinstance(self.cell_index_snapshot, int) or self.cell_index_snapshot < 0):
            raise ValueError("cell_index_snapshot est invalide.")
        if not isinstance(self.local_context, InterpretationContext):
            raise TypeError("local_context doit être une InterpretationContext.")
        if self.tpstudio_proposal is not None and type(self.tpstudio_proposal) is not InterpretationClassification:
            raise TypeError("La proposition TPStudio est invalide.")
        if self.teacher_decision is not None and type(self.teacher_decision) is not InterpretationClassification:
            raise TypeError("La décision enseignant est invalide.")
        if self.teacher_decision is None and self.reviewed_at is not None:
            raise ValueError("reviewed_at doit être absent pour une trace PENDING.")
        if self.teacher_decision is not None and (not isinstance(self.reviewed_at, str) or not self.reviewed_at.strip()):
            raise ValueError("reviewed_at est requis pour une décision enseignant.")

    @property
    def review_status(self) -> str:
        if self.teacher_decision is None:
            return "PENDING"
        if self.teacher_decision is self.tpstudio_proposal:
            return "CONFIRMED"
        return "REPLACED"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "copy_id": self.copy_id,
            "copy_sha256": self.copy_sha256,
            "expectation_id": self.expectation_id,
            "cell_id": self.cell_id,
            "cell_index_snapshot": self.cell_index_snapshot,
            "student_answer": self.student_answer,
            "local_context": self.local_context.to_dict(),
            "tpstudio_proposal": self.tpstudio_proposal.name if self.tpstudio_proposal else None,
            "tpstudio_feedback": self.tpstudio_feedback,
            "teacher_decision": self.teacher_decision.name if self.teacher_decision else None,
            "teacher_feedback": self.teacher_feedback,
            "reviewed_at": self.reviewed_at,
            "review_status": self.review_status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "InterpretationReviewTrace":
        def classification(value: object) -> InterpretationClassification | None:
            return InterpretationClassification[str(value)] if value is not None else None

        return cls(
            int(payload["schema_version"]), str(payload["copy_id"]), str(payload["copy_sha256"]),
            str(payload["expectation_id"]), str(payload["cell_id"]),
            int(payload["cell_index_snapshot"]) if payload.get("cell_index_snapshot") is not None else None,
            str(payload["student_answer"]), InterpretationContext.from_dict(payload["local_context"]),
            classification(payload.get("tpstudio_proposal")),
            str(payload["tpstudio_feedback"]) if payload.get("tpstudio_feedback") is not None else None,
            classification(payload.get("teacher_decision")),
            str(payload["teacher_feedback"]) if payload.get("teacher_feedback") is not None else None,
            str(payload["reviewed_at"]) if payload.get("reviewed_at") is not None else None,
        )


def _fallback_cell_id(cell: NotebookNode, expectation_id: str, occurrence: int) -> str:
    """Build a stable legacy key; identical duplicate cells still depend on order."""
    role = cell.get("metadata", {}).get("tpstudio", {}).get("role", "")
    material = "|".join((expectation_id, str(role), str(cell.get("source", "")), str(occurrence)))
    return "fallback:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def build_interpretation_review_traces(
    notebook: NotebookNode,
    evaluations: tuple[InterpretationEvaluation, ...],
    contexts: dict[object, InterpretationContext],
    feedback: tuple[InterpretationFeedbackItem, ...],
    *,
    copy_id: str,
    copy_sha256: str,
) -> tuple[InterpretationReviewTrace, ...]:
    feedback_by_key = {(item.expectation_id, item.cell_index): item.text for item in feedback}
    occurrences: dict[str, int] = {}
    traces = []
    for evaluation in evaluations:
        index = evaluation.cell_index
        cell = notebook.cells[index] if index is not None and index < len(notebook.cells) else None
        if cell is None:
            continue
        expectation_id = evaluation.expectation_id
        occurrence = occurrences.get(expectation_id, 0) + 1
        occurrences[expectation_id] = occurrence
        raw_id = cell.get("id")
        cell_id = str(raw_id) if isinstance(raw_id, str) and raw_id.strip() else _fallback_cell_id(cell, expectation_id, occurrence)
        context = contexts.get((expectation_id, index))
        if context is None:
            context = contexts.get(expectation_id, InterpretationContext(expectation_id))
        traces.append(InterpretationReviewTrace(
            1, copy_id, copy_sha256, expectation_id, cell_id, index,
            str(cell.get("source", "")), context,
            evaluation.classification, feedback_by_key.get((expectation_id, index)),
        ))
    return tuple(traces)


def build_interpretation_contexts(notebook: NotebookNode) -> dict[object, InterpretationContext]:
    contexts: dict[object, InterpretationContext] = {}
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
        context = InterpretationContext(
            expectation_id, str(manipulation_id) if manipulation_id is not None else None,
            prompt, tuple(scientific[-3:]), protocol,
        )
        contexts[(expectation_id, index)] = context
        contexts.setdefault(expectation_id, context)
    return contexts


def _classify(source: str, context: InterpretationContext) -> InterpretationClassification:
    text = " ".join(source.split()).strip()
    normalized = text.lower()
    if len(re.findall(r"\w+", text)) < 4:
        return InterpretationClassification.CLEARLY_INSUFFICIENT
    if re.fullmatch(r"(?:le |la |les )?(?:graphe|courbe|résultats?) (?:est|sont) (?:correct|bons?|bonnes?)\.?", normalized):
        return InterpretationClassification.CLEARLY_INSUFFICIENT

    # These are deliberately broad linguistic roots, not a TP vocabulary.
    # They separate an observed quantity, a qualitative comparison, and an
    # explicit scientific criterion without turning the decision into a score.
    has_observation = bool(re.search(
        r"\b(valeur|résultat\w*|resultat\w*|mesur\w*|écart|ecart|courb\w*|graph\w*|"
        r"tendanc\w*|pente|augment\w*|diminu\w*)\b",
        normalized,
    ))
    has_comparison = bool(re.search(
        r"\b(proch\w*|supérieur\w*|superieur\w*|inférieur\w*|inferieur\w*|"
        r"attendu\w*|théor\w*|theor\w*|constructeur|raisonn\w*|"
        r"faible|grand\w*|petit\w*)\b",
        normalized,
    ))
    has_criterion = bool(re.search(
        r"écart\s+normalisé|ecart\s+normalise|\bseuil\b|\bincertitude\w*\b|"
        r"\bconstructeur\b",
        normalized,
    ))
    has_link = bool(re.search(
        r"\b(donc|ainsi|car|comme|puisque|ce qui|permet\w*|montre\w*|"
        r"signifie\w*|interpr\w*|valide\w*)\b",
        normalized,
    ))
    has_conclusion = bool(re.search(
        r"\b(compatible\w*|cohérent\w*|coherent\w*|accord\w*|"
        r"satisfais\w*|correct\w*)\b",
        normalized,
    ))
    is_hedged = bool(re.search(r"\b(sembl\w*|para[iî]t\w*)\b", normalized))
    has_context = bool(context.local_scientific_context or context.linked_protocol)
    if has_observation and has_criterion and has_context and (has_link or has_conclusion):
        return InterpretationClassification.CLEARLY_SUFFICIENT
    # An unqualified evaluative assertion is not an interpretation, whereas
    # a hedged or comparative statement is useful but incomplete.
    if has_observation and has_conclusion and not has_comparison and not has_criterion and not has_link and not is_hedged:
        return InterpretationClassification.CLEARLY_INSUFFICIENT
    if has_observation and (has_comparison or is_hedged):
        return InterpretationClassification.AMBIGUOUS
    if has_observation and not has_link and not has_conclusion:
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
