from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import re
import unicodedata


@dataclass(frozen=True)
class NotebookIdentity:
    names: str = ""
    group: str = ""
    session_date: str = ""


@dataclass(frozen=True)
class GradebookRow:
    last_name: str
    first_name: str
    group: str
    session: str
    tp_name: str
    notebook_name: str
    date: str
    grade: str = ""


CSV_COLUMNS = [
    "Nom",
    "Prénom",
    "Groupe",
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
    fallback_date = date_value or date.today().isoformat()

    rows: list[GradebookRow] = []

    for notebook_path in sorted(directory.glob(pattern)):
        if not notebook_path.is_file():
            continue

        if _should_ignore_notebook(notebook_path):
            continue

        identity = read_notebook_identity(notebook_path)

        last_name, first_name = split_identity_names(identity.names)

        if not last_name and not first_name:
            last_name, first_name = infer_student_name_from_notebook(
                notebook_path.name,
                tp_name=tp_name,
            )

        rows.append(
            GradebookRow(
                last_name=last_name,
                first_name=first_name,
                group=identity.group,
                session=session,
                tp_name=tp_name,
                notebook_name=notebook_path.name,
                date=identity.session_date or fallback_date,
                grade="",
            )
        )

    return rows


def gradebook_row_to_csv_row(row: GradebookRow) -> dict[str, str]:
    return {
        "Nom": row.last_name,
        "Prénom": row.first_name,
        "Groupe": row.group,
        "Séance": row.session,
        "Nom du TP": row.tp_name,
        "Nom du notebook": row.notebook_name,
        "Date": row.date,
        "Note": row.grade,
    }


def read_notebook_identity(notebook_path: str | Path) -> NotebookIdentity:
    path = Path(notebook_path)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return NotebookIdentity()

    cells = data.get("cells", [])
    if not isinstance(cells, list):
        return NotebookIdentity()

    for cell in cells:
        if not isinstance(cell, dict):
            continue

        text = _cell_text(cell)

        if not _looks_like_identity_cell(cell, text):
            continue

        identity = extract_identity_from_text(text)
        if identity.names or identity.group or identity.session_date:
            return identity

    return NotebookIdentity()


def extract_identity_from_text(text: str) -> NotebookIdentity:
    values = {
        "names": "",
        "group": "",
        "date": "",
    }

    for line in text.splitlines():
        key, value = _identity_key_value_from_line(line)
        if key and value:
            values[key] = value

    return NotebookIdentity(
        names=values["names"],
        group=values["group"],
        session_date=values["date"],
    )


def split_identity_names(names_value: str) -> tuple[str, str]:
    cleaned = " ".join(names_value.strip().split())

    if not cleaned:
        return "", ""

    # Si plusieurs étudiants sont saisis dans la zone "Noms", on garde la valeur
    # brute dans la colonne Nom. C'est plus sûr que d'inventer un découpage.
    if _looks_like_multiple_names(cleaned):
        return cleaned, ""

    parts = [
        part for part in re.split(r"[-_\s]+", cleaned)
        if part
    ]

    if len(parts) == 2:
        return parts[0].upper(), _title_name_part(parts[1])

    return cleaned, ""


def infer_student_name_from_notebook(
    filename: str,
    *,
    tp_name: str = "",
) -> tuple[str, str]:
    stem = Path(filename).stem
    cleaned = _remove_generated_suffixes(stem)
    cleaned = _remove_common_copy_words(cleaned)

    parts = _split_name_parts(cleaned)
    parts = _remove_tp_name_parts(parts, tp_name)
    parts = _remove_non_student_tokens(parts)

    if len(parts) >= 2:
        return parts[0].upper(), _title_name_part(parts[1])

    return "", ""


def _looks_like_identity_cell(cell: dict, text: str) -> bool:
    metadata = cell.get("metadata", {})
    if isinstance(metadata, dict):
        tpstudio = metadata.get("tpstudio", {})
        if isinstance(tpstudio, dict):
            if tpstudio.get("cell_role") == "report_identity":
                return True
            if tpstudio.get("marker") == "tpstudio_report_identity":
                return True

    normalized = _normalized_text(text)

    if "identification du compte rendu" in normalized:
        return True

    has_names = "noms" in normalized or "nom" in normalized
    has_group = "groupe" in normalized
    has_date = "date de la seance" in normalized or "date seance" in normalized

    return has_names and has_group and has_date


def _identity_key_value_from_line(line: str) -> tuple[str, str]:
    cleaned = _clean_identity_line(line)

    if ":" not in cleaned:
        return "", ""

    label, value = cleaned.split(":", 1)
    normalized_label = _normalized_text(label)
    value = value.strip()

    if normalized_label in {"nom", "noms"}:
        return "names", value

    if normalized_label == "groupe":
        return "group", value

    if normalized_label in {
        "date",
        "date de la seance",
        "date seance",
        "date de seance",
    }:
        return "date", value

    return "", ""


def _clean_identity_line(line: str) -> str:
    cleaned = line.strip()
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.replace("__", "")
    cleaned = cleaned.replace("`", "")
    cleaned = cleaned.replace("\u00a0", " ")
    cleaned = re.sub(r"<br\s*/?>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _looks_like_multiple_names(text: str) -> bool:
    lowered = f" {_normalized_text(text)} "

    separators = [
        ",",
        ";",
        "/",
        " et ",
        " & ",
        " + ",
    ]

    return any(separator in lowered for separator in separators)


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
    removable = {
        "copie",
        "etudiant",
        "étudiant",
        "notebook",
        "tp",
        "fausse",
        "codex",
        "modele",
        "modèle",
        "corrige",
        "corrigé",
        "ameliore",
        "amélioré",
    }

    raw_parts = re.split(r"[-_\s.]+", text)
    kept_parts = [
        part for part in raw_parts
        if part and _normalized_text(part) not in removable
    ]

    return " ".join(kept_parts)


def _remove_tp_name_parts(parts: list[str], tp_name: str) -> list[str]:
    if not tp_name:
        return parts

    tp_tokens = {
        _normalized_text(part)
        for part in re.split(r"[-_\s.]+", tp_name)
        if _normalized_text(part)
    }

    return [
        part for part in parts
        if _normalized_text(part) not in tp_tokens
    ]


def _remove_non_student_tokens(parts: list[str]) -> list[str]:
    generic_tokens = {
        "de",
        "du",
        "des",
        "la",
        "le",
        "les",
        "loi",
        "lois",
        "seance",
        "séance",
        "numero",
        "numéro",
        "n",
        "no",
    }

    kept: list[str] = []

    for part in parts:
        normalized = _normalized_text(part)
        if not normalized:
            continue
        if normalized in generic_tokens:
            continue
        kept.append(part)

    return kept


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

    subparts = re.split(r"(-)", text.lower())
    return "".join(part.capitalize() if part != "-" else part for part in subparts)


def _normalized_text(text: str) -> str:
    normalized = _strip_accents(text).lower()
    normalized = normalized.replace("*", "")
    normalized = normalized.replace("_", " ")
    normalized = normalized.replace("-", " ")
    normalized = normalized.replace(":", " ")
    normalized = normalized.replace("\u00a0", " ")
    return " ".join(normalized.split())


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
    ]

    return any(marker in stem for marker in ignored_markers)


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")

    if isinstance(source, list):
        return "".join(str(part) for part in source)

    return str(source)
