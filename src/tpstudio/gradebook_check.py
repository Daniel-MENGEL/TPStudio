from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tpstudio.gradebook_export import build_gradebook_result


@dataclass(frozen=True)
class GradebookCheckSummary:
    tp_name: str
    session: str
    kholle_week: str
    pattern: str
    notebooks_found: int
    notebooks_analyzed: int
    notebooks_ignored: int
    gradebook_rows: int
    detected_students: int
    unmatched_named_students: int
    missing_identity_notebooks: int
    missing_students: int


def build_gradebook_check_summary(
    copies_dir: str | Path,
    *,
    session: str,
    tp_name: str,
    kholle_week: str | None = None,
    pattern: str = "*.ipynb",
    students_file: str | Path | None = None,
) -> GradebookCheckSummary:
    directory = Path(copies_dir)

    notebooks_found = [
        path
        for path in sorted(directory.glob(pattern))
        if path.is_file()
    ]

    result = build_gradebook_result(
        directory,
        session=session,
        tp_name=tp_name,
        week_value=kholle_week,
        pattern=pattern,
        students_file=students_file,
    )

    analyzed_notebook_names = {row.notebook_name for row in result.rows}
    notebooks_analyzed = len(analyzed_notebook_names)
    notebooks_ignored = max(0, len(notebooks_found) - notebooks_analyzed)

    detected_students = sum(
        1
        for row in result.rows
        if row.last_name or row.first_name
    )

    unmatched_named_students = sum(
        1
        for unmatched in result.unmatched_students
        if unmatched.entered_last_name or unmatched.entered_first_name
    )

    missing_identity_notebooks = sum(
        1
        for unmatched in result.unmatched_students
        if not unmatched.entered_last_name and not unmatched.entered_first_name
    )

    return GradebookCheckSummary(
        tp_name=tp_name,
        session=session,
        kholle_week=kholle_week or "",
        pattern=pattern,
        notebooks_found=len(notebooks_found),
        notebooks_analyzed=notebooks_analyzed,
        notebooks_ignored=notebooks_ignored,
        gradebook_rows=len(result.rows),
        detected_students=detected_students,
        unmatched_named_students=unmatched_named_students,
        missing_identity_notebooks=missing_identity_notebooks,
        missing_students=len(result.missing_students),
    )


def format_gradebook_check_summary(summary: GradebookCheckSummary) -> str:
    lines = [
        "Contrôle TPStudio du suivi",
        f"TP : {summary.tp_name}",
        f"Séance : {summary.session}",
    ]

    if summary.kholle_week:
        lines.append(f"Semaine de kholle n° : {summary.kholle_week}")

    if summary.pattern != "*.ipynb":
        lines.append(f"Motif de fichiers : {summary.pattern}")

    lines.extend(
        [
            "",
            f"Notebooks trouvés : {summary.notebooks_found}",
            f"Notebooks analysés : {summary.notebooks_analyzed}",
            f"Notebooks ignorés : {summary.notebooks_ignored}",
            f"Lignes de suivi : {summary.gradebook_rows}",
            f"Étudiants détectés : {summary.detected_students}",
            f"Noms non reconnus : {summary.unmatched_named_students}",
            f"Identités absentes : {summary.missing_identity_notebooks}",
            f"Copies manquantes : {summary.missing_students}",
        ]
    )

    if (
        summary.unmatched_named_students == 0
        and summary.missing_identity_notebooks == 0
        and summary.missing_students == 0
    ):
        lines.append("")
        lines.append("Aucune anomalie majeure détectée.")

    return "\n".join(lines)
