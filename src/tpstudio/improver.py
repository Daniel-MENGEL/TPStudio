"""Création non destructive de notebooks améliorés.

La commande A18 ne modifie jamais le notebook d'origine. Elle écrit une copie
nouvelle, destinée à être relue et validée par l'enseignant.
"""

from __future__ import annotations

import json
import re
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


def improve_notebook(tp_dir: Path) -> Path:
    """Crée une copie améliorée du notebook associé à un dossier de TP.

    Si un notebook existe, il est copié puis enrichi avec une section finale.
    Si aucun notebook n'existe, une première ébauche est créée à partir du
    fichier LaTeX du dossier.
    """

    tp_dir = Path(tp_dir)
    if not tp_dir.exists():
        raise FileNotFoundError(f"Dossier introuvable : {tp_dir}")

    notebook = _find_student_notebook(tp_dir)
    if notebook is None:
        return _create_initial_notebook_from_latex(tp_dir)

    output = _available_output_path(notebook.with_name(f"{notebook.stem}-ameliore.ipynb"))
    data = json.loads(notebook.read_text(encoding="utf-8"))

    cells = data.setdefault("cells", [])
    cells.extend(_improvement_cells(data))

    output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


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


def _improvement_cells(data: dict) -> list[dict]:
    existing_text = "\n".join(
        "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        for cell in data.get("cells", [])
    ).lower()

    suggestions = _suggestions_from_notebook_text(existing_text)

    lines = [
        "## Améliorations proposées\n",
        "\n",
        "> Cette section a été ajoutée automatiquement par TPStudio.\n",
        "> Elle sert de base de travail et doit être relue avant diffusion aux étudiants.\n",
        "\n",
    ]

    for suggestion in suggestions:
        lines.append(f"- {suggestion}\n")

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
        _evaluation_grid_cell(),
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
            "## Évaluation par compétences\n",
            "\n",
            "Donnée à titre indicatif, cette partie sera complétée par le professeur au moment de la correction.\n",
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
    text = re.sub(r"[^a-zA-ZÀ-ÿ0-9]+", "-", text).strip("-")
    return text or "notebook"


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
