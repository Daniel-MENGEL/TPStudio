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

    def __post_init__(self) -> None:
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("Le nom étudiant ne peut pas être vide.")


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
    ignored = {"tp", "lois", "de", "snell", "descartes", "laws", "untitled", "copy"}
    return tuple(token for token in tokens if token.casefold() not in ignored and not token.isdigit() and len(token) > 1)


def _normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def resolve_copy_identity(notebook_identity: CopyIdentity, *, filename_hint: tuple[str, ...] = ()) -> CopyIdentity:
    if notebook_identity.status is CopyIdentityStatus.MISSING:
        if filename_hint:
            return CopyIdentity((), CopyIdentitySource.FILENAME, CopyIdentityStatus.TO_REVIEW, warnings=("Identité absente du notebook ; indice filename à vérifier.",))
        return notebook_identity
    notebook_text = _normalise(" ".join(student.display_name for student in notebook_identity.students))
    filename_text = _normalise(" ".join(filename_hint))
    if filename_hint and not all(token in filename_text for token in notebook_text.split()):
        return replace(notebook_identity, status=CopyIdentityStatus.TO_REVIEW, warnings=("Le filename semble divergent de l'identité du notebook.",))
    return notebook_identity


def identify_selected_copy(selected: SelectedCopy) -> SelectedCopy:
    notebook_identity = extract_copy_identity_from_notebook(selected.workspace_path)
    resolved = resolve_copy_identity(notebook_identity, filename_hint=extract_identity_hint_from_filename(selected.original_filename))
    return replace(selected, identity=resolved)


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
