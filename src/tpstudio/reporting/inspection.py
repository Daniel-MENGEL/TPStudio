from __future__ import annotations

from pathlib import Path

from tpstudio.models import TPDocument


def format_inspection(
    document: TPDocument,
    tex_path: Path,
    manifest_path: Path,
    report_path: Path,
) -> str:
    """Construit l'affichage lisible de la commande `tpstudio inspect`."""

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
        f"✓ Manifest : {manifest_path}",
        f"✓ Rapport : {report_path}",
    ]

    return "\n".join(lines)


def make_inspection_report(document: TPDocument, tex_path: Path) -> str:
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
        lines.append(f"### {block.title} (`{block.kind}`)")
        lines.extend(_markdown_items(block.items))
        lines.append("")

    return "\n".join(lines)


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
