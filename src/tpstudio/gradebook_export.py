from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import unicodedata


@dataclass(frozen=True)
class GradebookRow:
    last_name: str
    first_name: str
    session: str
    tp_name: str
    notebook_name: str
    date: str
    grade: str = ""


CSV_COLUMNS = [
    "Nom",
    "Prénom",
    "Séance",
    "Nom du TP",
    "Nom du notebook",
    "Date",
    "Note",
]


def export_gradebook_csv(
    copies_dir: str | Path,
    output_path: str | Path,
    *,
    session: str,
    tp_name: str,
    date_value: str | None = None,
    pattern: str = "*.ipynb",
) -> Path:
    output = Path(output_path)
    rows = build_gradebook_rows(
        copies_dir,
        session=session,
        tp_name=tp_name,
        date_value=date_value,
        pattern=pattern,
    )

    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for row in rows:
            writer.writerow(gradebook_row_to_csv_row(row))

    return output


def build_gradebook_rows(
    copies_dir: str | Path,
    *,
    session: str,
    tp_name: str,
    date_value: str | None = None,
    pattern: str = "*.ipynb",
) -> list[GradebookRow]:
    directory = Path(copies_dir)
    normalized_date = date_value or date.today().isoformat()

    rows: list[GradebookRow] = []

    for notebook_path in sorted(directory.glob(pattern)):
        if not notebook_path.is_file():
            continue

        if _should_ignore_notebook(notebook_path):
            continue

        last_name, first_name = infer_student_name_from_notebook(notebook_path.name)

        rows.append(
            GradebookRow(
                last_name=last_name,
                first_name=first_name,
                session=session,
                tp_name=tp_name,
                notebook_name=notebook_path.name,
                date=normalized_date,
                grade="",
            )
        )

    return rows


def gradebook_row_to_csv_row(row: GradebookRow) -> dict[str, str]:
    return {
        "Nom": row.last_name,
        "Prénom": row.first_name,
        "Séance": row.session,
        "Nom du TP": row.tp_name,
        "Nom du notebook": row.notebook_name,
        "Date": row.date,
        "Note": row.grade,
    }


def infer_student_name_from_notebook(filename: str) -> tuple[str, str]:
    stem = Path(filename).stem
    cleaned = _remove_generated_suffixes(stem)
    cleaned = _remove_common_copy_words(cleaned)

    parts = _split_name_parts(cleaned)

    if len(parts) >= 2:
        return parts[0].upper(), _title_name_part(parts[1])

    if len(parts) == 1:
        return parts[0].upper(), ""

    return "", ""


def _remove_generated_suffixes(stem: str) -> str:
    suffixes = [
        "-retour-tpstudio",
        "-rapport-tpstudio",
        "-correction",
        "-corrige",
        "-corrigé",
        "-feedback",
    ]

    lowered = stem.lower()
    cleaned = stem

    for suffix in suffixes:
        index = lowered.find(suffix)
        if index != -1:
            cleaned = cleaned[:index]
            lowered = cleaned.lower()

    return cleaned


def _remove_common_copy_words(text: str) -> str:
    # Ces mots sont retirés seulement s'ils apparaissent comme segments séparés.
    removable = {
        "copie",
        "etudiant",
        "étudiant",
        "notebook",
        "tp",
        "fausse",
    }

    raw_parts = re.split(r"[-_\s.]+", text)
    kept_parts = [
        part for part in raw_parts
        if part and _strip_accents(part).lower() not in removable
    ]

    return " ".join(kept_parts)


def _split_name_parts(text: str) -> list[str]:
    raw_parts = re.split(r"[-_\s.]+", text)
    parts = [_clean_name_part(part) for part in raw_parts]
    return [part for part in parts if part]


def _clean_name_part(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\d+", "", cleaned)
    cleaned = re.sub(r"\d+$", "", cleaned)
    cleaned = cleaned.strip()
    return cleaned


def _title_name_part(text: str) -> str:
    if not text:
        return ""

    # Garde les prénoms composés lisibles : jean-luc -> Jean-Luc.
    subparts = re.split(r"(-)", text.lower())
    return "".join(part.capitalize() if part != "-" else part for part in subparts)


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _should_ignore_notebook(path: Path) -> bool:
    name = path.name.lower()
    stem = path.stem.lower()

    if name.startswith("."):
        return True

    ignored_markers = [
        "-retour-tpstudio",
        "-rapport-tpstudio",
        "-retour-a",
        "-ameliore",
        "-amélioré",
        "modele",
        "modèle",
        "corrige",
        "corrigé",
    ]

    return any(marker in stem for marker in ignored_markers)
