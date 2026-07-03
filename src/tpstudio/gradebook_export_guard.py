from __future__ import annotations

from tpstudio.gradebook_check import (
    GradebookCheckSummary,
    format_gradebook_check_summary,
)


def gradebook_check_has_blocking_issues(summary: GradebookCheckSummary) -> bool:
    # Les copies manquantes ne sont pas bloquantes :
    # en TP, une partie de la classe peut ne pas être présente chaque semaine.
    return (
        summary.unmatched_named_students > 0
        or summary.missing_identity_notebooks > 0
    )


def format_gradebook_export_blocked_message(summary: GradebookCheckSummary) -> str:
    lines = [
        format_gradebook_check_summary(summary),
        "",
        "Export interrompu : anomalies bloquantes détectées.",
        "",
        "Anomalies bloquantes : noms non reconnus ou identités absentes.",
        "Les rapports non rendus restent signalés dans le bilan, mais ne bloquent pas l'export.",
        "",
        "Corrige les anomalies ou relance avec --allow-issues pour forcer l'export.",
    ]

    return "\n".join(lines)
