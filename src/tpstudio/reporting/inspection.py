from __future__ import annotations

from pathlib import Path

from tpstudio.models import Notebook, TPDocument


def format_inspection(
    document: TPDocument,
    tex_path: Path,
    manifest_path: Path,
    report_path: Path,
    notebook: Notebook | None = None,
) -> str:
    """Construit l'affichage lisible de la commande `tpstudio inspect`."""

    notebook = notebook if notebook is not None else document.notebook

    lines: list[str] = [
        "TPStudio - Inspection",
        "─────────────────────",
        "",
        f"📄 Fichier LaTeX : {tex_path.name}",
        f"📘 Titre : {document.metadata.title or 'non détecté'}",
    ]

    if document.metadata.session_label or document.metadata.tp_code:
        session = document.metadata.session_label or "séance non détectée"
        code = document.metadata.tp_code or "code TP non détecté"
        lines.append(f"🏷️  Séance : {session} — {code}")

    lines += [
        "",
        _format_general_instructions(document),
        "",
        _format_list("🎯 Objectifs", document.objectives),
        "",
        _format_list("🧰 Matériel", document.equipment),
        "",
        _format_list("❓ Questions", document.questions),
        "",
        _format_teacher_calls(document),
        "",
        _format_sections(document),
        "",
        _format_coherence(document),
        "",
        _format_notebook(notebook),
        "",
        f"✓ Manifest : {manifest_path}",
        f"✓ Rapport : {report_path}",
    ]

    lines += ["", "## Cohérence LaTeX / Notebook", ""]
    lines.extend(_markdown_coherence(document))

    return "\n".join(lines)


def make_inspection_report(document: TPDocument, tex_path: Path, notebook: Notebook | None = None) -> str:
    """Construit le rapport Markdown écrit dans `_build/rapport_inspection.md`."""

    meta = document.metadata
    lines: list[str] = [
        "# Rapport d'inspection TPStudio",
        "",
        f"- Fichier LaTeX : `{tex_path.name}`",
        f"- Titre : {meta.title or 'non détecté'}",
        f"- Séance : {meta.session_label or 'non détectée'}",
        f"- Code TP : {meta.tp_code or 'non détecté'}",
        f"- Slug PDF : {meta.pdf_slug or 'non détecté'}",
        "",
        "## Consignes générales",
        "",
        *_markdown_general_instructions(document),
        "",
        "## Objectifs",
        "",
    ]

    lines.extend(_markdown_items(document.objectives))
    lines += ["", "## Matériel", ""]
    lines.extend(_markdown_items(document.equipment))
    lines += ["", "## Questions", ""]
    lines.extend(_markdown_items(document.questions))
    lines += ["", "## Appels professeur", ""]
    lines.extend(_markdown_teacher_calls(document))
    lines += ["", "## Sections détectées", ""]

    if document.sections:
        for index, section in enumerate(document.sections, start=1):
            lines.append(
                f"{index}. {section.title or 'Section sans titre'} "
                f"(niveau {section.level}, {len(section.items)} item(s))"
            )
    else:
        lines.append("Aucune section détectée.")

    lines += ["", "## Blocs pédagogiques", ""]
    for block in document.blocks:
        if block.kind in {"rapport", "appels"}:
            continue
        lines.append(f"### {block.title} (`{block.kind}`)")
        lines.extend(_markdown_items(block.items))
        lines.append("")

    return "\n".join(lines)



def _format_general_instructions(document: TPDocument) -> str:
    flags: list[str] = []
    if document.metadata.report_required:
        flags.append("✓ rapport demandé")
    if document.metadata.teacher_calls_enabled:
        flags.append("✓ appels professeur activés")

    if not flags:
        return "🧾 Consignes générales\n    aucune consigne générale détectée"

    lines = ["🧾 Consignes générales"]
    lines.extend(f"    {flag}" for flag in flags)
    return "\n".join(lines)


def _markdown_general_instructions(document: TPDocument) -> list[str]:
    items: list[str] = []
    if document.metadata.report_required:
        items.append("- Rapport demandé aux étudiants.")
    if document.metadata.teacher_calls_enabled:
        items.append("- Appels professeur possibles lorsque le symbole apparaît.")
    if not items:
        return ["Aucune consigne générale détectée."]
    return items

def _format_list(title: str, items: list[str]) -> str:
    if not items:
        return f"{title}\n    aucun élément détecté"
    lines = [f"{title} ({len(items)})"]
    lines.extend(f"    • {item}" for item in items)
    return "\n".join(lines)


def _format_teacher_calls(document: TPDocument) -> str:
    calls = document.teacher_calls
    if not calls:
        return "👁 Appels professeur\n    aucun appel détecté"

    lines = [f"👁 Appels professeur ({len(calls)})"]
    for call in calls:
        context = f" — {call.section_title}" if call.section_title else ""
        lines.append(f"    • ligne {call.line}{context} : {call.text}")
    return "\n".join(lines)


def _format_sections(document: TPDocument) -> str:
    if not document.sections:
        return "📚 Sections\n    aucune section détectée"

    lines = [f"📚 Sections ({len(document.sections)})"]
    for index, section in enumerate(document.sections, start=1):
        title = section.title or "Section sans titre"
        item_count = len(section.items)
        lines.append(f"    {index}. {title} — {item_count} item(s)")
    return "\n".join(lines)


def _markdown_teacher_calls(document: TPDocument) -> list[str]:
    if not document.teacher_calls:
        return ["Aucun appel détecté."]

    lines: list[str] = []
    for call in document.teacher_calls:
        context = f" — {call.section_title}" if call.section_title else ""
        lines.append(f"- ligne {call.line}{context} : {call.text}")
    return lines


def _markdown_items(items: list[str]) -> list[str]:
    if not items:
        return ["Aucun élément détecté."]
    return [f"- {item}" for item in items]

def _format_notebook(notebook) -> str:
    if notebook is None:
        return "📓 Notebook\n    aucun notebook détecté"

    name = notebook.path.name if notebook.path else "notebook"
    return "\n".join(
        [
            f"📓 Notebook : {name}",
            f"    • cellules : {notebook.cell_count}",
            f"    • markdown : {notebook.markdown_cell_count}",
            f"    • code : {notebook.code_cell_count}",
            f"    • cellules avec Réponse : {notebook.response_cell_count}",
        ]
    )


def _markdown_notebook(notebook) -> list[str]:
    if notebook is None:
        return ["Aucun notebook détecté."]

    name = notebook.path.name if notebook.path else "notebook"
    return [
        f"- Fichier : `{name}`",
        f"- Cellules : {notebook.cell_count}",
        f"- Markdown : {notebook.markdown_cell_count}",
        f"- Code : {notebook.code_cell_count}",
        f"- Cellules avec `Réponse :` : {notebook.response_cell_count}",
    ]



def _format_coherence(document: TPDocument) -> str:
    """Construit un diagnostic simple de cohérence LaTeX / Notebook.

    Ce diagnostic reste volontairement prudent : il observe des signaux
    faibles sans décider à la place de l'enseignant.
    """

    notebook = getattr(document, "notebook", None)
    sections = getattr(document, "sections", []) or []
    teacher_calls = getattr(document, "teacher_calls", []) or []

    lines = ["🔎 Cohérence LaTeX / Notebook"]

    if notebook is None:
        lines.append("    ⚠ aucun notebook associé détecté")
        if sections:
            lines.append(f"    ℹ {len(sections)} section(s) LaTeX détectée(s)")
        return "\n".join(lines)

    cell_count = _notebook_count(notebook, "cell_count")
    markdown_count = _notebook_count(notebook, "markdown_cell_count")
    code_count = _notebook_count(notebook, "code_cell_count")
    response_count = _notebook_count(notebook, "response_cell_count")

    lines.append("    ✓ notebook trouvé")
    lines.append(f"    ℹ {len(sections)} section(s) LaTeX détectée(s)")
    lines.append(f"    ℹ {cell_count} cellule(s) notebook détectée(s)")

    if response_count == 0:
        lines.append("    ⚠ aucune cellule contenant « Réponse : »")
    else:
        lines.append(f"    ✓ {response_count} cellule(s) contenant « Réponse : »")

    if cell_count == 0:
        lines.append("    ⚠ notebook vide")
    elif markdown_count == 0:
        lines.append("    ⚠ aucune cellule Markdown : notebook très orienté code")
    elif code_count > 2 * markdown_count:
        lines.append(
            f"    ℹ notebook plutôt orienté code ({code_count} code / {markdown_count} markdown)"
        )
    elif markdown_count > 2 * max(code_count, 1):
        lines.append(
            f"    ℹ notebook plutôt orienté texte ({markdown_count} markdown / {code_count} code)"
        )
    else:
        lines.append(
            f"    ✓ équilibre global texte/code ({markdown_count} markdown / {code_count} code)"
        )

    if teacher_calls:
        lines.append(f"    ℹ {len(teacher_calls)} appel(s) professeur dans le LaTeX")

    return "\n".join(lines)


def _markdown_coherence(document: TPDocument) -> list[str]:
    """Version Markdown du diagnostic de cohérence."""

    notebook = getattr(document, "notebook", None)
    sections = getattr(document, "sections", []) or []
    teacher_calls = getattr(document, "teacher_calls", []) or []

    if notebook is None:
        lines = ["- ⚠ Aucun notebook associé détecté."]
        if sections:
            lines.append(f"- {len(sections)} section(s) LaTeX détectée(s).")
        return lines

    cell_count = _notebook_count(notebook, "cell_count")
    markdown_count = _notebook_count(notebook, "markdown_cell_count")
    code_count = _notebook_count(notebook, "code_cell_count")
    response_count = _notebook_count(notebook, "response_cell_count")

    lines = [
        "- ✓ Notebook trouvé.",
        f"- {len(sections)} section(s) LaTeX détectée(s).",
        f"- {cell_count} cellule(s) notebook détectée(s).",
    ]

    if response_count == 0:
        lines.append("- ⚠ Aucune cellule contenant `Réponse :`.")
    else:
        lines.append(f"- ✓ {response_count} cellule(s) contenant `Réponse :`.")

    if cell_count == 0:
        lines.append("- ⚠ Notebook vide.")
    elif markdown_count == 0:
        lines.append("- ⚠ Aucune cellule Markdown : notebook très orienté code.")
    elif code_count > 2 * markdown_count:
        lines.append(
            f"- ℹ Notebook plutôt orienté code : {code_count} cellule(s) code / {markdown_count} cellule(s) Markdown."
        )
    elif markdown_count > 2 * max(code_count, 1):
        lines.append(
            f"- ℹ Notebook plutôt orienté texte : {markdown_count} cellule(s) Markdown / {code_count} cellule(s) code."
        )
    else:
        lines.append(
            f"- ✓ Équilibre global texte/code : {markdown_count} cellule(s) Markdown / {code_count} cellule(s) code."
        )

    if teacher_calls:
        lines.append(f"- ℹ {len(teacher_calls)} appel(s) professeur détecté(s) dans le LaTeX.")

    return lines


def _notebook_count(notebook: object, attr: str) -> int:
    """Récupère un compteur de notebook, même si son nom évolue légèrement."""

    value = getattr(notebook, attr, None)
    if isinstance(value, int):
        return value

    cells = getattr(notebook, "cells", None)
    if not isinstance(cells, list):
        return 0

    if attr == "cell_count":
        return len(cells)

    if attr == "markdown_cell_count":
        return sum(1 for cell in cells if _cell_type(cell) == "markdown")

    if attr == "code_cell_count":
        return sum(1 for cell in cells if _cell_type(cell) == "code")

    if attr == "response_cell_count":
        return sum(1 for cell in cells if "Réponse :" in _cell_source(cell))

    return 0


def _cell_type(cell: object) -> str:
    if isinstance(cell, dict):
        return str(cell.get("cell_type", ""))
    return str(getattr(cell, "cell_type", ""))


def _cell_source(cell: object) -> str:
    if isinstance(cell, dict):
        source = cell.get("source", "")
    else:
        source = getattr(cell, "source", "")

    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)
