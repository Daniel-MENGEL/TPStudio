"""Conservative, provenance-preserving copy identity handling."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import re
import unicodedata
from pathlib import Path

import nbformat

from .model import SelectedCopy


@dataclass(frozen=True, slots=True)
class StudentIdentity:
    display_name: str
    family_name: str | None = None
    given_names: str | None = None
    email: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("Le nom étudiant ne peut pas être vide.")
        if self.email is not None:
            if not isinstance(self.email, str) or "@" not in self.email or self.email != self.email.strip():
                raise ValueError("L'email étudiant est invalide.")
            object.__setattr__(self, "email", self.email.casefold())


class CopyIdentitySource(str, Enum):
    NOTEBOOK = "notebook"
    FILENAME = "filename"
    MANUAL = "manual"


class CopyIdentityStatus(str, Enum):
    CONFIRMED = "confirmed"
    TO_REVIEW = "to_review"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class CopyIdentity:
    students: tuple[StudentIdentity, ...]
    source: CopyIdentitySource | None
    status: CopyIdentityStatus
    raw_value: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "students", tuple(self.students))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        if self.status is CopyIdentityStatus.MISSING and self.students:
            raise ValueError("Une identité manquante ne peut pas porter d'étudiants.")


_LABEL = re.compile(r"(?im)^\s*[#*_]*\s*(?:nom\(s\)|noms?|étudiants?|etudiants?|binôme|binome)\s*:?[#*_]*\s*(.+?)\s*$")
_PLACEHOLDERS = {"", "nom", "prénom", "prenom", "nom prénom", "nom prenom", "à compléter", "a compléter", "a completer", "votre nom", "vos noms", "xxx", "???"}


def _clean_value(value: str) -> str:
    value = re.sub(r"^[#*_\s]+|[#*_\s]+$", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _is_placeholder(value: str) -> bool:
    return _clean_value(value).casefold() in _PLACEHOLDERS


def _students_from_value(value: str) -> tuple[StudentIdentity, ...]:
    value = _clean_value(value)
    if _is_placeholder(value):
        return ()
    parts = re.split(r"\s+(?:et|&|and)\s+|[,;/]", value, flags=re.IGNORECASE)
    return tuple(StudentIdentity(part.strip()) for part in parts if part.strip() and not _is_placeholder(part))


def extract_copy_identity_from_notebook(notebook_path: Path) -> CopyIdentity:
    try:
        notebook = nbformat.read(notebook_path, as_version=4)
    except Exception:
        return CopyIdentity((), None, CopyIdentityStatus.MISSING, warnings=("Notebook invalide.",))
    for cell in tuple(notebook.cells)[:15]:
        if cell.cell_type != "markdown":
            continue
        match = _LABEL.search(cell.source)
        if match:
            raw = _clean_value(match.group(1))
            students = _students_from_value(raw)
            if students:
                return CopyIdentity(students, CopyIdentitySource.NOTEBOOK, CopyIdentityStatus.CONFIRMED, raw)
            return CopyIdentity((), None, CopyIdentityStatus.MISSING, raw)
    return CopyIdentity((), None, CopyIdentityStatus.MISSING)


def extract_identity_hint_from_filename(original_filename: str) -> tuple[str, ...]:
    stem = Path(original_filename).stem
    tokens = [token for token in re.split(r"[-_\s]+", stem) if token]
    ignored = {"tp", "lois", "de", "snell", "descartes", "laws", "untitled", "copy", "et", "and"}
    return tuple(token for token in tokens if token.casefold() not in ignored and not token.isdigit() and len(token) > 1)


def _normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _identity_tokens(value: str) -> set[str]:
    return {token for token in _normalise(value).split() if len(token) > 1}


def resolve_copy_identity(notebook_identity: CopyIdentity, *, filename_hint: tuple[str, ...] = ()) -> CopyIdentity:
    if notebook_identity.status is CopyIdentityStatus.MISSING:
        if filename_hint:
            return CopyIdentity((), CopyIdentitySource.FILENAME, CopyIdentityStatus.TO_REVIEW, warnings=("Identité absente du notebook ; indice filename à vérifier.",))
        return notebook_identity
    filename_tokens = _identity_tokens(" ".join(filename_hint))
    student_tokens = [_identity_tokens(student.display_name) for student in notebook_identity.students]
    # Missing tokens are not contradictory: a filename may contain only first
    # names, only family names, or names in a different order. Contradiction
    # requires a sufficiently strong signal with no overlap at all.
    if filename_tokens and len(filename_tokens) >= 2 and not any(filename_tokens & tokens for tokens in student_tokens):
        return replace(notebook_identity, status=CopyIdentityStatus.TO_REVIEW, warnings=("Le nom du fichier semble indiquer une identité différente.",))
    return notebook_identity


def identify_selected_copy(selected: SelectedCopy) -> SelectedCopy:
    notebook_identity = extract_copy_identity_from_notebook(selected.workspace_path)
    resolved = resolve_copy_identity(notebook_identity, filename_hint=extract_identity_hint_from_filename(selected.original_filename))
    return replace(selected, identity=resolved)


def confirm_copy_identity(selected: SelectedCopy, students: tuple[StudentIdentity, ...] | list[StudentIdentity]) -> SelectedCopy:
    """Apply an explicit teacher choice without consulting filename evidence."""
    chosen = tuple(students)
    if not chosen:
        raise ValueError("Au moins un étudiant doit être sélectionné.")
    if any(type(student) is not StudentIdentity for student in chosen):
        raise TypeError("La sélection d'étudiants est invalide.")
    identity = CopyIdentity(
        chosen, CopyIdentitySource.MANUAL, CopyIdentityStatus.CONFIRMED,
        " & ".join(student.display_name for student in chosen),
    )
    return replace(selected, identity=identity)


def canonical_tp_name(project_id: str) -> str:
    return "Lois-de-Snell-Descartes" if project_id == "snells-laws-mvp" else project_id


def _safe_component(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = re.sub(r"[^\w]+", "-", value, flags=re.UNICODE)
    return re.sub(r"-+", "-", value).strip("-")


def build_canonical_copy_stem(tp_name: str, identity: CopyIdentity) -> str | None:
    if identity.status is not CopyIdentityStatus.CONFIRMED or not identity.students:
        return None
    components = [_safe_component(tp_name)] + [_safe_component(student.display_name) for student in identity.students]
    components = [component for component in components if component]
    return "-".join(components) or None
