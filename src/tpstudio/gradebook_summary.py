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


def write_gradebook_summary_html(
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

    content = format_gradebook_summary_html(
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


def format_gradebook_summary_html(
    *,
    session: str,
    tp_name: str,
    kholle_week: str = "",
    bundle_paths: GradebookBundlePaths | None = None,
    check_summary: GradebookCheckSummary | None = None,
    unmatched_students: list | tuple = (),
    missing_students: list | tuple = (),
) -> str:
    import html

    def esc(value: object) -> str:
        return html.escape(str(value), quote=True)

    cards: list[str] = []

    if check_summary is not None:
        cards.append(
            _html_section(
                "Résumé",
                [
                    ("Notebooks trouvés", check_summary.notebooks_found),
                    ("Notebooks analysés", check_summary.notebooks_analyzed),
                    ("Notebooks ignorés", check_summary.notebooks_ignored),
                    ("Lignes de suivi", check_summary.gradebook_rows),
                    ("Étudiants détectés", check_summary.detected_students),
                    ("Noms non reconnus", check_summary.unmatched_named_students),
                    ("Identités absentes", check_summary.missing_identity_notebooks),
                    ("Rapports non rendus", check_summary.missing_students),
                ],
            )
        )

    if bundle_paths is not None:
        cards.append(
            """
            <section class="card">
              <h2>Fichiers générés</h2>
              <ul>
                <li><strong>Suivi :</strong> {followup}</li>
                <li><strong>Anomalies :</strong> {unmatched}</li>
                <li><strong>Rapports non rendus :</strong> {missing}</li>
              </ul>
            </section>
            """.format(
                followup=_html_file_link(bundle_paths.followup_csv),
                unmatched=_html_file_link(bundle_paths.unmatched_csv),
                missing=_html_file_link(bundle_paths.missing_csv),
            )
        )

    cards.append(_html_unmatched_students_section(unmatched_students))
    cards.append(_html_missing_students_section(missing_students))

    if not unmatched_students and not missing_students:
        cards.append(
            """
            <section class="card success">
              <h2>Bilan</h2>
              <p>Aucune anomalie majeure détectée.</p>
            </section>
            """
        )

    week_line = (
        f'<p><strong>Semaine de kholle n° :</strong> {esc(kholle_week)}</p>'
        if kholle_week
        else ""
    )

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Bilan TPStudio — {esc(tp_name)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7fb;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --border: #e5e7eb;
      --accent: #2563eb;
      --warning: #b45309;
      --danger: #b91c1c;
      --success: #047857;
    }}
    body {{
      margin: 0;
      padding: 2rem;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
    }}
    header {{
      margin-bottom: 1.5rem;
    }}
    h1 {{
      margin: 0 0 0.5rem;
      font-size: 2rem;
    }}
    h2 {{
      margin-top: 0;
      font-size: 1.25rem;
    }}
    .meta {{
      color: var(--muted);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 1rem;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 1.1rem 1.25rem;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
    }}
    .success {{
      border-left: 5px solid var(--success);
    }}
    .warning {{
      border-left: 5px solid var(--warning);
    }}
    .danger {{
      border-left: 5px solid var(--danger);
    }}
    dl {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 0.45rem 1rem;
      margin: 0;
    }}
    dt {{
      color: var(--muted);
    }}
    dd {{
      margin: 0;
      font-weight: 700;
    }}
    ul {{
      padding-left: 1.2rem;
      margin-bottom: 0;
    }}
    code {{
      background: #f3f4f6;
      border-radius: 6px;
      padding: 0.1rem 0.3rem;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Bilan TPStudio — {esc(tp_name)}</h1>
      <div class="meta">
        <p><strong>Séance :</strong> {esc(session)}</p>
        {week_line}
      </div>
    </header>
    <div class="grid">
      {''.join(cards)}
    </div>
  </main>
</body>
</html>
"""


def _html_section(title: str, values: list[tuple[str, object]]) -> str:
    import html

    items = "\n".join(
        f"<dt>{html.escape(str(label))}</dt><dd>{html.escape(str(value))}</dd>"
        for label, value in values
    )

    return f"""
    <section class="card">
      <h2>{html.escape(title)}</h2>
      <dl>
        {items}
      </dl>
    </section>
    """


def _html_unmatched_students_section(unmatched_students: list | tuple) -> str:
    import html

    if not unmatched_students:
        return """
        <section class="card success">
          <h2>Anomalies à vérifier</h2>
          <p>Aucune anomalie à vérifier.</p>
        </section>
        """

    items: list[str] = []

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

        detail = html.escape(name)
        if notebook:
            detail += f" — <code>{html.escape(notebook)}</code>"
        if reason:
            detail += f" — {html.escape(reason)}"

        items.append(f"<li>{detail}</li>")

    return f"""
    <section class="card danger">
      <h2>Anomalies à vérifier</h2>
      <ul>
        {''.join(items)}
      </ul>
    </section>
    """


def _html_missing_students_section(missing_students: list | tuple) -> str:
    import html

    if not missing_students:
        return """
        <section class="card success">
          <h2>Rapports non rendus</h2>
          <p>Aucun rapport non rendu signalé.</p>
        </section>
        """

    items: list[str] = []

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

        if email:
            items.append(f"<li>{html.escape(name)} — {html.escape(email)}</li>")
        else:
            items.append(f"<li>{html.escape(name)}</li>")

    return f"""
    <section class="card warning">
      <h2>Rapports non rendus</h2>
      <ul>
        {''.join(items)}
      </ul>
    </section>
    """

def _html_file_link(path: Path) -> str:
    import html

    filename = path.name
    escaped = html.escape(filename, quote=True)
    return f'<a href="{escaped}">{escaped}</a>'

