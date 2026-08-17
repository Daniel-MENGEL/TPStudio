"""Conservative inference of a teacher's expected graph model from Markdown.

This module proposes a contract; it never mutates a project or executes a
notebook.  The rules are deliberately small and deterministic because French
"régression linéaire" is not, by itself, evidence for a through-origin model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
import re
import unicodedata

from .model import ExpectedGraphModel


class ExpectedModelProposalConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExpectedModelProposalSource(str, Enum):
    NONE = "none"
    STATEMENT = "statement"
    CORRECTION = "correction"
    STATEMENT_AND_CORRECTION = "statement_and_correction"


@dataclass(frozen=True, slots=True)
class ExpectedGraphModelProposal:
    """An explainable, non-persistent proposal for one TP's graph model."""

    model: ExpectedGraphModel | None
    confidence: ExpectedModelProposalConfidence
    evidence: tuple[str, ...]
    source: ExpectedModelProposalSource

    def __post_init__(self) -> None:
        if self.model is not None and type(self.model) is not ExpectedGraphModel:
            raise TypeError("Le modèle proposé doit être un ExpectedGraphModel ou None.")
        if type(self.confidence) is not ExpectedModelProposalConfidence:
            raise TypeError("La confiance doit être un ExpectedModelProposalConfidence.")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("Chaque indice doit être une chaîne non vide.")
        if type(self.source) is not ExpectedModelProposalSource:
            raise TypeError("La source doit être un ExpectedModelProposalSource.")


_PROPORTIONAL = re.compile(
    r"\b(?:proportionnel(?:le)?|proportionnalit[eé]|relation de proportionnalit[eé])\b"
)
_ORIGIN_LINE = re.compile(r"droite\s+(?:qui\s+)?passe\s+par\s+l['’]origine")
_ORIGIN_FORMULA = re.compile(
    r"\b[xy]\s*=\s*[ak]\s*\*?\s*[xX]\b|\b[YX]\s*=\s*[kK]\s*\*?\s*[Xx]\b"
)
_AFFINE_WORD = re.compile(r"\b(?:fonction|relation|mod[eè]le|r[eé]gression)\s+affine\b")
_AFFINE_FORMULA = re.compile(
    r"\b[xy]\s*=\s*[ak]\s*\*?\s*[xX]\s*[+]\s*[bB]\b"
)
_QUADRATIC_WORD = re.compile(
    r"\b(?:fonction|relation|mod[eè]le|r[eé]gression)\s+quadratique\b"
    r"|\bpolyn[oô]me\s+de\s+degr[eé]\s+2\b|\bparabole\b"
)
_QUADRATIC_FORMULA = re.compile(
    r"\b[xy]\s*=.*[xX]\s*(?:\^\s*2|²).*[+]\s*[bB].*[+]\s*[cC]\b"
)
_GENERIC_LINEAR = re.compile(r"\br[eé]gression\s+lin[eé]aire\b")
_LINEAR_WORD = re.compile(r"\bfonction\s+lin[eé]aire\b")
_NEGATED = re.compile(
    r"\b(?:ne\s+pas|ne\s+\w+\s+pas|n['’]?est\s+pas|pas\s+de|sans\s+utiliser|"
    r"non\s+(?:affine|lin[eé]aire|quadratique|proportionnel(?:le)?))\b"
)
_EXPLORATORY = re.compile(
    r"\b(?:v[eé]rifier|d[eé]terminer|tester|voir)\s+si\b|"
    r"\b(?:peut|pourrait)\s+e?tre\b|\bconvient\s+ou\s+non\b|"
    r"\best[- ]ce\s+que\b|\bpour\s+savoir\s+si\b|"
    r"\bse\s+demande(?:r)?\s+si\b|"
    r"\b(?:on\s+)?(?:peut|pourrait)\s+se\s+demander\s+si\b|"
    r"\bil\s+est\s+possible\s+de\s+se\s+demander\s+si\b"
)


def _normalise(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    without_latex_spacing = re.sub(r"\\[,;!]", " ", without_accents)
    return re.sub(r"\s+", " ", without_latex_spacing).strip()


def _lines(markdown: Sequence[str], label: str) -> tuple[tuple[str, str], ...]:
    if isinstance(markdown, (str, bytes)):
        raise TypeError("Les cellules Markdown doivent former une séquence de chaînes.")
    result = []
    for cell in markdown:
        if not isinstance(cell, str):
            raise TypeError("Chaque cellule Markdown doit être une chaîne.")
        segments = re.split(r"(?<=[.;:!?])\s+|\n+", cell)
        for segment in segments:
            if segment.strip():
                result.append((_normalise(segment), f"{label} : {segment.strip()[:180]}"))
    return tuple(result)


def _document_candidates(
    lines: tuple[tuple[str, str], ...],
) -> tuple[tuple[ExpectedGraphModel | None, str], ...]:
    candidates: list[tuple[ExpectedGraphModel | None, str]] = []
    for text, evidence in lines:
        if _NEGATED.search(text) or _EXPLORATORY.search(text):
            continue
        if _QUADRATIC_WORD.search(text) or _QUADRATIC_FORMULA.search(text):
            candidates.append((ExpectedGraphModel.QUADRATIC, evidence))
            continue
        if _AFFINE_WORD.search(text) or _AFFINE_FORMULA.search(text):
            candidates.append((ExpectedGraphModel.AFFINE, evidence))
            continue
        if _PROPORTIONAL.search(text) or _ORIGIN_LINE.search(text) or _ORIGIN_FORMULA.search(text):
            candidates.append((ExpectedGraphModel.LINEAR_THROUGH_ORIGIN, evidence))
            continue
        # "régression linéaire" is deliberately recorded as ambiguity only.
        if _GENERIC_LINEAR.search(text):
            candidates.append((None, evidence))
        elif _LINEAR_WORD.search(text):
            candidates.append((ExpectedGraphModel.LINEAR_THROUGH_ORIGIN, evidence))
    return tuple(candidates)


def _source(has_statement: bool, has_correction: bool) -> ExpectedModelProposalSource:
    if not has_statement and not has_correction:
        return ExpectedModelProposalSource.NONE
    if has_statement and has_correction:
        return ExpectedModelProposalSource.STATEMENT_AND_CORRECTION
    return ExpectedModelProposalSource.STATEMENT if has_statement else ExpectedModelProposalSource.CORRECTION


def infer_expected_graph_model(
    statement_markdown: Sequence[str],
    correction_markdown: Sequence[str] = (),
) -> ExpectedGraphModelProposal:
    """Propose a model from Markdown evidence without changing any project."""

    statement_lines = _lines(statement_markdown, "Énoncé")
    correction_lines = _lines(correction_markdown, "Corrigé")
    statement = _document_candidates(statement_lines)
    correction = _document_candidates(correction_lines)
    all_candidates = statement + correction
    source = _source(bool(statement), bool(correction))
    evidence = tuple(item[1] for item in all_candidates[:4])
    models = {item[0] for item in all_candidates if item[0] is not None}
    has_ambiguity = any(item[0] is None for item in all_candidates)
    if len(models) > 1:
        return ExpectedGraphModelProposal(None, ExpectedModelProposalConfidence.LOW, evidence, source)
    if has_ambiguity and models:
        return ExpectedGraphModelProposal(None, ExpectedModelProposalConfidence.LOW, evidence, source)
    if not models:
        return ExpectedGraphModelProposal(None, ExpectedModelProposalConfidence.LOW, evidence, source)
    model = next(iter(models))
    in_statement = any(item[0] is model for item in statement)
    in_correction = any(item[0] is model for item in correction)
    confidence = (
        ExpectedModelProposalConfidence.HIGH
        if in_statement and in_correction
        else ExpectedModelProposalConfidence.MEDIUM
    )
    return ExpectedGraphModelProposal(model, confidence, evidence, source)
