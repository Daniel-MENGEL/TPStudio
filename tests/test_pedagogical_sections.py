from __future__ import annotations

from pathlib import Path

import nbformat

from tpstudio.pedagogical_sections import (
    add_pedagogical_section_feedback_to_notebook,
    add_pedagogical_section_feedback_to_report,
    analyze_pedagogical_sections_in_notebook,
)


def _notebook(*sources: str):
    return nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(source)
            for source in sources
        ]
    )


def test_fragile_protocol_is_detected() -> None:
    notebook = _notebook(
        "## Protocole\n\nOn utilise le matériel qui nous a été fourni."
    )

    findings = analyze_pedagogical_sections_in_notebook(notebook)

    assert len(findings) == 1
    assert findings[0].section_kind == "protocole"
    assert findings[0].status == "fragile"
    assert "formulation trop générale" in findings[0].reasons


def test_detailed_protocol_is_not_flagged_as_weak() -> None:
    notebook = _notebook(
        "## Protocole\n\n"
        "Nous plaçons le disque gradué devant le laser et nous alignons le rayon "
        "sur le centre du disque. Nous choisissons plusieurs angles d'incidence, "
        "nous relevons pour chacun l'angle de réfraction puis nous reportons les "
        "mesures dans un tableau avant de calculer l'indice."
    )

    findings = analyze_pedagogical_sections_in_notebook(notebook)

    assert len(findings) == 1
    assert findings[0].status in {"solide", "acceptable"}


def test_response_cells_are_left_to_existing_response_engine() -> None:
    notebook = _notebook(
        "## Protocole\n\n**Réponse :** On utilise le matériel fourni."
    )

    findings = analyze_pedagogical_sections_in_notebook(notebook)

    assert findings == []


def test_local_feedback_is_inserted_after_fragile_protocol(
    tmp_path: Path,
) -> None:
    copy = tmp_path / "copy.ipynb"
    corrected = tmp_path / "corrected.ipynb"

    notebook = _notebook(
        "## Protocole\n\nOn utilise le matériel qui nous a été fourni."
    )
    nbformat.write(notebook, copy)
    nbformat.write(notebook, corrected)

    inserted = add_pedagogical_section_feedback_to_notebook(
        copy,
        corrected,
    )

    assert inserted == 1

    output = nbformat.read(corrected, as_version=4)

    assert len(output.cells) == 2
    assert "Retour TPStudio — Protocole" in output.cells[1].source
    assert "À revoir" in output.cells[1].source


def test_report_gets_section_diagnostic_and_updated_comment_count(
    tmp_path: Path,
) -> None:
    copy = tmp_path / "copy.ipynb"
    report = tmp_path / "report.md"

    notebook = _notebook(
        "## Protocole\n\nOn utilise le matériel qui nous a été fourni."
    )
    nbformat.write(notebook, copy)

    report.write_text(
        "# Rapport TPStudio\n\n"
        "### Synthèse rapide\n"
        "- Commentaires locaux insérés : **1**.\n\n"
        "### Priorités avant nouveau rendu\n"
        "- Aucune priorité évidente détectée.\n\n"
        "### Diagnostic des réponses\n"
        "- Aucune zone `Réponse :` détectée.\n\n"
        "### Conseils ciblés\n"
        "- Relancez le notebook.\n",
        encoding="utf-8",
    )

    weak_count = add_pedagogical_section_feedback_to_report(
        copy,
        report,
    )

    assert weak_count == 1

    text = report.read_text(encoding="utf-8")

    assert "Commentaires locaux insérés : **2**" in text
    assert "Sections pédagogiques fragiles ou à compléter : **1**" in text
    assert "### Diagnostic des sections pédagogiques" in text
    assert "partie « Protocole »" in text
    assert "section **fragile**" in text

def test_conjugated_protocol_actions_are_recognized() -> None:
    notebook = _notebook(
        "## Protocole\n\n"
        "Nous plaçons le disque devant le laser, nous alignons le rayon, "
        "nous choisissons plusieurs angles d'incidence, nous relevons "
        "les angles de réfraction et nous reportons les mesures avant "
        "de calculer l'indice."
    )

    findings = analyze_pedagogical_sections_in_notebook(notebook)

    assert len(findings) == 1
    assert findings[0].status in {"solide", "acceptable"}

