from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tpstudio.student_inspection import (
    StudentNotebookDiagnostic,
    inspect_student_notebook,
)


@dataclass
class CopyComparison:
    model_path: Path
    copy_path: Path
    model: StudentNotebookDiagnostic
    copy: StudentNotebookDiagnostic
    missing_response_cells: int
    missing_result_cells: int
    missing_interpretation_cells: int
    missing_checklist_cells: int

    @property
    def readiness_level(self) -> str:
        if self.copy.code_cells_with_errors:
            return "à reprendre"

        if self.model.response_cells and self.copy.response_cells == 0:
            return "faible"

        missing_major = self.missing_response_cells + self.missing_result_cells

        if missing_major == 0 and self.copy.empty_response_cells == 0:
            return "bonne base"

        if missing_major <= 2:
            return "partielle"

        return "faible"


def compare_copy_to_model(model_path: str | Path, copy_path: str | Path) -> CopyComparison:
    model = inspect_student_notebook(model_path)
    copy = inspect_student_notebook(copy_path)

    return CopyComparison(
        model_path=Path(model_path),
        copy_path=Path(copy_path),
        model=model,
        copy=copy,
        missing_response_cells=max(model.response_cells - copy.response_cells, 0),
        missing_result_cells=max(model.result_cells - copy.result_cells, 0),
        missing_interpretation_cells=max(model.interpretation_cells - copy.interpretation_cells, 0),
        missing_checklist_cells=max(model.checklist_cells - copy.checklist_cells, 0),
    )


def format_copy_comparison_report(comparison: CopyComparison) -> str:
    lines: list[str] = []

    model = comparison.model
    copy = comparison.copy

    lines.append("TPStudio - Comparaison modèle / copie")
    lines.append("────────────────────────────────────")
    lines.append("")
    lines.append(f"📘 Modèle : {comparison.model_path.name}")
    lines.append(f"📓 Copie : {comparison.copy_path.name}")
    lines.append("")

    lines.append("📝 Zones Réponse")
    lines.append(f"    • attendues dans le modèle : {model.response_cells}")
    lines.append(f"    • présentes dans la copie : {copy.response_cells}")
    lines.append(f"    • manquantes estimées : {comparison.missing_response_cells}")
    lines.append(f"    • vides ou à compléter : {copy.empty_response_cells}")
    lines.append("")

    lines.append("📌 Cellules Résultat")
    lines.append(f"    • attendues dans le modèle : {model.result_cells}")
    lines.append(f"    • présentes dans la copie : {copy.result_cells}")
    lines.append(f"    • manquantes estimées : {comparison.missing_result_cells}")
    lines.append("")

    lines.append("💬 Interprétation")
    lines.append(f"    • attendues dans le modèle : {model.interpretation_cells}")
    lines.append(f"    • présentes dans la copie : {copy.interpretation_cells}")
    lines.append(f"    • manquantes estimées : {comparison.missing_interpretation_cells}")
    lines.append("")

    lines.append("✅ Checklist / grille")
    lines.append(f"    • attendues dans le modèle : {model.checklist_cells}")
    lines.append(f"    • présentes dans la copie : {copy.checklist_cells}")
    lines.append(f"    • manquantes estimées : {comparison.missing_checklist_cells}")
    lines.append("")

    lines.append("💻 Code dans la copie")
    lines.append(f"    • cellules de code : {copy.code_cells}")
    if copy.empty_code_cells:
        lines.append(f"    • cellules de code vides ignorées : {copy.empty_code_cells}")
    lines.append(f"    • cellules non exécutées : {copy.code_cells_not_executed}")
    lines.append(f"    • cellules avec erreur : {copy.code_cells_with_errors}")
    lines.append("")

    lines.append("🔎 Cellules de la copie à vérifier")
    if not copy.issues:
        lines.append("    ✓ aucune cellule problématique évidente détectée")
    else:
        for issue in copy.issues:
            symbol = "⚠" if issue.severity == "warning" else "ℹ"
            line = f"    {symbol} cellule {issue.cell_number} — {issue.message}"
            if issue.preview:
                line += f" : {issue.preview}"
            lines.append(line)
    lines.append("")

    lines.append("🧪 Corrigeabilité comparative")
    lines.append(f"    niveau : {comparison.readiness_level}")

    if model.response_cells and copy.response_cells == 0:
        lines.append("    • la copie ne reprend pas les zones « Réponse : » du modèle")
    elif comparison.missing_response_cells:
        lines.append("    • certaines zones « Réponse : » du modèle semblent absentes")
    else:
        lines.append("    • les zones « Réponse : » semblent présentes")

    if comparison.missing_result_cells:
        lines.append("    • certaines cellules « Résultat » semblent absentes")
    else:
        lines.append("    • les cellules « Résultat » semblent présentes")

    if copy.code_cells_with_errors:
        lines.append("    • des erreurs d'exécution empêchent une correction fiable")
    elif copy.code_cells_not_executed:
        lines.append("    • certaines cellules de code non vides n'ont pas été exécutées")
    elif copy.code_cells:
        lines.append("    • le code de la copie semble exécuté sans erreur détectée")

    return "\n".join(lines)
