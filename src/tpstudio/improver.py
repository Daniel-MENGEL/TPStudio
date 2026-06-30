"""Création non destructive de notebooks améliorés.

La commande A18 ne modifie jamais le notebook d'origine. Elle écrit une copie
nouvelle, destinée à être relue et validée par l'enseignant.
"""

from __future__ import annotations

# Génération non destructive de notebooks améliorés.
#
# Ce module contient la logique de la commande `tpstudio improve`.
#
# Principes importants :
# - ne jamais modifier le notebook source ;
# - ignorer les notebooks déjà générés en `-ameliore` comme sources ;
# - utiliser `\\rapport` actif dans le LaTeX pour décider entre grille complète
#   et checklist légère ;
# - placer les cellules de résultat au plus près des sections concernées.


import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable


CORRECTION_MARKERS = (
    "correction",
    "corrige",
    "corrigé",
    "solution",
    "solutions",
    "prof",
    "teacher",
)

STUDENT_MARKERS = (
    "eleve",
    "élève",
    "etudiant",
    "étudiant",
    "student",
)


def improve_notebook(tp_path: Path) -> Path:
    # Améliore un TP à partir d'un dossier ou d'un notebook.
    #
    # Si un notebook élève existe, TPStudio génère une copie améliorée de ce
    # notebook. Si aucun notebook n'existe encore, TPStudio crée une première
    # trame de notebook à partir du fichier LaTeX du TP.

    if tp_path.is_file() and tp_path.suffix == ".ipynb":
        notebook_path = tp_path
        latex_text = _read_latex_text_near(notebook_path)

        output = _next_available_path(
            notebook_path.with_name(f"{notebook_path.stem}-ameliore.ipynb")
        )

        data = json.loads(notebook_path.read_text(encoding="utf-8"))
        _improve_existing_notebook_data(data, latex_text=latex_text)
        _remove_generic_comment_cells(data)
        _reposition_result_cells_by_matching_heading(data)
        _reposition_comparison_after_results(data)

        output.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output

    folder = tp_path

    try:
        notebook_path = _find_source_notebook_for_improve(folder)
    except FileNotFoundError:
        latex_path = _find_latex_file_for_improve(folder)
        return improve_latex_only(latex_path)

    output = _next_available_path(
        notebook_path.with_name(f"{notebook_path.stem}-ameliore.ipynb")
    )

    data = json.loads(notebook_path.read_text(encoding="utf-8"))
    latex_text = _read_latex_text_near(notebook_path)

    _improve_existing_notebook_data(data, latex_text=latex_text)
    _remove_generic_comment_cells(data)
    _reposition_result_cells_by_matching_heading(data)
    _reposition_comparison_after_results(data)

    output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


def improve_latex_only(latex_path: Path) -> Path:
    latex_text = _read_text_file(latex_path)

    output = _next_available_path(
        latex_path.with_name(f"{_slugify(latex_path.stem)}.ipynb")
    )

    data = {
        "cells": _latex_outline_cells(latex_text),
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    data["cells"].extend(_improvement_cells(data, latex_text=latex_text))

    output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


def _find_latex_file_for_improve(folder: Path) -> Path:
    tex_files = sorted(folder.glob("*.tex"))
    if not tex_files:
        raise FileNotFoundError(f"Aucun fichier LaTeX trouvé dans {folder}")

    # S'il y a plusieurs fichiers, on privilégie le plus gros : c'est
    # généralement le fichier principal du TP.
    return max(tex_files, key=lambda path: path.stat().st_size)


def _find_source_notebook_for_improve(folder: Path) -> Path:
    notebooks = sorted(folder.glob("*.ipynb"))
    if not notebooks:
        raise FileNotFoundError(f"Aucun notebook trouvé dans {folder}")

    ignored_markers = (
        "correction",
        "corrige",
        "corrigé",
        "solution",
        "solutions",
        "prof",
        "teacher",
        "ameliore",
        "amélioré",
        "amelioree",
        "améliorée",
    )

    candidates = [
        notebook for notebook in notebooks
        if not any(marker in notebook.stem.lower() for marker in ignored_markers)
    ]

    if candidates:
        return candidates[0]

    return notebooks[0]


def _next_available_path(path: Path) -> Path:
    if not path.exists():
        return path

    suffix = path.suffix
    stem = path.stem
    parent = path.parent

    counter = 2
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _find_student_notebook(tp_dir: Path) -> Path | None:
    notebooks = sorted(
        path for path in tp_dir.glob("*.ipynb")
        if not path.name.startswith(".")
        and not path.name.endswith("-checkpoint.ipynb")
        and "-ameliore" not in path.stem.lower()
    )
    if not notebooks:
        return None

    student_candidates = [
        path for path in notebooks
        if not _looks_like_correction(path)
    ]
    candidates = student_candidates or notebooks

    if len(candidates) == 1:
        return candidates[0]

    folder_words = set(_words(tp_dir.name))
    scored = []
    for path in candidates:
        words = set(_words(path.stem))
        student_bonus = 2 if _looks_like_student(path) else 0
        scored.append((len(folder_words & words) + student_bonus, path))

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _looks_like_correction(path: Path) -> bool:
    name = path.stem.lower()
    return any(marker in name for marker in CORRECTION_MARKERS)


def _looks_like_student(path: Path) -> bool:
    name = path.stem.lower()
    return any(marker in name for marker in STUDENT_MARKERS)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ0-9]+", text.lower())


def _available_output_path(path: Path) -> Path:
    if not path.exists():
        return path

    for index in range(2, 100):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate

    raise FileExistsError(f"Impossible de trouver un nom disponible pour {path}")


def _improve_existing_notebook_data(data: dict, latex_text: str = "") -> None:
    # Ajoute des cellules d'amélioration à des emplacements plus pédagogiques.
    # Le notebook source n'est jamais modifié : cette fonction ne travaille
    # que sur la copie chargée en mémoire avant écriture.

    cells = data.setdefault("cells", [])
    existing_text = _notebook_text(data).lower()

    _insert_measurement_result_cells(cells)

    contextual_insertions = _contextual_improvement_cells(existing_text)
    improvement_cells = _improvement_cells(data, latex_text=latex_text)

    if contextual_insertions:
        insertion_index = _before_improvements_insertion_index(cells, improvement_cells)
        cells[insertion_index:insertion_index] = contextual_insertions

    cells.extend(improvement_cells)


def _insert_measurement_result_cells(cells: list[dict]) -> None:
    # Insère les zones de résultats au plus près des parties concernées.
    # Pour le moment, l'heuristique s'appuie sur les titres et sur quelques
    # marqueurs de code courants.

    if _notebook_already_contains_generated_kind(cells, "measurement_result"):
        return

    headings = _notebook_headings_from_cells(cells)
    suggestions: list[dict] = []
    seen: set[str] = set()

    for heading in headings:
        suggestion = _result_prompt_from_heading(heading)
        if suggestion is None:
            continue

        suggestion["source_heading"] = heading

        key = suggestion["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(suggestion)

    insertions: list[tuple[int, dict]] = []

    for suggestion in suggestions:
        cell = _result_cell_from_suggestion(suggestion)
        index = _measurement_result_insertion_index(cells, suggestion)
        insertions.append((index, cell))

    if len(suggestions) >= 2 and not _notebook_contains_title(cells, "comparaison des résultats obtenus"):
        comparison_cell = _generated_markdown_cell(
            [
                "### Comparaison des résultats obtenus\n",
                "\n",
                "**Réponse :**\n",
                "\n",
                "Comparer les différentes valeurs mesurées lorsqu'elles concernent une même grandeur physique ou des méthodes différentes.\n",
                "\n",
                "On attend notamment :\n",
                "- les valeurs comparées avec leurs incertitudes ;\n",
                "- le calcul éventuel d'un écart normalisé ;\n",
                "- une conclusion sur la compatibilité des résultats.\n",
            ],
            kind="measurement_comparison",
        )
        insertions.append((_comparison_insertion_index(cells), comparison_cell))

    # Insertion en partant de la fin pour ne pas décaler les indices déjà calculés.
    for index, cell in sorted(insertions, key=lambda item: item[0], reverse=True):
        cells[index:index] = [cell]


def _result_cell_from_suggestion(suggestion: dict) -> dict:
    return _generated_markdown_cell(
        [
            f"### Résultat — {suggestion['title']}\n",
            "\n",
            "**Réponse :**\n",
            "\n",
            suggestion["intro"] + "\n",
            "\n",
            "On attend notamment :\n",
            *[f"- {item}\n" for item in suggestion["items"]],
        ],
        kind="measurement_result",
    )


def _measurement_result_insertion_index(cells: list[dict], suggestion: dict) -> int:
    title = suggestion.get("title", "").lower()
    source_heading = suggestion.get("source_heading", "")

    if "angle au sommet" in title or ("angle" in title and "prisme" in title):
        # Cas du goniomètre : le résultat sur A clôt la partie angle,
        # juste avant la vraie partie sur l'indice.
        index = _find_specific_heading_index(
            cells,
            required=("mesure", "indice", "prisme"),
            min_level=2,
        )
        if index is not None:
            return index

    if "indice" in title and "prisme" in title:
        # Cas du goniomètre : le résultat sur n vient après le calcul de n.
        index = _find_code_index_after_marker(cells, ("#calcul de n", "calcul de n", "calcul n"))
        if index is not None:
            return index + 1

    # Cas général : placer le résultat à la fin de la section qui a déclenché
    # la suggestion, et non pas avant une section vaguement ressemblante.
    heading_index = _find_exact_heading_index(cells, source_heading)
    if heading_index is not None:
        next_same_or_higher = _find_next_heading_index_same_or_higher_level(cells, heading_index + 1, heading_index)
        section_end = next_same_or_higher if next_same_or_higher is not None else len(cells)
        last_code = _find_last_code_index(cells, heading_index + 1, section_end)
        if last_code is not None:
            return last_code + 1
        return section_end

    return _best_contextual_insertion_index(cells)


def _comparison_insertion_index(cells: list[dict]) -> int:
    # La comparaison doit suivre le calcul d'écart normalisé quand il existe.
    index = _find_code_index_after_marker(cells, ("écart normalisé", "ecart normalisé", "ecart normalise"))
    if index is not None:
        return index + 1
    return _best_contextual_insertion_index(cells)


def _notebook_headings_from_cells(cells: list[dict]) -> list[str]:
    headings: list[str] = []
    for cell in cells:
        if cell.get("cell_type") != "markdown":
            continue
        for line in _cell_text(cell).splitlines():
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue
            title = stripped.lstrip("#").strip()
            if title:
                headings.append(title)
    return headings


def _result_prompt_from_heading(heading: str) -> dict | None:
    normalized = heading.lower()

    if _looks_like_import_or_general_heading(normalized):
        return None

    if "angle" in normalized and ("prisme" in normalized or "sommet" in normalized or " a" in normalized):
        return {
            "title": "Angle au sommet du prisme",
            "intro": "Présenter ici la valeur mesurée de l'angle au sommet du prisme, avec son incertitude.",
            "items": [
                "les angles mesurés au goniomètre ;",
                "la méthode utilisée pour déterminer l'angle A ;",
                "la valeur finale de A avec son incertitude ;",
                "un court commentaire sur la précision de la mesure.",
            ],
        }

    if "indice" in normalized and ("prisme" in normalized or "$n$" in normalized or " n" in normalized):
        return {
            "title": "Indice du prisme",
            "intro": "Présenter ici la valeur obtenue pour l'indice du prisme, avec son incertitude.",
            "items": [
                "la valeur de l'angle au minimum de déviation si elle intervient ;",
                "la formule ou la méthode de calcul utilisée ;",
                "la valeur finale de n avec son incertitude ;",
                "une comparaison éventuelle avec une valeur attendue.",
            ],
        }

    if "masse en eau" in normalized:
        return {
            "title": "Masse en eau du calorimètre",
            "intro": "Présenter ici la masse en eau du calorimètre obtenue expérimentalement.",
            "items": [
                "les mesures de température et de masse utilisées ;",
                "le bilan énergétique exploité ;",
                "la valeur finale avec son incertitude ;",
                "un commentaire sur les principales sources d'erreur.",
            ],
        }

    if "capacité thermique" in normalized or "capacite thermique" in normalized:
        return {
            "title": _clean_heading_for_result_title(heading),
            "intro": "Présenter ici la capacité thermique déterminée expérimentalement.",
            "items": [
                "les grandeurs mesurées ;",
                "le bilan énergétique ou la relation utilisée ;",
                "la valeur finale avec son incertitude ;",
                "une comparaison éventuelle avec une valeur tabulée.",
            ],
        }

    if "chaleur latente" in normalized or "fusion" in normalized:
        return {
            "title": "Chaleur latente de fusion",
            "intro": "Présenter ici la valeur expérimentale de la chaleur latente de fusion.",
            "items": [
                "les mesures nécessaires au bilan énergétique ;",
                "la relation utilisée ;",
                "la valeur finale avec son incertitude ;",
                "une comparaison avec une valeur attendue.",
            ],
        }

    if any(marker in normalized for marker in ("mesure", "détermination", "determination")):
        return {
            "title": _clean_heading_for_result_title(heading),
            "intro": "Présenter ici le résultat expérimental associé à cette partie.",
            "items": [
                "les mesures utilisées ;",
                "la méthode d'exploitation ;",
                "la valeur finale avec son incertitude si elle est disponible ;",
                "un court commentaire sur la cohérence du résultat.",
            ],
        }

    return None


def _find_exact_heading_index(cells: list[dict], heading: str) -> int | None:
    target = _normalize_heading_title(heading)
    if not target:
        return None

    for index, cell in enumerate(cells):
        if cell.get("cell_type") != "markdown":
            continue
        for line in _cell_text(cell).splitlines():
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue
            title = stripped.lstrip("#").strip()
            if _normalize_heading_title(title) == target:
                return index

    return None


def _find_next_heading_index_same_or_higher_level(
    cells: list[dict],
    start: int,
    reference_index: int,
) -> int | None:
    reference_level = _first_heading_level(cells[reference_index])
    if reference_level is None:
        return _find_next_heading_index(cells, start)

    for index in range(start, len(cells)):
        if cells[index].get("cell_type") != "markdown":
            continue
        level = _first_heading_level(cells[index])
        if level is not None and level <= reference_level:
            return index

    return None


def _first_heading_level(cell: dict) -> int | None:
    for line in _cell_text(cell).splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return len(stripped) - len(stripped.lstrip("#"))
    return None


def _normalize_heading_title(title: str) -> str:
    cleaned = title.replace("<center>", "").replace("</center>", "")
    cleaned = cleaned.replace("**", "").replace("$", "")
    cleaned = cleaned.replace("\\", "")
    cleaned = " ".join(cleaned.lower().split())
    return cleaned


def _find_specific_heading_index(
    cells: list[dict],
    required: tuple[str, ...],
    min_level: int = 1,
) -> int | None:
    for index, cell in enumerate(cells):
        if cell.get("cell_type") != "markdown":
            continue

        for line in _cell_text(cell).splitlines():
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue

            level = len(stripped) - len(stripped.lstrip("#"))
            if level < min_level:
                continue

            title = stripped.lstrip("#").strip().lower()
            if all(marker in title for marker in required):
                return index

    return None


def _find_heading_index(cells: list[dict], markers: tuple[str, ...]) -> int | None:
    for index, cell in enumerate(cells):
        if cell.get("cell_type") != "markdown":
            continue
        source = _cell_text(cell).lower()
        lines = [line.strip() for line in source.splitlines()]
        heading_lines = [line for line in lines if line.startswith("#")]
        if any(all(marker in line for marker in markers) for line in heading_lines):
            return index
    return None


def _find_heading_index_from_words(cells: list[dict], words: set[str]) -> int | None:
    if not words:
        return None
    for index, cell in enumerate(cells):
        if cell.get("cell_type") != "markdown":
            continue
        for line in _cell_text(cell).lower().splitlines():
            if not line.strip().startswith("#"):
                continue
            line_words = _important_words(line)
            if words & line_words:
                return index
    return None


def _find_next_heading_index(cells: list[dict], start: int) -> int | None:
    for index in range(start, len(cells)):
        if cells[index].get("cell_type") != "markdown":
            continue
        if any(line.strip().startswith("#") for line in _cell_text(cells[index]).splitlines()):
            return index
    return None


def _find_last_code_index(cells: list[dict], start: int, end: int) -> int | None:
    for index in range(end - 1, start - 1, -1):
        if cells[index].get("cell_type") == "code":
            return index
    return None


def _find_code_index_after_marker(cells: list[dict], markers: tuple[str, ...]) -> int | None:
    for index in range(len(cells) - 1, -1, -1):
        if cells[index].get("cell_type") != "code":
            continue
        source = _cell_text(cells[index]).lower()
        if any(marker in source for marker in markers):
            return index
    return None


def _important_words(text: str) -> set[str]:
    words = set(_words(text))
    ignored = {
        "resultat", "résultat", "mesure", "mesures", "du", "de", "des",
        "la", "le", "les", "au", "aux", "d", "l", "un", "une",
    }
    return {word for word in words if word not in ignored and len(word) >= 3}


def _notebook_already_contains_generated_kind(cells: list[dict], kind: str) -> bool:
    for cell in cells:
        metadata = cell.get("metadata", {})
        tpstudio = metadata.get("tpstudio", {}) if isinstance(metadata, dict) else {}
        if tpstudio.get("kind") == kind:
            return True
    return False


def _notebook_contains_title(cells: list[dict], title: str) -> bool:
    target = title.lower()
    return any(target in _cell_text(cell).lower() for cell in cells)


def _looks_like_import_or_general_heading(normalized: str) -> bool:
    markers = (
        "importation",
        "bibliothèque",
        "bibliotheque",
        "fonctions utiles",
        "texte du tp",
        "<center>",
    )
    return any(marker in normalized for marker in markers)


def _clean_heading_for_result_title(heading: str) -> str:
    title = heading.replace("<center>", "").replace("</center>", "")
    title = title.replace("**", "").replace("$", "")
    title = " ".join(title.split())
    return title.strip() or "Résultat expérimental"


def _contextual_improvement_cells(existing_text: str) -> list[dict]:
    # A19e : on reste volontairement sobre.
    #
    # Les cellules de type "Résultat — ..." et "Comparaison des résultats"
    # portent déjà la rédaction attendue. On évite donc d'ajouter une
    # "Réponse guidée" générique ou un "Commentaire / interprétation" qui
    # ferait doublon.
    #
    # On ajoute seulement une conclusion si le notebook n'en contient pas.

    cells: list[dict] = []

    if not any(marker in existing_text for marker in ("conclusion", "bilan", "synthèse")):
        cells.append(_generated_markdown_cell(
            [
                "### Conclusion / bilan\n",
                "\n",
                "**Réponse :**\n",
                "\n",
                "À compléter par l'étudiant : résumer les résultats principaux du TP et indiquer les limites de la méthode utilisée.\n",
            ],
            kind="contextual_conclusion",
        ))

    return cells


def _before_improvements_insertion_index(cells: list[dict], improvement_cells: list[dict]) -> int:
    # Place les cellules de conclusion juste avant le bloc final
    # "Améliorations proposées par TPStudio".
    #
    # Dans l'état actuel, ce bloc final n'est pas encore dans cells :
    # il sera ajouté juste après. L'emplacement voulu est donc la fin
    # actuelle du notebook.

    return len(cells)


def _best_contextual_insertion_index(cells: list[dict]) -> int:
    # Choisit un emplacement raisonnable pour les cellules de rédaction.

    for index, cell in enumerate(cells):
        source = _cell_text(cell).lower()
        if "évaluation par compétences" in source or "evaluation par competences" in source:
            return index

    for index in range(len(cells) - 1, -1, -1):
        if cells[index].get("cell_type") == "code":
            return index + 1

    return len(cells)


def _notebook_text(data: dict) -> str:
    return "\n".join(_cell_text(cell) for cell in data.get("cells", []))


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(item) for item in source)
    return str(source)


def _generated_markdown_cell(source: list[str], kind: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {
            "tpstudio": {
                "generated": True,
                "kind": kind,
            }
        },
        "source": source,
    }


def _latex_outline_cells(latex_text: str) -> list[dict]:
    cells: list[dict] = []

    title = _extract_latex_title(latex_text)
    if title:
        cells.append(_markdown_cell([f"# {title}\n"], kind="latex_outline_title"))

    sections = _extract_latex_sections(latex_text)
    if not sections:
        cells.append(_markdown_cell([
            "## Travail à compléter\n",
            "\n",
            "**Réponse :**\n",
            "\n",
            "Compléter cette partie à partir du texte du TP.\n",
        ], kind="latex_outline_fallback"))
        return cells

    for section in sections:
        cells.append(_markdown_cell([
            f"## {section}\n",
            "\n",
            "### Objectif\n",
            "\n",
            "À préciser à partir du texte du TP.\n",
            "\n",
            "### Travail à réaliser\n",
            "\n",
            "**Réponse :**\n",
            "\n",
            "Compléter cette partie pendant la séance.\n",
        ], kind="latex_outline_section"))

    return cells


def _extract_latex_title(latex_text: str) -> str:
    match = re.search(r"\\title\{([^}]*)\}", latex_text)
    if match:
        return _clean_latex_text(match.group(1))
    return ""


def _extract_latex_sections(latex_text: str) -> list[str]:
    pattern = re.compile(r"\\(?:section|subsection)\*?\{([^}]*)\}")
    sections: list[str] = []
    for match in pattern.finditer(latex_text):
        title = _clean_latex_text(match.group(1))
        if title:
            sections.append(title)
    return sections


def _clean_latex_text(text: str) -> str:
    cleaned = re.sub(r"\\[A-Za-z]+\*?(?:\[[^]]*\])?", "", text)
    cleaned = cleaned.replace("{", "").replace("}", "")
    cleaned = cleaned.replace("$", "")
    cleaned = " ".join(cleaned.split())
    return cleaned


def _markdown_cell(source: list[str]) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source,
    }


def _reposition_comparison_after_results(data: dict) -> None:
    """Place la comparaison après les cellules Résultat qui la précèdent logiquement.

    Dans certains notebooks, TPStudio insère d'abord une cellule
    ``Comparaison des résultats obtenus`` puis ajoute ensuite un dernier bloc
    ``Résultat — ...``. La comparaison doit venir après les résultats à
    comparer, et avant les blocs globaux de fin.
    """

    cells = data.get("cells", [])
    if not isinstance(cells, list):
        return

    for comparison_index, cell in enumerate(list(cells)):
        if not _is_comparison_cell(cell):
            continue

        end_index = _next_global_end_index(cells, comparison_index + 1)
        last_result_index = None

        for index in range(comparison_index + 1, end_index):
            candidate = cells[index]
            if _is_result_cell(candidate):
                last_result_index = index

        if last_result_index is None:
            continue

        moved_cell = cells.pop(comparison_index)

        if comparison_index < last_result_index:
            last_result_index -= 1

        cells.insert(last_result_index + 1, moved_cell)
        return


def _is_comparison_cell(cell: dict) -> bool:
    if cell.get("cell_type") != "markdown":
        return False

    first_line = _first_non_empty_line(cell)
    key = _placement_key(first_line.lstrip("#").strip())
    return key == "comparaison resultats obtenus"


def _is_result_cell(cell: dict) -> bool:
    if cell.get("cell_type") != "markdown":
        return False

    first_line = _first_non_empty_line(cell)
    return first_line.startswith("### Résultat —")


def _next_global_end_index(cells: list[dict], start: int) -> int:
    for index in range(start, len(cells)):
        first_line = _first_non_empty_line(cells[index])
        if _is_global_end_heading(first_line):
            return index
    return len(cells)


def _first_non_empty_line(cell: dict) -> str:
    for line in _cell_text(cell).splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _remove_generic_comment_cells(data: dict) -> None:
    """Supprime les anciennes cellules génériques de commentaire.

    Ces cellules, du type ``🧠 Commentez :``, sont trop vagues pour être
    conservées systématiquement dans les notebooks améliorés. TPStudio préfère
    maintenant insérer des cellules plus contextualisées : résultat, comparaison,
    conclusion ou bilan.
    """

    cells = data.get("cells", [])
    if not isinstance(cells, list):
        return

    filtered_cells = []
    for cell in cells:
        if _is_generic_comment_cell(cell):
            continue
        filtered_cells.append(cell)

    data["cells"] = filtered_cells


def _is_generic_comment_cell(cell: dict) -> bool:
    if cell.get("cell_type") != "markdown":
        return False

    text = _cell_text(cell).strip()
    if not text:
        return False

    first_line = text.splitlines()[0].strip()
    return first_line.startswith("🧠 Commentez")


def _reposition_result_cells_by_matching_heading(data: dict) -> None:
    """Replace les cellules Résultat près du sous-titre correspondant.

    Si une cellule ``### Résultat — X`` correspond à un sous-titre ``### X``
    déjà présent dans le notebook, elle est replacée à la fin de ce bloc,
    avant le sous-titre suivant de même niveau.

    La boucle est bornée pour éviter tout risque d'oscillation sur un notebook
    atypique.
    """

    cells = data.get("cells", [])
    if not isinstance(cells, list):
        return

    seen_states: set[tuple[str, ...]] = set()
    max_moves = max(len(cells), 1)

    for _ in range(max_moves):
        state = tuple(_first_non_empty_line(cell) for cell in cells)
        if state in seen_states:
            return
        seen_states.add(state)

        changed = _apply_one_result_reposition(data)
        if not changed:
            return
def _apply_one_result_reposition(data: dict) -> bool:
    cells = data.get("cells", [])
    if not isinstance(cells, list):
        return False

    for result_index, cell in enumerate(cells):
        if cell.get("cell_type") != "markdown":
            continue

        source = _cell_text(cell)
        lines = source.splitlines()
        first_line = lines[0].strip() if lines else ""

        if not first_line.startswith("### Résultat —"):
            continue

        result_title = first_line.replace("### Résultat —", "", 1).strip()
        result_key = _placement_key(result_title)
        if not result_key:
            continue

        heading_index = _find_matching_non_result_heading(cells, result_key)
        if heading_index is None:
            continue

        heading_level = _matching_heading_level(cells[heading_index], result_key)
        target_index = _end_of_heading_block_for_result(
            cells,
            heading_index,
            heading_level=heading_level,
        )

        if target_index == result_index or target_index == result_index + 1:
            continue

        moved_cell = cells.pop(result_index)
        if result_index < target_index:
            target_index -= 1
        cells.insert(target_index, moved_cell)
        return True

    return False


def _matching_heading_level(cell: dict, result_key: str) -> int | None:
    if cell.get("cell_type") != "markdown":
        return None

    for line in _cell_text(cell).splitlines():
        stripped = line.strip()
        match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if not match:
            continue

        heading_text = match.group(2).strip()
        heading_key = _placement_key(heading_text)

        if heading_key == result_key:
            return len(match.group(1))

    return None


def _find_matching_non_result_heading(cells: list[dict], result_key: str) -> int | None:
    for index, cell in enumerate(cells):
        if cell.get("cell_type") != "markdown":
            continue

        for line in _cell_text(cell).splitlines():
            stripped = line.strip()

            if not stripped.startswith("#"):
                continue
            if "Résultat —" in stripped:
                continue

            heading_text = stripped.lstrip("#").strip()
            heading_key = _placement_key(heading_text)

            if heading_key == result_key:
                return index

    return None


def _end_of_heading_block_for_result(
    cells: list[dict],
    heading_index: int,
    heading_level: int | None = None,
) -> int:
    if heading_level is None:
        heading_level = _markdown_heading_level(cells[heading_index])

    index = heading_index + 1
    last_content_index = heading_index

    while index < len(cells):
        cell = cells[index]
        level = _markdown_heading_level(cell)

        text = _cell_text(cell).strip()
        lines = text.splitlines()
        first_line = lines[0].strip() if lines else ""

        # Certains titres ajoutés par TPStudio sont des blocs de fin globaux.
        # Ils ne doivent jamais être considérés comme faisant partie de la
        # dernière section expérimentale du TP, même s'ils sont écrits en ###.
        if _is_global_end_heading(first_line):
            break

        if level is not None and heading_level is not None and level <= heading_level:
            break

        if first_line.startswith("### Résultat —"):
            index += 1
            continue

        # On place le résultat après le contenu utile de la sous-partie,
        # mais avant les cellules de commentaire guidé.
        if cell.get("cell_type") == "code":
            last_content_index = index
        elif cell.get("cell_type") == "markdown" and text and not text.startswith("🧠"):
            last_content_index = index

        index += 1

    return last_content_index + 1


def _is_global_end_heading(first_line: str) -> bool:
    if not first_line.startswith("#"):
        return False

    title = first_line.lstrip("#").strip()
    key = _placement_key(title)

    global_markers = {
        "conclusion bilan",
        "ameliorations proposees par tpstudio",
        "evaluation par competences",
        "checklist fin tp",
    }

    return key in global_markers


def _markdown_heading_level(cell: dict) -> int | None:
    if cell.get("cell_type") != "markdown":
        return None

    for line in _cell_text(cell).splitlines():
        stripped = line.strip()
        match = re.match(r"^(#{1,6})\s+", stripped)
        if match:
            return len(match.group(1))

    return None


def _placement_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        char for char in normalized
        if not unicodedata.combining(char)
    )

    lowered = without_accents.lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)

    stopwords = {"de", "la", "le", "l", "d", "du", "des"}
    tokens = [token for token in lowered.split() if token not in stopwords]
    return " ".join(tokens)


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    return str(source)


def _improvement_cells(data: dict, latex_text: str = "") -> list[dict]:
    existing_text = "\n".join(
        "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        for cell in data.get("cells", [])
    ).lower()

    suggestions = _suggestions_from_notebook_text(existing_text)

    lines = [
        "---\n",
        "\n",
        "## 🛠 Améliorations proposées par TPStudio\n",
        "\n",
        "> Cette section a été ajoutée automatiquement.  \n",
        "> Elle sert de base de travail et doit être relue avant diffusion aux étudiants.\n",
        "\n",
        "### Points à vérifier\n",
        "\n",
    ]

    for suggestion in suggestions:
        lines.append(f"- {suggestion}\n")

    lines.extend([
        "\n",
        "> Les propositions ci-dessus ne modifient pas le travail demandé : elles indiquent seulement les zones qui pourraient être mieux guidées ou mieux explicitées.\n",
    ])

    improvement_cell = {
        "cell_type": "markdown",
        "metadata": {
            "tpstudio": {
                "generated": True,
                "kind": "improvement_plan",
            }
        },
        "source": lines,
    }

    return [
        improvement_cell,
        _evaluation_cell_for_context(latex_text),
    ]



def _suggestions_from_notebook_text(text: str) -> list[str]:
    suggestions: list[str] = []

    if "protocole" not in text:
        suggestions.append("Ajouter une zone **Protocole** pour expliciter la démarche expérimentale.")

    if not any(marker in text for marker in ("commentaire", "interprétation", "interpreter", "interpréter", "analyse")):
        suggestions.append("Ajouter une zone **Commentaire / interprétation** après les résultats importants.")

    if not any(marker in text for marker in ("conclusion", "bilan", "synthèse")):
        suggestions.append("Ajouter une zone **Conclusion / bilan** en fin de notebook.")

    if "réponse" not in text and "reponse" not in text:
        suggestions.append("Ajouter des zones **Réponse :** aux endroits où l'élève doit rédiger.")

    if not any(marker in text for marker in ("évaluation", "evaluation", "barème", "bareme", "grille")):
        suggestions.append("Ajouter éventuellement une courte grille d'évaluation si le notebook sert de rapport complet.")

    if not suggestions:
        suggestions.append("Conserver la structure actuelle et harmoniser seulement la forme si nécessaire.")

    return suggestions[:6]



def _evaluation_cell_for_context(latex_text: str) -> dict:
    if _has_report_instruction(latex_text):
        return _evaluation_grid_cell()
    return _light_end_of_tp_checklist_cell()


def _has_report_instruction(latex_text: str) -> bool:
    if not latex_text:
        return False

    for line in latex_text.splitlines():
        active_part = line.split("%", 1)[0]
        if "\\rapport" in active_part:
            return True

    return False


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _read_latex_text_near(notebook_path: Path) -> str:
    folder = notebook_path.parent
    tex_files = sorted(folder.glob("*.tex"))
    if not tex_files:
        return ""

    parts: list[str] = []
    for tex_file in tex_files:
        try:
            content = tex_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = tex_file.read_text(encoding="latin-1")
        parts.append(f"\n% --- TPStudio source: {tex_file.name} ---\n")
        parts.append(content)

    return "\n".join(parts)


def _light_end_of_tp_checklist_cell() -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {
            "tpstudio": {
                "generated": True,
                "kind": "light_end_of_tp_checklist",
            }
        },
        "source": [
            "## ✅ Checklist de fin de TP\n",
            "\n",
            "> Cette checklist est indicative. Elle sert à vérifier que le notebook est exploitable et compréhensible, sans transformer le TP en rapport complet.\n",
            "\n",
            "| Point à vérifier | Fait |\n",
            "|---|:---:|\n",
            "| Les mesures principales sont indiquées avec leurs unités | ☐ |\n",
            "| Les calculs importants sont présents et lisibles | ☐ |\n",
            "| Les résultats finaux sont clairement identifiés | ☐ |\n",
            "| Les incertitudes ou écarts sont mentionnés lorsque c'est pertinent | ☐ |\n",
            "| Les comparaisons demandées sont commentées brièvement | ☐ |\n",
            "| Le bilan final résume ce qui a été obtenu | ☐ |\n",
        ],
    }


def _evaluation_grid_cell() -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {
            "tpstudio": {
                "generated": True,
                "kind": "evaluation_grid",
            }
        },
        "source": [
            "---\n",
            "\n",
            "## 📊 Évaluation par compétences\n",
            "\n",
            "> Donnée à titre indicatif. Cette partie sera complétée par le professeur au moment de la correction.\n",
            "\n",
            "| Compétence évaluée | Barème |\n",
            "|---|---:|\n",
            "| Rappeler les objectifs du TP | /1 |\n",
            "| Expliquer succinctement la problématique de chaque manipulation effectuée : que cherche-t-on à mesurer et pourquoi ? | /3 |\n",
            "| Écrire précisément le protocole de mesure utilisé : appareillage, figures descriptives, difficultés rencontrées | /3 |\n",
            "| Présenter les valeurs mesurées : tableaux, courbes annotées, valeurs avec incertitudes justifiées et commentées | /3 |\n",
            "| Interpréter les résultats obtenus : comparaison aux valeurs attendues, explication des écarts éventuels | /3 |\n",
            "| Nombre de questions résolues | /3 |\n",
            "\n",
            "### Formule indicative\n",
            "\n",
            "La note est calculée avec la formule :\n",
            "\n",
            "$$20\\times\\left(0,9+\\frac{a}{10}\\right)\\times\\left(0,7+\\frac{b}{10}\\right)\\times\\left(0,7+\\frac{c}{10}\\right)\\times\\left(0,7+\\frac{d}{10}\\right)\\times\\left(0,7+\\frac{e}{10}\\right)\\times\\left(0,7+\\frac{f}{10}\\right)$$\n",
            "\n",
            "avec $a$ la note d'objectifs, puis $b,c,d,e,f$ les notes sur 3 pour les autres compétences.\n",
        ],
    }



def _create_initial_notebook_from_latex(tp_dir: Path) -> Path:
    tex_file = _find_latex_file(tp_dir)
    title = tex_file.stem if tex_file else tp_dir.name
    tex_text = tex_file.read_text(encoding="utf-8", errors="ignore") if tex_file else ""

    sections = _extract_latex_sections(tex_text)
    questions = _extract_latex_questions(tex_text)

    output = _available_output_path(tp_dir / f"{_slugify(title)}.ipynb")

    cells: list[dict] = [
        _markdown_cell([
            f"# {title}\n",
            "\n",
            "> Notebook créé automatiquement par TPStudio à partir du fichier LaTeX.\n",
            "> À relire et compléter avant diffusion.\n",
        ], kind="generated_title")
    ]

    if sections:
        for section in sections:
            cells.append(_markdown_cell([
                f"## {section}\n",
                "\n",
                "### Protocole\n",
                "\n",
                "À compléter.\n",
                "\n",
                "### Réponse :\n",
                "\n",
                "À rédiger.\n",
            ], kind="generated_section"))
    elif questions:
        cells.append(_markdown_cell(["## Questions et réponses\n"], kind="generated_section"))
        for question in questions:
            cells.append(_markdown_cell([
                f"### {question}\n",
                "\n",
                "**Réponse :**\n",
                "\n",
                "À rédiger.\n",
            ], kind="generated_question"))
    else:
        cells.append(_markdown_cell([
            "## Travail à réaliser\n",
            "\n",
            "**Réponse :**\n",
            "\n",
            "À rédiger.\n",
        ], kind="generated_section"))

    cells.append(_evaluation_grid_cell())

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "pygments_lexer": "ipython3",
            },
            "tpstudio": {
                "generated": True,
                "source": "latex",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    output.write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def _find_latex_file(tp_dir: Path) -> Path | None:
    files = sorted(tp_dir.glob("*.tex"))
    if not files:
        return None

    preferred = [path for path in files if not path.name.startswith("_")]
    return preferred[0] if preferred else files[0]


def _extract_latex_sections(text: str) -> list[str]:
    pattern = re.compile(r"\\(?:section|subsection)\*?\{([^{}]+)\}")
    sections = [_clean_latex(match.group(1)) for match in pattern.finditer(text)]
    return _unique_non_empty(sections)[:12]


def _extract_latex_questions(text: str) -> list[str]:
    patterns = [
        re.compile(r"\\question\*?\{([^{}]+)\}"),
        re.compile(r"\\item\s+([^\n]+)"),
    ]
    questions: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            candidate = _clean_latex(match.group(1))
            if "?" in candidate or len(candidate) > 25:
                questions.append(candidate)
    return _unique_non_empty(questions)[:12]


def _clean_latex(text: str) -> str:
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _unique_non_empty(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if item and key not in seen:
            result.append(item)
            seen.add(key)
    return result


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        char for char in normalized
        if not unicodedata.combining(char)
    )

    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", without_accents)
    cleaned = cleaned.strip("-")
    return cleaned or "notebook"


def _markdown_cell(source: list[str], kind: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {
            "tpstudio": {
                "generated": True,
                "kind": kind,
            }
        },
        "source": source,
    }
