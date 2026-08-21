"""Pure, non-activating proposals between statement candidates and productions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata
from typing import Any

from tpstudio.expectations import ScientificProductionKind

from .candidate import CandidateItem, CandidateKind, CandidateScientificContract


class MatchConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidationState(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class CandidateProductionMatch:
    candidate_id: str
    production_id: str
    confidence: MatchConfidence
    score: float
    reasons: tuple[str, ...]
    validation_state: ValidationState = ValidationState.PROPOSED

    def __post_init__(self) -> None:
        for name in ("candidate_id", "production_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} doit être une chaîne non vide.")
        if type(self.confidence) is not MatchConfidence:
            raise TypeError("confidence doit être un MatchConfidence.")
        if type(self.validation_state) is not ValidationState:
            raise TypeError("validation_state doit être un ValidationState.")
        if not isinstance(self.score, (int, float)) or not 0 <= self.score <= 1:
            raise ValueError("score doit être compris entre 0 et 1.")
        reasons = tuple(self.reasons)
        if not reasons or any(not isinstance(reason, str) or not reason.strip() for reason in reasons):
            raise ValueError("Une proposition doit conserver ses raisons.")
        object.__setattr__(self, "reasons", reasons)


_KIND_COMPATIBILITY = {
    CandidateKind.QUANTITY: (ScientificProductionKind.QUANTITY,),
    CandidateKind.GRAPH: (ScientificProductionKind.PLOT,),
    CandidateKind.COMPARISON: (ScientificProductionKind.COMPARISON,),
    CandidateKind.RELATION: (ScientificProductionKind.RELATION,),
    CandidateKind.INTERPRETATION: (ScientificProductionKind.INTERPRETATION,),
    CandidateKind.CONCLUSION: (ScientificProductionKind.INTERPRETATION,),
}


def _words(value: str) -> set[str]:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("_", " ")
    stopwords = {
        "de", "du", "des", "la", "le", "les", "un", "une", "et", "en",
        "a", "au", "aux", "pour", "par", "dans", "sur", "avec", "the",
        "of", "and", "to", "from", "la", "m", "l",
    }
    return {
        word for word in re.findall(r"[a-z][a-z0-9_]*", value)
        if len(word) > 1 and word not in stopwords
    }


def _symbols(value: str) -> set[str]:
    return {item.casefold() for item in re.findall(r"(?<![A-Za-z])[A-Za-z][A-Za-z0-9_]*", value)}


def _binding_texts(configuration: Any, production_id: str) -> tuple[str, ...]:
    plan = getattr(configuration, "notebook_binding_plan", None)
    if plan is None:
        return ()
    texts = []
    for binding in plan.for_production(production_id):
        texts.append(binding.id)
        texts.append(binding.description)
        texts.append(binding.selector.value)
    return tuple(texts)


def _score(candidate: CandidateItem, production: Any, configuration: Any) -> tuple[float, list[str]] | None:
    compatible = _KIND_COMPATIBILITY.get(candidate.kind, ())
    kind = getattr(production, "kind", None)
    semantic_exception = (
        candidate.kind is CandidateKind.QUANTITY
        and candidate.metadata.get("derived_quantity_role") == "normalized_error"
        and kind is ScientificProductionKind.RELATION
        and "normalized" in _words(f"{production.id} {production.label}")
    )
    if kind not in compatible and not semantic_exception:
        return None

    reasons: list[str] = []
    score = 0.45
    if kind in compatible:
        reasons.append("kind compatible")
    else:
        score = 0.35
        reasons.append("résultat dérivé et production relationnelle : compatibilité sémantique partielle")

    production_text = " ".join((production.id, production.label, production.description, *_binding_texts(configuration, production.id)))
    candidate_text = f"{candidate.normalized_text} {candidate.source_text}"
    candidate_words = _words(candidate_text)
    overlap = candidate_words & _words(production_text)
    if overlap:
        score += min(0.20, 0.05 * len(overlap))
        reasons.append("vocabulaire commun : " + ", ".join(sorted(overlap)))

    if (
        candidate.kind is CandidateKind.RELATION
        and candidate.metadata.get("relation_role") == "provided_scientific_context"
        and not overlap
    ):
        return None

    candidate_symbols = set(candidate.target_symbols)
    if candidate.scientific_symbol:
        candidate_symbols.add(candidate.scientific_symbol)
    binding_symbols = _symbols(" ".join(_binding_texts(configuration, production.id)))
    production_symbols = _symbols(production_text)
    symbol_overlap = {symbol.casefold() for symbol in candidate_symbols} & (binding_symbols | production_symbols)
    if symbol_overlap:
        score += 0.25
        reasons.append("symbole compatible : " + ", ".join(sorted(symbol_overlap)))

    binding_words = _words(" ".join(_binding_texts(configuration, production.id)))
    if candidate.kind is CandidateKind.GRAPH and binding_words & {"plot", "graph", "graphe"}:
        score += 0.25
        reasons.append("binding graphique compatible")
    if candidate.kind is CandidateKind.COMPARISON and binding_words & {"comparison", "comparaison"}:
        score += 0.25
        reasons.append("binding de comparaison compatible")
    if (
        candidate.metadata.get("derived_quantity_role") == "normalized_error"
        and kind not in compatible
        and "normalized" in _words(production_text)
    ):
        score += 0.15
        reasons.append("rôle dérivé normalized_error compatible")
        score = min(score, 0.49)
        reasons.append("kind différent : proposition à valider")

    # A provided relation is context from the statement, never a high-confidence
    # student-production match without teacher validation.
    if candidate.kind is CandidateKind.RELATION and candidate.metadata.get("relation_role") == "provided_scientific_context":
        score = min(score, 0.39)
        reasons.append("relation fournie : validation professeur nécessaire")

    return min(score, 1.0), reasons


def propose_candidate_production_matches(
    candidate_contract: CandidateScientificContract,
    project_configuration: Any,
) -> tuple[CandidateProductionMatch, ...]:
    """Return explainable proposals without modifying the project configuration."""
    if not isinstance(candidate_contract, CandidateScientificContract):
        raise TypeError("candidate_contract doit être un CandidateScientificContract.")
    plan = getattr(project_configuration, "scientific_production_plan", None)
    if plan is None:
        raise TypeError("La configuration doit exposer scientific_production_plan.")

    scored: list[tuple[CandidateItem, Any, float, list[str]]] = []
    for candidate in candidate_contract.items:
        options = []
        for production in plan:
            result = _score(candidate, production, project_configuration)
            if result is not None:
                options.append((production, *result))
        options = [
            option for option in options
            if option[1] >= (
                0.35
                if (
                    candidate.kind is CandidateKind.RELATION
                    and candidate.metadata.get("relation_role") == "provided_scientific_context"
                )
                else 0.35
                if (
                    candidate.metadata.get("derived_quantity_role")
                    and option[0].kind is ScientificProductionKind.RELATION
                )
                else 0.50
            )
        ]
        options.sort(key=lambda option: (-option[1], option[0].id))
        if options and len(options) > 1 and options[0][1] - options[1][1] < 0.08:
            for production, score, reasons in options:
                reasons = [*reasons, "ambiguïté : plusieurs productions plausibles"]
                scored.append((candidate, production, score, reasons))
        elif options:
            production, score, reasons = options[0]
            scored.append((candidate, production, score, reasons))

    matches = []
    for candidate, production, score, reasons in scored:
        confidence = (
            MatchConfidence.HIGH if score >= 0.75
            else MatchConfidence.MEDIUM if score >= 0.50
            else MatchConfidence.LOW
        )
        if "ambiguïté : plusieurs productions plausibles" in reasons:
            confidence = min(confidence, MatchConfidence.MEDIUM, key=lambda item: ("low", "medium", "high").index(item.value))
        matches.append(CandidateProductionMatch(candidate.candidate_id, production.id, confidence, score, tuple(reasons)))
    return tuple(matches)
