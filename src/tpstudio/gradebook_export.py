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
    week: str = ""
    # Backward compatibility for notebooks generated before A46.
    session_date: str = ""


@dataclass(frozen=True)
class StudentRecord:
    last_name: str
    first_name: str
    email: str = ""
    group: str = ""


@dataclass(frozen=True)
class GradebookRow:
    last_name: str
    first_name: str
    email: str
    group: str
    session: str
    tp_name: str
    notebook_name: str
    week: str
    grade: str = ""

    @property
    def date(self) -> str:
        # Compatibility with older internal tests or user scripts.
        return self.week


@dataclass(frozen=True)
class UnmatchedStudent:
    entered_last_name: str
    entered_first_name: str
    notebook_name: str
    identity_names: str
    group: str
    week: str
    reason: str

    @property
    def date(self) -> str:
        # Compatibility with older internal tests or user scripts.
        return self.week


@dataclass(frozen=True)
class MissingStudent:
    last_name: str
    first_name: str
    email: str = ""


@dataclass(frozen=True)
class MissingStudent:
    last_name: str
    first_name: str
    email: str = ""


@dataclass(frozen=True)
class GradebookBuildResult:
    rows: list[GradebookRow]
    unmatched_students: list[UnmatchedStudent]
    missing_students: list[MissingStudent]
    missing_students: list[MissingStudent]


CSV_COLUMNS = [
    "Nom",
    "Prénom",
    "Email",
    "Groupe",
    "Séance",
    "Nom du TP",
    "Nom du notebook",
    "Semaine de kholle n°",
    "Note",
]


UNMATCHED_COLUMNS = [
    "Nom saisi",
    "Prénom saisi",
    "Nom du notebook",
    "Noms cellule",
    "Groupe",
    "Semaine de kholle n°",
    "Raison",
]


MISSING_COLUMNS = [
    "Nom",
    "Prénom",
    "Email",
    "Raison",
]


MISSING_COLUMNS = [
    "Nom",
    "Prénom",
    "Email",
    "Raison",
]


def export_gradebook_csv(
    copies_dir: str | Path,
    output_path: str | Path,
    *,
    session: str,
    tp_name: str,
    week_value: str | None = None,
    date_value: str | None = None,
    pattern: str = "*.ipynb",
    students_file: str | Path | None = None,
    unmatched_output_path: str | Path | None = None,
    missing_output_path: str | Path | None = None,
) -> Path:
    output = Path(output_path)

    build_result = build_gradebook_result(
        copies_dir,
        session=session,
        tp_name=tp_name,
        week_value=week_value,
        date_value=date_value,
        pattern=pattern,
        students_file=students_file,
    )

    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for row in build_result.rows:
            writer.writerow(gradebook_row_to_csv_row(row))

    if unmatched_output_path:
        export_unmatched_students_csv(
            build_result.unmatched_students,
            unmatched_output_path,
        )

    if missing_output_path:
        export_missing_students_csv(
            build_result.missing_students,
            missing_output_path,
        )

    return output


def build_gradebook_rows(
    copies_dir: str | Path,
    *,
    session: str,
    tp_name: str,
    week_value: str | None = None,
    date_value: str | None = None,
    pattern: str = "*.ipynb",
    students_file: str | Path | None = None,
) -> list[GradebookRow]:
    return build_gradebook_result(
        copies_dir,
        session=session,
        tp_name=tp_name,
        week_value=week_value,
        date_value=date_value,
        pattern=pattern,
        students_file=students_file,
    ).rows


def build_gradebook_result(
    copies_dir: str | Path,
    *,
    session: str,
    tp_name: str,
    week_value: str | None = None,
    date_value: str | None = None,
    pattern: str = "*.ipynb",
    students_file: str | Path | None = None,
) -> GradebookBuildResult:
    directory = Path(copies_dir)
    fallback_week = week_value or date_value or ""
    official_students = load_students_csv(students_file) if students_file else []

    rows: list[GradebookRow] = []
    unmatched_students: list[UnmatchedStudent] = []
    matched_student_keys: set[tuple[str, str]] = set()
    matched_student_keys: set[tuple[str, str]] = set()

    for notebook_path in sorted(directory.glob(pattern)):
        if not notebook_path.is_file():
            continue

        if _should_ignore_notebook(notebook_path):
            continue

        identity = read_notebook_identity(notebook_path)
        students = split_identity_students(identity.names)

        if not students:
            fallback_student = infer_student_name_from_notebook(
                notebook_path.name,
                tp_name=tp_name,
            )
            if fallback_student != ("", ""):
                students = [fallback_student]

        if not students and _looks_like_reference_notebook(notebook_path, tp_name):
            continue

        if not students:
            students = [("", "")]

        effective_week = identity.week or identity.session_date or fallback_week

        for last_name, first_name in students:
            official_student = match_student_record(
                last_name,
                first_name,
                official_students,
            )

            if official_student:
                matched_student_keys.add(_student_record_key(official_student))
                final_last_name = official_student.last_name
                final_first_name = official_student.first_name
                email = official_student.email
                # Le groupe du notebook est le groupe de manipulation
                # de la séance. Il peut changer à chaque TP, donc on ne le
                # déduit jamais depuis la liste officielle d'étudiants.
                group = identity.group
            else:
                final_last_name = last_name
                final_first_name = first_name
                email = ""
                group = identity.group

                if official_students:
                    reason = (
                        "identité absente"
                        if not last_name and not first_name
                        else "étudiant non trouvé dans la liste officielle"
                    )
                    unmatched_students.append(
                        UnmatchedStudent(
                            entered_last_name=last_name,
                            entered_first_name=first_name,
                            notebook_name=notebook_path.name,
                            identity_names=identity.names,
                            group=identity.group,
                            week=effective_week,
                            reason=reason,
                        )
                    )

            rows.append(
                GradebookRow(
                    last_name=final_last_name,
                    first_name=final_first_name,
                    email=email,
                    group=group,
                    session=session,
                    tp_name=tp_name,
                    notebook_name=notebook_path.name,
                    week=effective_week,
                    grade="",
                )
            )

    missing_students = find_missing_students(
        official_students,
        matched_student_keys,
    )

    return GradebookBuildResult(
        rows=rows,
        unmatched_students=unmatched_students,
        missing_students=missing_students,
    )


def export_unmatched_students_csv(
    unmatched_students: list[UnmatchedStudent],
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=UNMATCHED_COLUMNS)
        writer.writeheader()

        for unmatched in unmatched_students:
            writer.writerow(unmatched_student_to_csv_row(unmatched))

    return output


def export_missing_students_csv(
    missing_students: list[MissingStudent],
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MISSING_COLUMNS)
        writer.writeheader()

        for missing in missing_students:
            writer.writerow(missing_student_to_csv_row(missing))

    return output


def export_missing_students_csv(
    missing_students: list[MissingStudent],
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MISSING_COLUMNS)
        writer.writeheader()

        for missing in missing_students:
            writer.writerow(missing_student_to_csv_row(missing))

    return output


def gradebook_row_to_csv_row(row: GradebookRow) -> dict[str, str]:
    return {
        "Nom": row.last_name,
        "Prénom": row.first_name,
        "Email": row.email,
        "Groupe": row.group,
        "Séance": row.session,
        "Nom du TP": row.tp_name,
        "Nom du notebook": row.notebook_name,
        "Semaine de kholle n°": row.week,
        "Note": row.grade,
    }


def unmatched_student_to_csv_row(unmatched: UnmatchedStudent) -> dict[str, str]:
    return {
        "Nom saisi": unmatched.entered_last_name,
        "Prénom saisi": unmatched.entered_first_name,
        "Nom du notebook": unmatched.notebook_name,
        "Noms cellule": unmatched.identity_names,
        "Groupe": unmatched.group,
        "Semaine de kholle n°": unmatched.week,
        "Raison": unmatched.reason,
    }


def missing_student_to_csv_row(missing: MissingStudent) -> dict[str, str]:
    return {
        "Nom": missing.last_name,
        "Prénom": missing.first_name,
        "Email": missing.email,
        "Raison": "aucune copie détectée pour cet étudiant",
    }


def find_missing_students(
    official_students: list[StudentRecord],
    matched_student_keys: set[tuple[str, str]],
) -> list[MissingStudent]:
    missing_students: list[MissingStudent] = []

    for student in official_students:
        if _student_record_key(student) in matched_student_keys:
            continue

        missing_students.append(
            MissingStudent(
                last_name=student.last_name,
                first_name=student.first_name,
                email=student.email,
            )
        )

    return missing_students


def _student_record_key(student: StudentRecord) -> tuple[str, str]:
    return (
        _normalized_identity_name(student.last_name),
        _normalized_identity_name(student.first_name),
    )


def missing_student_to_csv_row(missing: MissingStudent) -> dict[str, str]:
    return {
        "Nom": missing.last_name,
        "Prénom": missing.first_name,
        "Email": missing.email,
        "Raison": "aucune copie détectée pour cet étudiant",
    }


def find_missing_students(
    official_students: list[StudentRecord],
    matched_student_keys: set[tuple[str, str]],
) -> list[MissingStudent]:
    missing_students: list[MissingStudent] = []

    for student in official_students:
        if _student_record_key(student) in matched_student_keys:
            continue

        missing_students.append(
            MissingStudent(
                last_name=student.last_name,
                first_name=student.first_name,
                email=student.email,
            )
        )

    return missing_students


def _student_record_key(student: StudentRecord) -> tuple[str, str]:
    return (
        _normalized_identity_name(student.last_name),
        _normalized_identity_name(student.first_name),
    )


def load_students_csv(students_file: str | Path | None) -> list[StudentRecord]:
    if not students_file:
        return []

    path = Path(students_file)

    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        records: list[StudentRecord] = []

        for row in reader:
            last_name = _row_value(row, "Nom", "nom", "NOM", "last_name", "Last name")
            first_name = _row_value(row, "Prénom", "Prenom", "prenom", "first_name", "First name")
            email = _row_value(row, "Email", "email", "Mail", "mail")
            group = _row_value(row, "Groupe", "groupe", "Group", "group")

            if not last_name and not first_name:
                continue

            records.append(
                StudentRecord(
                    last_name=last_name.strip().upper(),
                    first_name=_title_name_part(first_name.strip()),
                    email=email.strip(),
                    group=group.strip(),
                )
            )

    return records


def match_student_record(
    last_name: str,
    first_name: str,
    official_students: list[StudentRecord],
) -> StudentRecord | None:
    if not last_name and not first_name:
        return None

    normalized_last = _normalized_identity_name(last_name)
    normalized_first = _normalized_identity_name(first_name)

    for student in official_students:
        student_last = _normalized_identity_name(student.last_name)
        student_first = _normalized_identity_name(student.first_name)

        if normalized_last == student_last and normalized_first == student_first:
            return student

        # Fallback if the student wrote "Prénom Nom" instead of "Nom Prénom".
        if normalized_last == student_first and normalized_first == student_last:
            return student

    return None


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
        if identity.names or identity.group or identity.week or identity.session_date:
            return identity

    return NotebookIdentity()


def extract_identity_from_text(text: str) -> NotebookIdentity:
    values = {
        "names": "",
        "group": "",
        "week": "",
        "date": "",
    }

    lines = text.splitlines()

    for index, line in enumerate(lines):
        key, value = _identity_key_value_from_line(line)

        if key and value:
            values[key] = value
            continue

        if key == "names" and not value:
            bullet_names = _following_bullet_values(lines[index + 1:])
            if bullet_names:
                values["names"] = " ; ".join(bullet_names)

    return NotebookIdentity(
        names=values["names"],
        group=values["group"],
        week=values["week"],
        session_date=values["date"],
    )


def split_identity_names(names_value: str) -> tuple[str, str]:
    students = split_identity_students(names_value)

    if len(students) == 1:
        return students[0]

    if len(students) > 1:
        return names_value.strip(), ""

    return "", ""


def split_identity_students(names_value: str) -> list[tuple[str, str]]:
    cleaned = " ".join(names_value.strip().split())

    if not cleaned:
        return []

    chunks = _split_student_chunks(cleaned)
    students: list[tuple[str, str]] = []

    for chunk in chunks:
        student = _split_single_student_name(chunk)
        if student != ("", ""):
            students.append(student)

    return students


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


def _split_student_chunks(names_value: str) -> list[str]:
    text = names_value.strip()

    # Separator order matters: the semicolon is the recommended separator.
    text = re.sub(r"\s*(?:;|/|&|\+)\s*", ";", text)
    text = re.sub(r"\s+\bet\s+", ";", text, flags=re.IGNORECASE)

    chunks = [chunk.strip(" .,-") for chunk in text.split(";")]
    return [chunk for chunk in chunks if chunk]


def _split_single_student_name(text: str) -> tuple[str, str]:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return "", ""

    # Format possible : NOM, Prénom.
    if "," in cleaned:
        last_name, first_name = cleaned.split(",", 1)
        return last_name.strip().upper(), _title_name_part(first_name.strip())

    parts = [part for part in re.split(r"[-_\s]+", cleaned) if part]

    if len(parts) >= 2:
        return parts[0].upper(), _title_name_part("-".join(parts[1:]))

    return cleaned.upper(), ""


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
    has_time_marker = (
        "semaine" in normalized
        or "date de la seance" in normalized
        or "date seance" in normalized
    )

    return has_names and has_group and has_time_marker


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
        "semaine",
        "numero de semaine",
        "n semaine",
        "no semaine",
        "numéro de semaine",
        "semaine de kholle",
        "semaine de kholle n",
        "semaine de kholle no",
        "semaine de kholle n°",
        "numero de semaine de kholle",
        "numéro de semaine de kholle",
    }:
        return "week", value

    if normalized_label in {
        "date",
        "date de la seance",
        "date seance",
        "date de seance",
    }:
        return "date", value

    return "", ""


def _following_bullet_values(lines: list[str]) -> list[str]:
    values: list[str] = []

    for line in lines:
        cleaned = _clean_identity_line(line)

        if not cleaned:
            if values:
                break
            continue

        if ":" in cleaned:
            break

        match = re.match(r"^[-*•]\s*(.+)$", cleaned)
        if not match:
            if values:
                break
            continue

        value = match.group(1).strip()
        if value:
            values.append(value)

    return values


def _clean_identity_line(line: str) -> str:
    cleaned = line.strip()
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.replace("__", "")
    cleaned = cleaned.replace("`", "")
    cleaned = cleaned.replace("\u00a0", " ")
    cleaned = re.sub(r"<br\s*/?>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _row_value(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value

    normalized_keys = {
        _normalized_text(key): value
        for key, value in row.items()
        if key is not None
    }

    for key in keys:
        value = normalized_keys.get(_normalized_text(key))
        if value is not None:
            return value

    return ""


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


def _normalized_identity_name(text: str) -> str:
    return _normalized_text(text).replace(" ", "")


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


def _looks_like_reference_notebook(path: Path, tp_name: str) -> bool:
    stem = path.stem
    normalized_stem = _normalized_text(stem)
    normalized_tp_name = _normalized_text(tp_name)

    student_markers = {
        "copie",
        "etudiant",
        "étudiant",
        "eleve",
        "élève",
    }

    if any(marker in normalized_stem.split() for marker in student_markers):
        return False

    reference_markers = {
        "codex",
        "modele",
        "modèle",
        "corrige",
        "corrigé",
    }

    if any(marker in normalized_stem.split() for marker in reference_markers):
        return True

    if "ameliore" in normalized_stem.split() or "amélioré" in normalized_stem.split():
        return True

    if normalized_tp_name:
        tp_tokens = [
            token
            for token in normalized_tp_name.split()
            if token not in {"de", "du", "des", "la", "le", "les"}
        ]
        stem_tokens = normalized_stem.split()

        if tp_tokens and all(token in stem_tokens for token in tp_tokens):
            remaining_tokens = [
                token
                for token in stem_tokens
                if token not in set(tp_tokens)
                and token not in {
                    "de",
                    "du",
                    "des",
                    "la",
                    "le",
                    "les",
                    "tp",
                    "seance",
                    "séance",
                }
            ]

            if not remaining_tokens:
                return True

    return False

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
