from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

from tpstudio.response_extraction import (
    NotebookResponse,
    extract_responses_from_notebook,
)


@dataclass(frozen=True)
class ResponseDiagnosis:
    response: NotebookResponse
    level: str
    signals: list[str]
    advice: list[str]
    has_numeric_value: bool
    has_comparison: bool
    has_physical_vocabulary: bool
    is_vague: bool


def diagnose_responses_from_notebook(notebook_path: str | Path) -> list[ResponseDiagnosis]:
    """Return lightweight diagnostics for extracted student answers.

    This is intentionally heuristic. It does not try to grade the scientific
    correctness yet; it only highlights textual clues that a teacher may want to
    inspect before deeper semantic comparison.
    """

    return [
        diagnose_response(response)
        for response in extract_responses_from_notebook(notebook_path)
    ]


def diagnose_response(response: NotebookResponse) -> ResponseDiagnosis:
    text = response.text
    lower = _normalize(text)

    has_numeric_value = _has_numeric_value(text)
    has_comparison = _has_comparison(lower)
    has_physical_vocabulary = _has_physical_vocabulary(lower)
    is_vague = _is_vague(lower, response.word_count)

    signals: list[str] = []
    advice: list[str] = []

    if response.is_empty:
        signals.append("réponse vide ou à compléter")
        advice.append("rédiger une réponse complète dans cette zone")
    elif response.word_count < 8:
        signals.append("réponse très courte")
        advice.append("développer la réponse avec une phrase complète")

    if not response.is_empty and not has_numeric_value:
        signals.append("aucune valeur numérique détectée")
        advice.append("ajouter une valeur mesurée ou calculée lorsque c'est pertinent")

    if not response.is_empty and not has_comparison:
        signals.append("aucune comparaison explicite détectée")
        advice.append("comparer le résultat obtenu à une valeur attendue ou à une autre méthode")

    if not response.is_empty and not has_physical_vocabulary:
        signals.append("vocabulaire physique peu explicite")
        advice.append("relier la réponse à la grandeur physique étudiée")

    if not response.is_empty and is_vague:
        signals.append("formulation vague")
        advice.append("préciser le résultat et la justification")

    if not signals:
        signals.append("réponse structurée sur le plan textuel")

    level = _diagnosis_level(response, signals)

    return ResponseDiagnosis(
        response=response,
        level=level,
        signals=_deduplicate(signals),
        advice=_deduplicate(advice),
        has_numeric_value=has_numeric_value,
        has_comparison=has_comparison,
        has_physical_vocabulary=has_physical_vocabulary,
        is_vague=is_vague,
    )


def format_response_diagnostic_report(notebook_path: str | Path) -> str:
    diagnoses = diagnose_responses_from_notebook(notebook_path)

    lines = [
        "TPStudio - Diagnostic des réponses étudiantes",
        "──────────────────────────────────────────",
        "",
        f"Réponses analysées : {len(diagnoses)}",
    ]

    if not diagnoses:
        lines.append("Aucune zone `Réponse :` détectée.")
        return "\n".join(lines)

    counts = _level_counts(diagnoses)

    lines.extend(
        [
            "",
            "Synthèse",
            f"    • solides : {counts.get('solide', 0)}",
            f"    • acceptables : {counts.get('acceptable', 0)}",
            f"    • fragiles : {counts.get('fragile', 0)}",
            f"    • à compléter : {counts.get('à compléter', 0)}",
        ]
    )

    for number, diagnosis in enumerate(diagnoses, start=1):
        response = diagnosis.response

        lines.append("")
        title = f"Réponse {number} — cellule {response.cell_number}"
        if response.context:
            title += f" — partie « {response.context} »"
        lines.append(title)
        lines.append(f"    niveau : {diagnosis.level}")

        lines.append("    indices :")
        for signal in diagnosis.signals:
            lines.append(f"        • {signal}")

        if diagnosis.advice:
            lines.append("    conseil :")
            for advice in diagnosis.advice:
                lines.append(f"        • {advice}")

        preview = _shorten(response.text)
        if preview:
            lines.append(f"    extrait : {preview}")
        else:
            lines.append("    extrait : —")

    return "\n".join(lines)


def _diagnosis_level(response: NotebookResponse, signals: list[str]) -> str:
    if response.is_empty:
        return "à compléter"

    blocking_signals = {
        "réponse très courte",
        "formulation vague",
    }

    weak_signals = {
        "aucune valeur numérique détectée",
        "aucune comparaison explicite détectée",
        "vocabulaire physique peu explicite",
    }

    if any(signal in blocking_signals for signal in signals):
        return "fragile"

    weak_count = sum(1 for signal in signals if signal in weak_signals)

    if weak_count >= 2:
        return "fragile"

    if weak_count == 1:
        return "acceptable"

    return "solide"


def _has_numeric_value(text: str) -> bool:
    return re.search(r"(?<![A-Za-zÀ-ÿ])[-+]?\d+(?:[,.]\d+)?(?:\s*(?:%|°|rad|m|cm|mm|s|kg|n|N))?", text) is not None


def _has_comparison(lower: str) -> bool:
    comparison_patterns = [
        r"\bcompar",
        r"\bcompatible\b",
        r"\bcoh[ée]rent",
        r"\bproche\b",
        r"\bvoisin\b",
        r"\battendu",
        r"\bth[ée]ori",
        r"\bvaleur\s+attendue\b",
        r"\b[ée]cart\s+normalis[ée]\b",
        r"\binf[ée]rieur\s+[àa]\b",
        r"\bsup[ée]rieur\s+[àa]\b",
        r"\bautre\s+m[ée]thode\b",
    ]

    return any(re.search(pattern, lower) for pattern in comparison_patterns)


def _has_physical_vocabulary(lower: str) -> bool:
    physical_terms = [
        "indice",
        "plexiglas",
        "réfraction",
        "refraction",
        "snell",
        "descartes",
        "angle",
        "pente",
        "incertitude",
        "écart normalisé",
        "ecart normalise",
        "sin",
        "mesure",
        "expérimental",
        "experimental",
        "loi",
        "droite",
        "alignés",
        "alignes",
    ]

    return any(term in lower for term in physical_terms)


def _is_vague(lower: str, word_count: int) -> bool:
    if word_count >= 18:
        return False

    vague_patterns = [
        r"\bcorrect\b",
        r"\bsemble\b",
        r"\bassez\b",
        r"\bplut[oô]t\b",
        r"\bglobalement\b",
        r"\b[àa] peu pr[èe]s\b",
        r"\bproches?\b",
        r"\bça va\b",
        r"\bc'est bon\b",
    ]

    return any(re.search(pattern, lower) for pattern in vague_patterns)


def _normalize(text: str) -> str:
    return text.lower().replace("œ", "oe")


def _level_counts(diagnoses: list[ResponseDiagnosis]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for diagnosis in diagnoses:
        counts[diagnosis.level] = counts.get(diagnosis.level, 0) + 1

    return counts


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)

    return result


def _shorten(text: str, max_length: int = 180) -> str:
    if len(text) <= max_length:
        return text

    return text[: max_length - 1].rstrip() + "…"
