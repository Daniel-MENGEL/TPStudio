"""Local, explicit student-roster storage for identity resolution."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import io
import json
from pathlib import Path
import re
import unicodedata

from .identity import (
    CopyIdentity, CopyIdentitySource, CopyIdentityStatus, StudentIdentity,
)


@dataclass(frozen=True, slots=True)
class RosterStudent:
    family_name: str
    given_names: str
    email: str

    def __post_init__(self) -> None:
        for name in ("family_name", "given_names", "email"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} ne peut pas être vide.")
        if "@" not in self.email:
            raise ValueError("L'email étudiant est invalide.")
        object.__setattr__(self, "family_name", self.family_name.strip())
        object.__setattr__(self, "given_names", self.given_names.strip())
        object.__setattr__(self, "email", self.email.strip().casefold())

    @property
    def label(self) -> str:
        return f"{self.given_names} {self.family_name}"

    def to_identity(self) -> StudentIdentity:
        return StudentIdentity(self.label, self.family_name, self.given_names, self.email)

    def to_dict(self) -> dict[str, str]:
        return {"family_name": self.family_name, "given_names": self.given_names, "email": self.email}

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "RosterStudent":
        return cls(str(value["family_name"]), str(value["given_names"]), str(value["email"]))


def default_roster_path() -> Path:
    return Path.home() / ".tpstudio" / "students.json"


def parse_roster_csv(text: str) -> tuple[RosterStudent, ...]:
    if not isinstance(text, str):
        raise TypeError("Le roster CSV doit être du texte.")
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter=";"))
    students: list[RosterStudent] = []
    seen: dict[str, RosterStudent] = {}
    for row_number, row in enumerate(rows, 1):
        values = [value.strip() for value in row]
        if not values or not any(values):
            continue
        if row_number == 1 and tuple(value.casefold() for value in values[:3]) == ("nom", "prénom", "mail"):
            continue
        if len(values) != 3 or not all(values):
            raise ValueError(f"Ligne {row_number} invalide dans le roster.")
        student = RosterStudent(*values)
        previous = seen.get(student.email)
        if previous is not None:
            if previous != student:
                raise ValueError(f"Email dupliqué avec des données contradictoires ligne {row_number}.")
            continue
        seen[student.email] = student
        students.append(student)
    return tuple(students)


def save_roster(students: tuple[RosterStudent, ...], path: Path | None = None) -> Path:
    path = default_roster_path() if path is None else path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [student.to_dict() for student in students]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_roster(path: Path | None = None) -> tuple[RosterStudent, ...]:
    path = default_roster_path() if path is None else path
    if not path.exists():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Le fichier roster est invalide.")
        students = tuple(RosterStudent.from_dict(item) for item in payload)
        if len({student.email for student in students}) != len(students):
            raise ValueError("Le roster contient des emails dupliqués.")
        return students
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("Le fichier roster est invalide.") from exc


def confirm_exact_roster_identity(
    identity: CopyIdentity,
    students: tuple[RosterStudent, ...],
) -> CopyIdentity:
    """Confirm an unambiguous notebook identity against the local roster.

    Filename hints remain useful when the notebook does not identify its
    authors.  They must not force a manual review when every author explicitly
    named in the notebook has one exact roster match.
    """

    if type(identity) is not CopyIdentity:
        raise TypeError("L'identité de copie est invalide.")
    students = tuple(students)
    if any(type(student) is not RosterStudent for student in students):
        raise TypeError("Le roster est invalide.")
    if (
        identity.status is not CopyIdentityStatus.TO_REVIEW
        or identity.source is not CopyIdentitySource.NOTEBOOK
        or not identity.students
    ):
        return identity

    roster_by_name: dict[str, list[RosterStudent]] = {}
    for student in students:
        roster_by_name.setdefault(_normalise_name(student.label), []).append(student)
    matches: list[RosterStudent] = []
    for detected in identity.students:
        candidates = roster_by_name.get(_normalise_name(detected.display_name), ())
        if len(candidates) != 1:
            return identity
        matches.append(candidates[0])
    if len({student.email for student in matches}) != len(matches):
        return identity
    return CopyIdentity(
        tuple(student.to_identity() for student in matches),
        CopyIdentitySource.NOTEBOOK,
        CopyIdentityStatus.CONFIRMED,
        identity.raw_value,
    )


def _normalise_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def suggest_roster_students(filename: str, students: tuple[RosterStudent, ...]) -> tuple[RosterStudent, ...]:
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", Path(filename).stem)
    normalized = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode().casefold()
    hints = [token for token in re.split(r"[^a-z0-9]+", normalized) if len(token) > 2]
    matches: dict[str, set[int]] = {hint: set() for hint in hints}
    for index, student in enumerate(students):
        names = (
            unicodedata.normalize("NFKD", student.family_name).encode("ascii", "ignore").decode().casefold(),
            unicodedata.normalize("NFKD", student.given_names).encode("ascii", "ignore").decode().casefold(),
        )
        for hint in hints:
            if any(name and (name in hint or hint in name) for name in names):
                matches[hint].add(index)
    selected = {
        index
        for candidates in matches.values()
        if len(candidates) == 1
        for index in candidates
    }
    return tuple(student for index, student in enumerate(students) if index in selected)
