from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
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
    copy_contexts: dict[int, str] = field(default_factory=dict)

    @property
    def readiness_level(self) -> str:
        if self.copy.code_cells_with_errors:
            return "à reprendre"

        if getattr(self.copy, "code_cells_to_complete", 0):
            return "à reprendre"

        if self.model.response_cells and self.copy.response_cells == 0:
            return "faible"

        missing_major = self.missing_response_cells + self.missing_result_cells

        if missing_major == 0 and self.copy.empty_response_cells == 0:
            return "bonne base"

        if missing_major <= 2:
            return "partielle"

        return "faible"

    def context_for_cell(self, cell_number: int) -> str:
        return self.copy_contexts.get(cell_number, "")


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
        copy_contexts=_cell_contexts_for_notebook(copy_path),
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
    if getattr(copy, "code_cells_to_complete", 0):
        lines.append(f"    • cellules à compléter : {copy.code_cells_to_complete}")
    lines.append(f"    • cellules non exécutées : {copy.code_cells_not_executed}")
    lines.append(f"    • cellules avec erreur : {copy.code_cells_with_errors}")
    lines.append("")

    lines.append("🔎 Cellules de la copie à vérifier")
    if not copy.issues:
        lines.append("    ✓ aucune cellule problématique évidente détectée")
    else:
        for issue in copy.issues:
            symbol = "⚠" if issue.severity == "warning" else "ℹ"
            context = comparison.context_for_cell(issue.cell_number)
            label = f"cellule {issue.cell_number}"
            if context:
                label += f" — {context}"
            line = f"    {symbol} {label} — {issue.message}"
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

    if getattr(copy, "code_cells_to_complete", 0):
        lines.append("    • certaines cellules contiennent encore du code à compléter")
    elif copy.code_cells_with_errors:
        lines.append("    • des erreurs d'exécution empêchent une correction fiable")
    elif copy.code_cells_not_executed:
        lines.append("    • certaines cellules de code non vides n'ont pas été exécutées")
    elif copy.code_cells:
        lines.append("    • le code de la copie semble exécuté sans erreur détectée")
    lines.append("")

    lines.append("💬 Retour possible à l'étudiant")
    feedback = student_feedback_for_comparison(comparison)
    if not feedback:
        lines.append("    ✓ aucune remarque technique bloquante évidente")
    else:
        for message in feedback:
            lines.append(f"    • {message}")

    return "\n".join(lines)


def student_feedback_for_comparison(comparison: CopyComparison) -> list[str]:
    messages: list[str] = []
    copy = comparison.copy

    code_to_complete_issues = [
        issue
        for issue in copy.issues
        if issue.kind in {"code_to_complete", "code_to_complete_not_executed"}
    ]
    if code_to_complete_issues:
        messages.append(
            "Certaines cellules contiennent encore du code à compléter, par exemple un « ? »."
        )
        for issue in code_to_complete_issues:
            if issue.kind == "code_to_complete_not_executed":
                messages.append(
                    f"{_student_cell_label(comparison, issue.cell_number)} : complétez cette cellule puis exécutez-la."
                )
            else:
                messages.append(
                    f"{_student_cell_label(comparison, issue.cell_number)} : le code contient encore un « ? » ; complétez puis relancez."
                )

    if copy.code_cells_with_errors:
        messages.append(
            "Le notebook contient des erreurs d'exécution : il faut le relancer et corriger les cellules indiquées."
        )
        for issue in copy.issues:
            if issue.kind == "execution_error":
                messages.append(
                    f"{_student_cell_label(comparison, issue.cell_number)} : erreur d'exécution à corriger."
                )

    plain_not_executed_issues = [
        issue for issue in copy.issues if issue.kind == "not_executed"
    ]
    if plain_not_executed_issues:
        messages.append(
            "Certaines cellules de code non vides n'ont pas été exécutées : relancez le notebook avant rendu."
        )
        for issue in plain_not_executed_issues:
            messages.append(
                f"{_student_cell_label(comparison, issue.cell_number)} : cellule de code à exécuter."
            )

    if copy.empty_response_cells:
        messages.append(
            f"{copy.empty_response_cells} réponse(s) sont vides ou à compléter."
        )
        for issue in copy.issues:
            if issue.kind == "empty_response":
                messages.append(
                    f"{_student_cell_label(comparison, issue.cell_number)} : réponse à compléter."
                )

    if comparison.model.response_cells and copy.response_cells == 0:
        messages.append(
            "La copie ne reprend pas les zones « Réponse : » du modèle distribué."
        )
    elif comparison.missing_response_cells:
        messages.append(
            "Certaines zones « Réponse : » attendues ne sont pas identifiables."
        )

    if comparison.missing_result_cells:
        messages.append(
            "Certains résultats attendus ne sont pas identifiables dans la copie."
        )

    if comparison.missing_interpretation_cells:
        messages.append(
            "Certaines interprétations attendues ne sont pas identifiables."
        )

    return messages


def _student_cell_label(comparison: CopyComparison, cell_number: int) -> str:
    context = comparison.context_for_cell(cell_number)
    if context:
        return f"Cellule {cell_number} — {context}"
    return f"Cellule {cell_number}"


def _cell_contexts_for_notebook(notebook_path: str | Path) -> dict[int, str]:
    path = Path(notebook_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    cells = data.get("cells", [])
    if not isinstance(cells, list):
        return {}

    contexts: dict[int, str] = {}
    current_heading = ""

    for index, cell in enumerate(cells):
        cell_number = index + 1
        text = _cell_text(cell)

        if cell.get("cell_type") == "markdown":
            heading = _last_markdown_heading(text)
            if heading:
                current_heading = heading

        if current_heading:
            contexts[cell_number] = f"partie « {current_heading} »"

    return contexts


def _last_markdown_heading(text: str) -> str:
    headings: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(?P<title>.+?)\s*$", line.strip())
        if match:
            headings.append(_clean_heading(match.group("title")))

    if headings:
        return headings[-1]

    return ""


def _clean_heading(title: str) -> str:
    title = re.sub(r"[*_`]+", "", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip(" .:-—\n\t")


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)
