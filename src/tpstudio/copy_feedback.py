from __future__ import annotations

import copy
import json
import re
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

    The original student notebook is never modified. The generated copy contains:
    - a structured summary cell at the beginning;
    - local Markdown comments after cells that need attention.
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

    original_cells = updated.setdefault("cells", [])
    if not isinstance(original_cells, list):
        original_cells = []

    updated["cells"] = _cells_with_feedback(original_cells, comparison)

    metadata = updated.setdefault("metadata", {})
    if isinstance(metadata, dict):
        tpstudio_metadata = metadata.setdefault("tpstudio", {})
        if isinstance(tpstudio_metadata, dict):
            tpstudio_metadata["feedback_inserted"] = True
            tpstudio_metadata["feedback_source_model"] = model.name
            tpstudio_metadata["feedback_source_copy"] = source.name
            tpstudio_metadata["feedback_format"] = "structured_v3"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(updated, ensure_ascii=False, indent=1), encoding="utf-8")
    return output


def _cells_with_feedback(cells: list[dict], comparison: CopyComparison) -> list[dict]:
    local_comments = local_feedback_by_cell(comparison)

    new_cells: list[dict] = [_feedback_markdown_cell(comparison)]

    for index, cell in enumerate(cells, start=1):
        new_cells.append(cell)

        comments = local_comments.get(index, [])
        if comments:
            new_cells.append(_local_feedback_markdown_cell(index, comments))

    return new_cells


def _feedback_markdown_cell(comparison: CopyComparison) -> dict:
    source = structured_feedback_markdown(comparison)

    return {
        "cell_type": "markdown",
        "metadata": {"tpstudio": {"cell_role": "student_feedback", "format": "structured_v3"}},
        "source": source.splitlines(keepends=True),
    }


def _local_feedback_markdown_cell(cell_number: int, comments: list[str]) -> dict:
    bullet_lines = "\n".join(f"> - {comment}" for comment in comments)

    source = (
        "> 💬 **TPStudio — commentaire local**\n"
        ">\n"
        f"> Cellule concernée dans la copie originale : **{cell_number}**.\n"
        ">\n"
        f"{bullet_lines}\n"
    )

    return {
        "cell_type": "markdown",
        "metadata": {
            "tpstudio": {
                "cell_role": "local_feedback",
                "target_cell_number": cell_number,
                "position": "after_target_cell",
                "format": "structured_v2",
            }
        },
        "source": source.splitlines(keepends=True),
    }


def structured_feedback_markdown(comparison: CopyComparison) -> str:
    urgent_items = _urgent_feedback_items(comparison)
    check_items = _check_feedback_items(comparison)
    local_comments = local_feedback_by_cell(comparison)
    summary_items = _summary_items(comparison, urgent_items, check_items, local_comments)
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
        "### Commentaires dans le notebook",
        *_bullet_lines(_local_comment_summary_items(local_comments)),
        "",
        "### Conseil avant nouveau rendu",
        *_bullet_lines(advice_items),
        "",
    ]

    return "\n".join(sections)


def local_feedback_by_cell(comparison: CopyComparison) -> dict[int, list[str]]:
    comments: dict[int, list[str]] = {}
    sources = _cell_sources_by_number(comparison.copy_path)

    for issue in comparison.copy.issues:
        source = sources.get(issue.cell_number, issue.preview)

        if _should_skip_local_comment(issue.kind, source):
            continue

        comment = _local_comment_for_issue(issue.kind)
        if not comment:
            continue

        comments.setdefault(issue.cell_number, []).append(comment)

    return {
        cell_number: _deduplicate(cell_comments)
        for cell_number, cell_comments in comments.items()
    }


def _should_skip_local_comment(kind: str, source: str) -> bool:
    if kind in {"not_executed", "missing_output"} and _is_setup_only_code(source):
        return True

    return False


def _is_setup_only_code(source: str) -> bool:
    meaningful_lines = _meaningful_code_lines(source)
    if not meaningful_lines:
        return True

    in_rcparams_block = False

    for line in meaningful_lines:
        stripped = line.strip()

        if "rcParams.update" in stripped:
            in_rcparams_block = True
            continue

        if in_rcparams_block:
            if stripped in {"}", "})", ")"} or stripped.endswith("})"):
                in_rcparams_block = False
                continue
            if _looks_like_dict_item(stripped):
                continue

        if _is_setup_line(stripped):
            continue

        return False

    return True


def _meaningful_code_lines(source: str) -> list[str]:
    lines: list[str] = []

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        lines.append(stripped)

    return lines


def _is_setup_line(line: str) -> bool:
    setup_prefixes = (
        "import ",
        "from ",
        "%matplotlib",
        "plt.rcParams",
        "matplotlib.rcParams",
        "rcParams",
        "np.set_printoptions",
        "pd.set_option",
        "warnings.filterwarnings",
    )

    return line.startswith(setup_prefixes)


def _looks_like_dict_item(line: str) -> bool:
    if line in {"{", "}", "},", "})", ")"}:
        return True

    return re.match(r"^[\"'].*[\"']\s*:\s*.+,?$", line) is not None


def _local_comment_for_issue(kind: str) -> str:
    if kind == "code_to_complete_not_executed":
        return "Cette cellule contient encore du code à compléter (`?`) et n'a pas été exécutée."
    if kind == "code_to_complete":
        return "Cette cellule contient encore du code à compléter (`?`) : complétez puis relancez."
    if kind == "execution_error":
        return "Cette cellule produit une erreur d'exécution : corrigez l'erreur puis relancez le notebook."
    if kind == "not_executed":
        return "Cette cellule de code n'a pas été exécutée."
    if kind == "missing_output":
        return "Cette cellule a été exécutée sans sortie visible : vérifiez que c'est bien attendu."
    if kind == "empty_response":
        return "Cette réponse est vide ou à compléter."
    if kind == "short_response":
        return "Cette réponse est très courte : vérifiez qu'elle est suffisamment justifiée."

    return ""


def _cell_sources_by_number(notebook_path: str | Path) -> dict[int, str]:
    try:
        data = json.loads(Path(notebook_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    cells = data.get("cells", [])
    if not isinstance(cells, list):
        return {}

    return {
        index: _cell_text(cell)
        for index, cell in enumerate(cells, start=1)
        if isinstance(cell, dict)
    }


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)


def _summary_items(
    comparison: CopyComparison,
    urgent_items: list[str],
    check_items: list[str],
    local_comments: dict[int, list[str]],
) -> list[str]:
    copy = comparison.copy

    items = [
        f"Niveau de corrigeabilité : **{comparison.readiness_level}**.",
        f"Points à corriger avant rendu : **{len(urgent_items)}**.",
        f"Points à vérifier : **{len(check_items)}**.",
        f"Commentaires locaux insérés : **{len(local_comments)}**.",
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

    sources = _cell_sources_by_number(comparison.copy_path)

    for issue in comparison.copy.issues:
        source = sources.get(issue.cell_number, issue.preview)
        if _should_skip_local_comment(issue.kind, source):
            continue

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


def _local_comment_summary_items(local_comments: dict[int, list[str]]) -> list[str]:
    if not local_comments:
        return ["Aucun commentaire local nécessaire."]
    if len(local_comments) == 1:
        return ["Un commentaire local a été inséré après la cellule concernée."]
    return [f"{len(local_comments)} commentaires locaux ont été insérés après les cellules concernées."]


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
