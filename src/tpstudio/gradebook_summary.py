from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tpstudio.gradebook_bundle import GradebookBundlePaths
from tpstudio.gradebook_check import GradebookCheckSummary
from tpstudio.gradebook_export import build_gradebook_result


@dataclass(frozen=True)
class GradebookSummaryMarkdown:
    path: Path
    content: str


def write_gradebook_summary_markdown(
    output_path: str | Path,
    *,
    copies_dir: str | Path,
    session: str,
    tp_name: str,
    kholle_week: str | None = None,
    pattern: str = "*.ipynb",
    students_file: str | Path | None = None,
    bundle_paths: GradebookBundlePaths | None = None,
    check_summary: GradebookCheckSummary | None = None,
) -> GradebookSummaryMarkdown:
    output = Path(output_path)

    result = build_gradebook_result(
        Path(copies_dir),
        session=session,
        tp_name=tp_name,
        week_value=kholle_week,
        pattern=pattern,
        students_file=students_file,
    )

    content = format_gradebook_summary_markdown(
        session=session,
        tp_name=tp_name,
        kholle_week=kholle_week or "",
        bundle_paths=bundle_paths,
        check_summary=check_summary,
        unmatched_students=result.unmatched_students,
        missing_students=result.missing_students,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")

    return GradebookSummaryMarkdown(path=output, content=content)


def format_gradebook_summary_markdown(
    *,
    session: str,
    tp_name: str,
    kholle_week: str = "",
    bundle_paths: GradebookBundlePaths | None = None,
    check_summary: GradebookCheckSummary | None = None,
    unmatched_students: list | tuple = (),
    missing_students: list | tuple = (),
) -> str:
    lines = [
        f"# Bilan TPStudio — {tp_name}",
        "",
        f"**Séance :** {session}  ",
    ]

    if kholle_week:
        lines.append(f"**Semaine de kholle n° :** {kholle_week}  ")

    lines.append("")

    if check_summary is not None:
        lines.extend(
            [
                "## Résumé",
                "",
                f"- Notebooks trouvés : {check_summary.notebooks_found}",
                f"- Notebooks analysés : {check_summary.notebooks_analyzed}",
                f"- Notebooks ignorés : {check_summary.notebooks_ignored}",
                f"- Lignes de suivi : {check_summary.gradebook_rows}",
                f"- Étudiants détectés : {check_summary.detected_students}",
                f"- Noms non reconnus : {check_summary.unmatched_named_students}",
                f"- Identités absentes : {check_summary.missing_identity_notebooks}",
                f"- Rapports non rendus : {check_summary.missing_students}",
                "",
            ]
        )

    if bundle_paths is not None:
        lines.extend(
            [
                "## Fichiers générés",
                "",
                f"- Suivi : `{bundle_paths.followup_csv.name}`",
                f"- Anomalies : `{bundle_paths.unmatched_csv.name}`",
                f"- Rapports non rendus : `{bundle_paths.missing_csv.name}`",
                "",
            ]
        )

    lines.extend(_format_unmatched_students_section(unmatched_students))
    lines.extend(_format_missing_students_section(missing_students))

    if not unmatched_students and not missing_students:
        lines.extend(["## Bilan", "", "Aucune anomalie majeure détectée.", ""])

    return "\n".join(lines).rstrip() + "\n"


def _format_unmatched_students_section(unmatched_students: list | tuple) -> list[str]:
    lines = ["## Anomalies à vérifier", ""]

    if not unmatched_students:
        lines.extend(["Aucune anomalie à vérifier.", ""])
        return lines

    for student in unmatched_students:
        name = " ".join(
            part
            for part in [
                getattr(student, "entered_last_name", ""),
                getattr(student, "entered_first_name", ""),
            ]
            if part
        ).strip() or "Identité absente"

        notebook = getattr(student, "notebook_name", "")
        reason = getattr(student, "reason", "")

        detail = name
        if notebook:
            detail += f" — `{notebook}`"
        if reason:
            detail += f" — {reason}"

        lines.append(f"- {detail}")

    lines.append("")
    return lines


def _format_missing_students_section(missing_students: list | tuple) -> list[str]:
    lines = ["## Rapports non rendus", ""]

    if not missing_students:
        lines.extend(["Aucun rapport non rendu signalé.", ""])
        return lines

    for student in missing_students:
        name = " ".join(
            part
            for part in [
                getattr(student, "last_name", ""),
                getattr(student, "first_name", ""),
            ]
            if part
        ).strip()

        email = getattr(student, "email", "")
        lines.append(f"- {name} — {email}" if email else f"- {name}")

    lines.append("")
    return lines
