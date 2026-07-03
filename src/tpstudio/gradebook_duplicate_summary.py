from __future__ import annotations

from pathlib import Path
import html

from tpstudio.gradebook_duplicates import DuplicateSubmission


def duplicate_submissions_output_path(followup_csv_path: str | Path) -> Path:
    followup = Path(followup_csv_path)
    base = followup.name.removesuffix("-suivi.csv")
    return followup.with_name(f"{base}-doublons-suspects.csv")


def append_duplicate_submissions_to_markdown(
    markdown_path: str | Path,
    duplicates: list[DuplicateSubmission],
) -> Path:
    path = Path(markdown_path)
    text = path.read_text(encoding="utf-8")

    section = format_duplicate_submissions_markdown_section(duplicates)

    if "## Doublons suspects" in text:
        return path

    path.write_text(text.rstrip() + "\n\n" + section + "\n", encoding="utf-8")
    return path


def format_duplicate_submissions_markdown_section(
    duplicates: list[DuplicateSubmission],
) -> str:
    lines = [
        "## Doublons suspects",
        "",
        f"Doublons suspects : {len(duplicates)}",
        "",
    ]

    if not duplicates:
        lines.append("Aucun doublon suspect détecté.")
        return "\n".join(lines)

    for duplicate in duplicates:
        name = " ".join(
            part
            for part in [duplicate.last_name, duplicate.first_name]
            if part
        ).strip()

        lines.append(f"- {name}")
        lines.append(f"  - TP : {duplicate.tp_name}")

        if duplicate.weeks:
            lines.append(f"  - Semaines de kholle n° : {' ; '.join(duplicate.weeks)}")

        lines.append(f"  - Notebooks : {' ; '.join(duplicate.notebook_names)}")
        lines.append(f"  - Raison : {duplicate.reason}")

    return "\n".join(lines)


def append_duplicate_submissions_to_html(
    html_path: str | Path,
    duplicates: list[DuplicateSubmission],
) -> Path:
    path = Path(html_path)
    text = path.read_text(encoding="utf-8")

    if "Doublons suspects" in text:
        return path

    section = format_duplicate_submissions_html_section(duplicates)

    if "</div>" in text:
        text = text.replace("</div>", section + "\n    </div>", 1)
    else:
        text = text.replace("</main>", section + "\n  </main>", 1)

    path.write_text(text, encoding="utf-8")
    return path


def format_duplicate_submissions_html_section(
    duplicates: list[DuplicateSubmission],
) -> str:
    if not duplicates:
        return """
      <section class="card success">
        <h2>Doublons suspects</h2>
        <p>Doublons suspects : 0</p>
        <p>Aucun doublon suspect détecté.</p>
      </section>
"""

    items: list[str] = []

    for duplicate in duplicates:
        name = " ".join(
            part
            for part in [duplicate.last_name, duplicate.first_name]
            if part
        ).strip()

        weeks = " ; ".join(duplicate.weeks)
        notebooks = " ; ".join(duplicate.notebook_names)

        details = [
            f"<strong>{html.escape(name)}</strong>",
            f"TP : {html.escape(duplicate.tp_name)}",
        ]

        if weeks:
            details.append(f"Semaines de kholle n° : {html.escape(weeks)}")

        details.append(f"Notebooks : {html.escape(notebooks)}")
        details.append(f"Raison : {html.escape(duplicate.reason)}")

        items.append("<li>" + "<br>".join(details) + "</li>")

    return f"""
      <section class="card danger">
        <h2>Doublons suspects</h2>
        <p>Doublons suspects : {len(duplicates)}</p>
        <ul>
          {''.join(items)}
        </ul>
      </section>
"""
