from __future__ import annotations

from pathlib import Path

from tpstudio.report_consistency import (
    reconcile_global_readiness,
    reconcile_global_readiness_text,
)


BASE_REPORT = """# Rapport TPStudio

### Synthèse rapide
- Corrigeabilité globale : **bonne base**.
- Raison principale : **aucun blocage majeur détecté**.
- Corrigeabilité technique : **bonne base**.
- Code à reprendre : **0** point(s).
- Écarts sémantiques de code à vérifier : **0**.
- Résultats numériques incompatibles : **0**.
- Commentaires locaux insérés : **2**.
"""


def test_keeps_global_summary_when_no_scientific_issue() -> None:
    updated = reconcile_global_readiness_text(BASE_REPORT)

    assert updated == BASE_REPORT


def test_semantic_and_numerical_issues_force_global_retake() -> None:
    report = (
        BASE_REPORT
        .replace(
            "Écarts sémantiques de code à vérifier : **0**",
            "Écarts sémantiques de code à vérifier : **2**",
        )
        .replace(
            "Résultats numériques incompatibles : **0**",
            "Résultats numériques incompatibles : **2**",
        )
    )

    updated = reconcile_global_readiness_text(report)

    assert (
        "Corrigeabilité globale : **à reprendre**"
        in updated
    )
    assert (
        "Raison principale : **erreurs de formule et "
        "incohérences numériques détectées**"
        in updated
    )
    assert (
        "Points scientifiques prioritaires : **4** "
        "(2 formule(s), 2 résultat(s) numérique(s))"
        in updated
    )
    assert (
        "Corrigeabilité technique : **bonne base**"
        in updated
    )


def test_semantic_issue_alone_updates_reason() -> None:
    report = BASE_REPORT.replace(
        "Écarts sémantiques de code à vérifier : **0**",
        "Écarts sémantiques de code à vérifier : **1**",
    )

    updated = reconcile_global_readiness_text(report)

    assert (
        "Raison principale : **écarts scientifiques "
        "dans les formules détectés**"
        in updated
    )


def test_numerical_issue_alone_updates_reason() -> None:
    report = BASE_REPORT.replace(
        "Résultats numériques incompatibles : **0**",
        "Résultats numériques incompatibles : **1**",
    )

    updated = reconcile_global_readiness_text(report)

    assert (
        "Raison principale : **résultats numériques "
        "incompatibles détectés**"
        in updated
    )


def test_file_reconciliation_is_idempotent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "report.md"

    report = (
        BASE_REPORT
        .replace(
            "Écarts sémantiques de code à vérifier : **0**",
            "Écarts sémantiques de code à vérifier : **2**",
        )
        .replace(
            "Résultats numériques incompatibles : **0**",
            "Résultats numériques incompatibles : **2**",
        )
    )
    path.write_text(report, encoding="utf-8")

    assert reconcile_global_readiness(path) is True

    first = path.read_text(encoding="utf-8")

    assert reconcile_global_readiness(path) is False
    assert path.read_text(encoding="utf-8") == first
