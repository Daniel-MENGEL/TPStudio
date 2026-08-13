"""Small, deterministic evaluation of explicitly marked conclusion cells."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

from nbformat.notebooknode import NotebookNode

from tpstudio.feedback import FeedbackAudience, FeedbackPriority
from tpstudio.protocol import ProtocolStatus, is_empty_or_placeholder


class ConclusionQuality(str, Enum):
    TB = "TB"
    B = "B"
    AB = "AB"
    A_REVOIR = "À revoir"


@dataclass(frozen=True, slots=True)
class ConclusionContext:
    """Non-student context used to judge a marked conclusion response."""
    objectives: tuple[str, ...] = ()
    local_prompt: str = ""
    prior_results: tuple[str, ...] = ()
    prior_interpretations: tuple[str, ...] = ()

    @property
    def reference_text(self) -> str:
        return " ".join((*self.objectives, self.local_prompt, *self.prior_results, *self.prior_interpretations))


def build_conclusion_contexts(notebook: NotebookNode) -> dict[str, ConclusionContext]:
    """Extract small, role-aware context without merging it into responses."""
    objectives: list[str] = []
    for cell in notebook.cells[:8]:
        source = cell.get("source", "")
        if cell.get("cell_type") == "markdown" and re.search(r"objectif|but du tp|objectifs", source, re.I):
            objectives.append(source)
    contexts: dict[str, ConclusionContext] = {}
    for index, cell in enumerate(notebook.cells):
        tp = cell.get("metadata", {}).get("tpstudio", {})
        if not isinstance(tp, dict) or tp.get("role") != "conclusion_response":
            continue
        expectation_id = str(tp.get("expectation_id", "conclusion-response"))
        prompt = ""
        if index and notebook.cells[index - 1].get("cell_type") == "markdown":
            previous = notebook.cells[index - 1]
            previous_tp = previous.get("metadata", {}).get("tpstudio", {})
            if not (isinstance(previous_tp, dict) and previous_tp.get("role") == "conclusion_response"):
                prompt = str(previous.get("source", ""))
        prior_results: list[str] = []
        for item in notebook.cells[:index]:
            item_tp = item.get("metadata", {}).get("tpstudio", {})
            role = item_tp.get("role") if isinstance(item_tp, dict) else None
            if role == "interpretation_response":
                prior_results.append(str(item.get("source", "")))
            elif role in {"result_response", "production_response"}:
                prior_results.append(str(item.get("source", "")))
        contexts[expectation_id] = ConclusionContext(tuple(objectives), prompt, tuple(prior_results), ())
    return contexts


@dataclass(frozen=True, slots=True)
class ConclusionEvaluation:
    expectation_id: str
    status: ProtocolStatus
    quality: ConclusionQuality | None
    cell_index: int | None = None
    cell_type: str | None = None
    objective_coverage: bool = False
    results_coverage: bool = False
    interpretation: bool = False
    synthesis: bool = False


@dataclass(frozen=True, slots=True)
class ConclusionDiagnostic:
    expectation_id: str
    status: ProtocolStatus
    quality: ConclusionQuality | None
    cell_index: int | None
    code: str
    message_key: str
    source: str = "conclusion-cell"


@dataclass(frozen=True, slots=True)
class ConclusionFeedbackItem:
    expectation_id: str
    text: str
    cell_index: int
    cell_type: str = "markdown"
    audience: FeedbackAudience = FeedbackAudience.STUDENT
    priority: FeedbackPriority = FeedbackPriority.NORMAL
    code: str = "CONCLUSION_EVALUATION"

    @property
    def message_key(self) -> str:
        return self.text


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _body(text: str) -> str:
    text = re.sub(r"(?m)^\s{1,6}#+\s*", "", text)
    text = re.sub(r"[*_`~]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _missing(text: str) -> bool:
    return is_empty_or_placeholder(text)


def _tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-zà-ÿ0-9]{3,}", _norm(text))}


def _evaluate_body(text: str, context: ConclusionContext) -> tuple[ConclusionQuality, bool, bool, bool, bool]:
    body = _body(text)
    normalized = _norm(body)
    words = re.findall(r"[a-zà-ÿ0-9]+", normalized)
    if len(words) < 3:
        return ConclusionQuality.A_REVOIR, False, False, False, False
    response_tokens = _tokens(body)
    reference_tokens = _tokens(context.reference_text)
    overlap = len(response_tokens & reference_tokens)
    objective = bool(context.objectives) and (
        overlap >= 1 or bool(re.search(r"\b(determ|verif|etud|objectif|montre|confir)", normalized))
    )
    results = bool(re.search(r"\b(valeur|obten|compatible|accord|ecart|pente|indice|tau|rc|g|celerite|angle|concord|numerique|doublet)\b", normalized))
    interpretation = bool(
        re.search(r"\b(car|donc|ainsi|ce qui|ce resultat|compatible|coherent|signif|montre|valide|limite|theor)", normalized)
    )
    if not interpretation and not objective:
        results = False
    synthesis = bool(context.objectives and (objective and results and interpretation))
    # A qualitative decision tree keeps the dimensions distinct: a result
    # cannot compensate for absent interpretation, and synthesis is required
    # for the top level.
    if objective and results and interpretation and synthesis and bool(context.prior_results or context.prior_interpretations):
        quality = ConclusionQuality.TB
    elif results and interpretation and (objective or bool(context.objectives)):
        quality = ConclusionQuality.B
    elif objective or results or interpretation:
        quality = ConclusionQuality.AB
    else:
        quality = ConclusionQuality.A_REVOIR
    return quality, objective, results, interpretation, synthesis


def evaluate_conclusion_cells(
    notebook: NotebookNode,
    *,
    context_text: str = "",
    contexts: dict[str, ConclusionContext] | None = None,
) -> tuple[ConclusionEvaluation, ...]:
    """Evaluate only cells whose metadata role is ``conclusion_response``."""
    matches: list[tuple[int, NotebookNode]] = []
    for index, cell in enumerate(notebook.cells):
        tp = cell.get("metadata", {}).get("tpstudio", {})
        if isinstance(tp, dict) and tp.get("role") == "conclusion_response":
            matches.append((index, cell))
    if not matches:
        return ()
    evaluations = []
    for index, cell in matches:
        tp = cell.get("metadata", {}).get("tpstudio", {})
        expectation_id = str(tp.get("expectation_id", f"conclusion-{index}"))
        if cell.get("cell_type") != "markdown" or not isinstance(cell.get("source"), str):
            evaluations.append(ConclusionEvaluation(expectation_id, ProtocolStatus.NOT_EVALUABLE, None, index, cell.get("cell_type")))
        elif _missing(cell["source"]):
            evaluations.append(ConclusionEvaluation(expectation_id, ProtocolStatus.MISSING, None, index, "markdown"))
        else:
            context = (contexts or {}).get(expectation_id, ConclusionContext(local_prompt=context_text))
            quality, objective, results, interpretation, synthesis = _evaluate_body(cell["source"], context)
            evaluations.append(ConclusionEvaluation(expectation_id, ProtocolStatus.PRESENT, quality, index, "markdown", objective, results, interpretation, synthesis))
    return tuple(evaluations)


def build_conclusion_diagnostics(evaluations: tuple[ConclusionEvaluation, ...]) -> tuple[ConclusionDiagnostic, ...]:
    values = []
    for item in evaluations:
        if item.status is ProtocolStatus.MISSING:
            values.append(ConclusionDiagnostic(item.expectation_id, item.status, None, item.cell_index, "CONCLUSION_MISSING", "La conclusion n'est pas renseignée."))
        elif item.status is ProtocolStatus.NOT_EVALUABLE:
            values.append(ConclusionDiagnostic(item.expectation_id, item.status, None, item.cell_index, "CONCLUSION_NOT_EVALUABLE", "La conclusion ne peut pas être évaluée automatiquement."))
    return tuple(values)


def build_conclusion_feedback(evaluations: tuple[ConclusionEvaluation, ...]) -> tuple[ConclusionFeedbackItem, ...]:
    values = []
    for item in evaluations:
        if item.cell_index is None or item.status is ProtocolStatus.NOT_EVALUABLE:
            continue
        if item.status is ProtocolStatus.MISSING:
            text = "La conclusion n'est pas renseignée."
        elif item.quality is ConclusionQuality.TB:
            text = "Conclusion : TB. Les objectifs sont repris, les résultats essentiels sont interprétés et la synthèse est claire."
        elif item.quality is ConclusionQuality.B:
            text = "Conclusion : B. La synthèse est correcte, mais un élément important pourrait être davantage explicité."
        elif item.quality is ConclusionQuality.AB:
            text = "Conclusion : AB. La conclusion contient des éléments utiles, mais la synthèse ou l'interprétation reste incomplète."
        else:
            text = "Conclusion : À revoir. La réponse ne synthétise pas suffisamment les résultats et leur signification scientifique."
        values.append(ConclusionFeedbackItem(item.expectation_id, text, item.cell_index))
    return tuple(values)
