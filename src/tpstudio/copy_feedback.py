from __future__ import annotations

import copy
import json
from pathlib import Path

from tpstudio.copy_comparison import (
    CopyComparison,
    compare_copy_to_model,
)


def create_feedback_notebook(
    model_path: str | Path,
    copy_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """Create a non-destructive notebook copy with TPStudio feedback inserted.

    The original student notebook is never modified. A Markdown cell is inserted
    at the beginning of the copied notebook so that the student sees a readable
    technical summary immediately when opening the file.
    """

    model = Path(model_path)
    source = Path(copy_path)

    if output_path is None:
        output = _next_available_feedback_path(source)
    else:
        output = Path(output_path)

    comparison = compare_copy_to_model(model, source)

    data = json.loads(source.read_text(encoding="utf-8"))
    updated = copy.deepcopy(data)

    cells = updated.setdefault("cells", [])
    if not isinstance(cells, list):
        cells = []
        updated["cells"] = cells

    cells.insert(0, _feedback_markdown_cell(comparison))

    metadata = updated.setdefault("metadata", {})
    if isinstance(metadata, dict):
        tpstudio_metadata = metadata.setdefault("tpstudio", {})
        if isinstance(tpstudio_metadata, dict):
            tpstudio_metadata["feedback_inserted"] = True
            tpstudio_metadata["feedback_source_model"] = model.name
            tpstudio_metadata["feedback_source_copy"] = source.name
            tpstudio_metadata["feedback_format"] = "structured_v1"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(updated, ensure_ascii=False, indent=1), encoding="utf-8")
    return output


def _feedback_markdown_cell(comparison: CopyComparison) -> dict:
    source = structured_feedback_markdown(comparison)

    return {
        "cell_type": "markdown",
        "metadata": {"tpstudio": {"cell_role": "student_feedback", "format": "structured_v1"}},
        "source": source.splitlines(keepends=True),
    }


def structured_feedback_markdown(comparison: CopyComparison) -> str:
    urgent_items = _urgent_feedback_items(comparison)
    check_items = _check_feedback_items(comparison)
    summary_items = _summary_items(comparison, urgent_items, check_items)
    advice_items = _advice_items(comparison, urgent_items, check_items)

    sections = [
        "## Retour TPStudio",
        "",
        "Ce retour automatique signale les points techniques à vérifier avant une correction détaillée.",
        "",
        "### Bilan rapide",
        *_bullet_lines(summary_items),
        "",
        "### À corriger avant de rendre",
        *_bullet_lines(urgent_items, empty="Aucun point bloquant évident détecté."),
        "",
        "### À vérifier",
        *_bullet_lines(check_items, empty="Aucun point de vérification supplémentaire évident."),
        "",
        "### Conseil avant nouveau rendu",
        *_bullet_lines(advice_items),
        "",
    ]

    return "\n".join(sections)


def _summary_items(
    comparison: CopyComparison,
    urgent_items: list[str],
    check_items: list[str],
) -> list[str]:
    copy = comparison.copy

    items = [
        f"Niveau de corrigeabilité : **{comparison.readiness_level}**.",
        f"Points à corriger avant rendu : **{len(urgent_items)}**.",
        f"Points à vérifier : **{len(check_items)}**.",
    ]

    if getattr(copy, "code_cells_to_complete", 0):
        items.append(f"Cellules contenant encore du code à compléter : **{copy.code_cells_to_complete}**.")

    if copy.code_cells_with_errors:
        items.append(f"Cellules avec erreur d'exécution : **{copy.code_cells_with_errors}**.")

    if copy.code_cells_not_executed:
        items.append(f"Cellules de code non exécutées : **{copy.code_cells_not_executed}**.")

    if copy.empty_response_cells:
        items.append(f"Réponses vides ou à compléter : **{copy.empty_response_cells}**.")

    return items


def _urgent_feedback_items(comparison: CopyComparison) -> list[str]:
    items: list[str] = []

    for issue in comparison.copy.issues:
        label = _student_cell_label(comparison, issue.cell_number)

        if issue.kind == "code_to_complete_not_executed":
            items.append(f"{label} : complétez cette cellule puis exécutez-la.")
        elif issue.kind == "code_to_complete":
            items.append(f"{label} : le code contient encore un `?` ; complétez puis relancez.")
        elif issue.kind == "execution_error":
            items.append(f"{label} : erreur d'exécution à corriger.")
        elif issue.kind == "empty_response":
            items.append(f"{label} : réponse à compléter.")

    if comparison.model.response_cells and comparison.copy.response_cells == 0:
        items.append("La copie ne reprend pas les zones `Réponse :` du modèle distribué.")
    elif comparison.missing_response_cells:
        items.append("Certaines zones `Réponse :` attendues ne sont pas identifiables.")

    if comparison.missing_result_cells:
        items.append("Certains résultats attendus ne sont pas identifiables dans la copie.")

    return _deduplicate(items)


def _check_feedback_items(comparison: CopyComparison) -> list[str]:
    items: list[str] = []

    for issue in comparison.copy.issues:
        label = _student_cell_label(comparison, issue.cell_number)

        if issue.kind == "not_executed":
            items.append(f"{label} : cellule de code à exécuter.")
        elif issue.kind == "missing_output":
            items.append(f"{label} : cellule exécutée sans sortie visible ; vérifiez que c'est attendu.")
        elif issue.kind == "short_response":
            items.append(f"{label} : réponse très courte à relire.")

    if comparison.missing_interpretation_cells:
        items.append("Certaines interprétations attendues ne sont pas identifiables.")

    if comparison.missing_checklist_cells:
        items.append("La checklist ou grille finale attendue n'est pas identifiable.")

    return _deduplicate(items)


def _advice_items(
    comparison: CopyComparison,
    urgent_items: list[str],
    check_items: list[str],
) -> list[str]:
    items = [
        "Relancez le notebook depuis le début avant de le rendre.",
        "Vérifiez qu'il ne reste plus de cellule avec `?` dans le code.",
        "Vérifiez que les sorties attendues apparaissent bien sous les cellules de calcul.",
    ]

    if urgent_items:
        items.append("Après correction, relisez le bloc `Retour TPStudio` pour vérifier que chaque point a été traité.")
    elif check_items:
        items.append("Le notebook semble techniquement exploitable, mais vérifiez les points listés.")
    else:
        items.append("Le notebook semble techniquement exploitable pour une correction détaillée.")

    return items


def _bullet_lines(items: list[str], *, empty: str | None = None) -> list[str]:
    if not items:
        if empty is None:
            return []
        return [f"- {empty}"]

    return [f"- {item}" for item in items]


def _student_cell_label(comparison: CopyComparison, cell_number: int) -> str:
    context = comparison.context_for_cell(cell_number)
    if context:
        return f"Cellule {cell_number} — {context}"
    return f"Cellule {cell_number}"


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)

    return result


def _next_available_feedback_path(copy_path: Path) -> Path:
    base = copy_path.with_name(copy_path.stem + "-retour-tpstudio.ipynb")
    if not base.exists():
        return base

    counter = 2
    while True:
        candidate = copy_path.with_name(copy_path.stem + f"-retour-tpstudio-{counter}.ipynb")
        if not candidate.exists():
            return candidate
        counter += 1
