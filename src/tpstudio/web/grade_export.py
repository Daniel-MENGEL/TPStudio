"""Build an Excel-friendly grade table from reviewed web copies."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import io
import re
import unicodedata

from .roster import RosterStudent


@dataclass(frozen=True, slots=True)
class WebGradeEntry:
    family_name: str
    given_names: str
    email: str | None
    project_title: str
    grade: str
    reviewed: bool
    display_name: str = ""


def _identity_key(family_name: str, given_names: str) -> str:
    value = unicodedata.normalize(
        "NFKD", f"{family_name or ''} {given_names or ''}"
    )
    value = "".join(character for character in value if not unicodedata.combining(character))
    return " ".join(sorted(re.findall(r"[a-z0-9]+", value.casefold())))


def _excel_grade(value: str) -> str:
    """Return a bare grade using the French decimal separator."""

    return value.strip().removesuffix("/20").strip().replace(".", ",")


def _ordered_words(value: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return tuple(re.findall(r"[a-z0-9]+", normalized.casefold()))


def _one_edit_apart(first: str, second: str) -> bool:
    if abs(len(first) - len(second)) > 1:
        return False
    if len(first) == len(second):
        return sum(a != b for a, b in zip(first, second)) == 1
    shorter, longer = sorted((first, second), key=len)
    return any(longer[:index] + longer[index + 1:] == shorter for index in range(len(longer)))


def _students_named_in_display(
    display_name: str, roster: tuple[RosterStudent, ...]
) -> tuple[RosterStudent, ...]:
    """Resolve only complete, non-overlapping names in a combined identity."""

    remaining = list(_ordered_words(display_name))
    matched: list[RosterStudent] = []
    for student in roster:
        family = _ordered_words(student.family_name)
        given = _ordered_words(student.given_names)
        for sequence in (family + given, given + family):
            for start in range(len(remaining) - len(sequence) + 1):
                if tuple(remaining[start:start + len(sequence)]) == sequence:
                    matched.append(student)
                    del remaining[start:start + len(sequence)]
                    break
            else:
                continue
            break
    if matched and not remaining:
        return tuple(matched)
    if len(remaining) == 2 and not matched:
        candidates = tuple(
            student for student in roster
            if len(_ordered_words(student.family_name)) == 1
            and len(_ordered_words(student.given_names)) == 1
            and (
                (remaining[0] == _ordered_words(student.given_names)[0]
                 and _one_edit_apart(remaining[1], _ordered_words(student.family_name)[0]))
                or (remaining[1] == _ordered_words(student.given_names)[0]
                    and _one_edit_apart(remaining[0], _ordered_words(student.family_name)[0]))
            )
        )
        if len(candidates) == 1:
            return candidates
    return ()


def build_web_gradebook_csv(
    entries: tuple[WebGradeEntry, ...],
    roster: tuple[RosterStudent, ...] = (),
) -> bytes:
    """Return a wide semicolon CSV: one student, one column per TP."""

    entries = tuple(entries)
    roster = tuple(roster)
    projects = tuple(sorted({entry.project_title for entry in entries}))
    by_email = {student.email.casefold(): student for student in roster}
    by_name = {
        _identity_key(student.family_name, student.given_names): student
        for student in roster
    }
    students: dict[str, tuple[str, str, str]] = {
        student.email.casefold(): (
            student.family_name, student.given_names, student.email
        )
        for student in roster
    }
    values: dict[tuple[str, str], WebGradeEntry] = {}
    for entry in entries:
        entry_email = (entry.email or "").strip()
        roster_student = by_email.get(entry_email.casefold()) if entry_email else None
        if roster_student is None:
            roster_student = by_name.get(
                _identity_key(entry.family_name, entry.given_names)
                or _identity_key(entry.display_name, "")
            )
        matches = (roster_student,) if roster_student is not None else _students_named_in_display(
            entry.display_name, roster
        )
        if matches:
            for matched_student in matches:
                student_key = matched_student.email.casefold()
                values[(student_key, entry.project_title)] = entry
        else:
            student_key = entry_email.casefold() or _identity_key(
                entry.family_name, entry.given_names
            ) or _identity_key(entry.display_name, "")
            if not student_key:
                raise ValueError("Une note ne peut pas être exportée sans identité étudiante.")
            students[student_key] = (
                entry.family_name or entry.display_name, entry.given_names or "", entry_email
            )
            values[(student_key, entry.project_title)] = entry

    columns = ["Nom", "Prénom", "Email"]
    for project in projects:
        columns.extend((f"Note — {project}", f"État — {project}"))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, delimiter=";")
    writer.writeheader()
    for student_key, (family_name, given_names, email) in sorted(
        students.items(), key=lambda item: (item[1][0].casefold(), item[1][1].casefold())
    ):
        row = {"Nom": family_name, "Prénom": given_names, "Email": email}
        for project in projects:
            entry = values.get((student_key, project))
            row[f"Note — {project}"] = (
                _excel_grade(entry.grade) if entry and entry.reviewed else ""
            )
            row[f"État — {project}"] = (
                "Validée" if entry and entry.reviewed
                else "À vérifier" if entry
                else "Non remise"
            )
        writer.writerow(row)
    return ("\ufeff" + stream.getvalue()).encode("utf-8")
