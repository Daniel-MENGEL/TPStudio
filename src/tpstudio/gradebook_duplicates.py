from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import dataclass
from pathlib import Path
import unicodedata

from tpstudio.gradebook_export import build_gradebook_result


DUPLICATE_COLUMNS = [
    "Nom",
    "Prénom",
    "Email",
    "Nom du TP",
    "Semaines de kholle n°",
    "Notebooks",
    "Raison",
]


@dataclass(frozen=True)
class DuplicateSubmission:
    last_name: str
    first_name: str
    email: str
    tp_name: str
    weeks: tuple[str, ...]
    notebook_names: tuple[str, ...]
    reason: str = "plusieurs copies détectées pour ce même étudiant et ce même TP"


def build_duplicate_submissions(
    copies_dir: str | Path,
    *,
    session: str,
    tp_name: str,
    week_value: str | None = None,
    date_value: str | None = None,
    pattern: str = "*.ipynb",
    students_file: str | Path | None = None,
) -> list[DuplicateSubmission]:
    result = build_gradebook_result(
        Path(copies_dir),
        session=session,
        tp_name=tp_name,
        week_value=week_value,
        date_value=date_value,
        pattern=pattern,
        students_file=students_file,
    )

    return find_duplicate_submissions(result.rows)


def find_duplicate_submissions(rows: list) -> list[DuplicateSubmission]:
    groups: dict[tuple[str, str, str], list] = defaultdict(list)

    for row in rows:
        last_name = getattr(row, "last_name", "")
        first_name = getattr(row, "first_name", "")

        if not last_name and not first_name:
            continue

        key = (
            _normalize_key(last_name),
            _normalize_key(first_name),
            _normalize_key(getattr(row, "tp_name", "")),
        )

        groups[key].append(row)

    duplicates: list[DuplicateSubmission] = []

    for group_rows in groups.values():
        notebook_names = sorted(
            {
                getattr(row, "notebook_name", "")
                for row in group_rows
                if getattr(row, "notebook_name", "")
            }
        )

        if len(notebook_names) <= 1:
            continue

        weeks = sorted(
            {
                getattr(row, "week", "")
                for row in group_rows
                if getattr(row, "week", "")
            },
            key=_normalize_key,
        )

        first_row = group_rows[0]

        duplicates.append(
            DuplicateSubmission(
                last_name=getattr(first_row, "last_name", ""),
                first_name=getattr(first_row, "first_name", ""),
                email=getattr(first_row, "email", ""),
                tp_name=getattr(first_row, "tp_name", ""),
                weeks=tuple(weeks),
                notebook_names=tuple(notebook_names),
            )
        )

    return sorted(
        duplicates,
        key=lambda duplicate: (
            _normalize_key(duplicate.last_name),
            _normalize_key(duplicate.first_name),
            _normalize_key(duplicate.tp_name),
        ),
    )


def export_duplicate_submissions_csv(
    duplicates: list[DuplicateSubmission],
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=DUPLICATE_COLUMNS)
        writer.writeheader()

        for duplicate in duplicates:
            writer.writerow(
                {
                    "Nom": duplicate.last_name,
                    "Prénom": duplicate.first_name,
                    "Email": duplicate.email,
                    "Nom du TP": duplicate.tp_name,
                    "Semaines de kholle n°": " ; ".join(duplicate.weeks),
                    "Notebooks": " ; ".join(duplicate.notebook_names),
                    "Raison": duplicate.reason,
                }
            )

    return output


def format_duplicate_submissions_report(
    duplicates: list[DuplicateSubmission],
    *,
    session: str,
    tp_name: str,
    week_value: str | None = None,
) -> str:
    lines = [
        "Doublons suspects TPStudio",
        f"TP : {tp_name}",
        f"Séance : {session}",
    ]

    if week_value:
        lines.append(f"Semaine de kholle n° utilisée par défaut : {week_value}")

    lines.append("")
    lines.append(f"Doublons suspects : {len(duplicates)}")
    lines.append("")

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
        lines.append(f"  TP : {duplicate.tp_name}")

        if duplicate.weeks:
            lines.append(f"  Semaines de kholle n° : {' ; '.join(duplicate.weeks)}")

        lines.append("  Notebooks :")

        for notebook_name in duplicate.notebook_names:
            lines.append(f"    - {notebook_name}")

        lines.append(f"  Raison : {duplicate.reason}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _normalize_key(value: object) -> str:
    text = str(value or "").strip()
    normalized = unicodedata.normalize("NFD", text)
    without_accents = "".join(
        char
        for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_accents.casefold().split())
