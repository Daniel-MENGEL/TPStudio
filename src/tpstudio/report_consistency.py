from __future__ import annotations

from pathlib import Path
import re


SEMANTIC_LABEL = "Écarts sémantiques de code à vérifier"
NUMERICAL_LABEL = "Résultats numériques incompatibles"


def reconcile_global_readiness(
    report_path: str | Path,
) -> bool:
    path = Path(report_path)
    text = path.read_text(encoding="utf-8")
    updated = reconcile_global_readiness_text(text)

    if updated == text:
        return False

    path.write_text(updated, encoding="utf-8")
    return True


def reconcile_global_readiness_text(text: str) -> str:
    semantic_count = _extract_bold_count(
        text,
        SEMANTIC_LABEL,
    )
    numerical_count = _extract_bold_count(
        text,
        NUMERICAL_LABEL,
    )

    if semantic_count <= 0 and numerical_count <= 0:
        return text

    reason = _scientific_reason(
        semantic_count=semantic_count,
        numerical_count=numerical_count,
    )

    text = _replace_summary_value(
        text,
        label="Corrigeabilité globale",
        value="à reprendre",
    )
    text = _replace_summary_value(
        text,
        label="Raison principale",
        value=reason,
    )

    text = _ensure_scientific_summary_line(
        text,
        semantic_count=semantic_count,
        numerical_count=numerical_count,
    )

    return text


def _extract_bold_count(
    text: str,
    label: str,
) -> int:
    pattern = re.compile(
        rf"^- {re.escape(label)}\s*:\s*\*\*(\d+)\*\*\.",
        re.MULTILINE,
    )
    match = pattern.search(text)

    if match is None:
        return 0

    return int(match.group(1))


def _scientific_reason(
    *,
    semantic_count: int,
    numerical_count: int,
) -> str:
    if semantic_count > 0 and numerical_count > 0:
        return (
            "erreurs de formule et incohérences numériques détectées"
        )

    if semantic_count > 0:
        return "écarts scientifiques dans les formules détectés"

    return "résultats numériques incompatibles détectés"


def _replace_summary_value(
    text: str,
    *,
    label: str,
    value: str,
) -> str:
    pattern = re.compile(
        rf"^- {re.escape(label)}\s*:\s*\*\*.*?\*\*\.\s*$",
        re.MULTILINE,
    )
    replacement = f"- {label} : **{value}**."

    if pattern.search(text):
        return pattern.sub(
            replacement,
            text,
            count=1,
        )

    return text


def _ensure_scientific_summary_line(
    text: str,
    *,
    semantic_count: int,
    numerical_count: int,
) -> str:
    label = "Points scientifiques prioritaires"

    if label in text:
        return text

    total = semantic_count + numerical_count
    line = (
        f"- {label} : **{total}** "
        f"({semantic_count} formule(s), "
        f"{numerical_count} résultat(s) numérique(s))."
    )

    anchor = re.compile(
        r"^- Corrigeabilité technique\s*:.*$",
        re.MULTILINE,
    )
    match = anchor.search(text)

    if match is None:
        return text

    line_end = match.end()

    return (
        text[:line_end]
        + "\n"
        + line
        + text[line_end:]
    )
