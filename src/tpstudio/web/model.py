"""Small immutable UI-domain models; no Streamlit dependency."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .identity import CopyIdentity
    from tpstudio.orchestration import CopyAnalysisResult
    from tpstudio.export import CopyExportResult


def validate_upload_filename(filename: str) -> str:
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("Le nom du fichier est vide.")
    if "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise ValueError("Le nom du fichier contient un chemin interdit.")
    if not filename.lower().endswith(".ipynb"):
        raise ValueError("Seuls les fichiers .ipynb sont acceptés.")
    return filename


def validate_web_source_id(source_id: str) -> str:
    if not isinstance(source_id, str) or re.fullmatch(r"copy-[0-9]{3,}", source_id) is None:
        raise ValueError("source_id web invalide.")
    return source_id


@dataclass(frozen=True, slots=True)
class SelectedCopy:
    source_id: str
    original_filename: str
    workspace_path: Path
    content_sha256: str
    identity: "CopyIdentity | None" = None

    def __post_init__(self) -> None:
        validate_web_source_id(self.source_id)
        validate_upload_filename(self.original_filename)
        if not isinstance(self.workspace_path, Path):
            raise TypeError("workspace_path doit être un Path.")
        if not isinstance(self.content_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", self.content_sha256) is None:
            raise ValueError("content_sha256 doit être un SHA-256 hexadécimal.")


@dataclass(frozen=True, slots=True)
class WebBatchOptions:
    include_teacher_feedback: bool = False
    include_diagnostics: bool = False
    hide_code: bool = False
    hide_outputs: bool = False
    overwrite: bool = False

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"L'option {name!r} doit être un booléen exact.")


@dataclass(frozen=True, slots=True)
class WebCopyOverride:
    """Teacher-selected active analysis, kept outside the scientific dispatch."""

    source_id: str
    project_id: str
    analysis: "CopyAnalysisResult"
    validated_by_teacher: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id doit être une chaîne non vide.")
        if not isinstance(self.project_id, str) or not self.project_id.strip():
            raise ValueError("project_id doit être une chaîne non vide.")
        from tpstudio.orchestration import CopyAnalysisResult

        if type(self.analysis) is not CopyAnalysisResult:
            raise TypeError("analysis doit être un CopyAnalysisResult.")
        if self.analysis.source_id != self.source_id or self.analysis.project_id != self.project_id:
            raise ValueError("L'override ne correspond pas à la copie ou au projet.")
        if type(self.validated_by_teacher) is not bool:
            raise TypeError("validated_by_teacher doit être booléen.")


@dataclass(frozen=True, slots=True)
class WebCopyExportState:
    """Export outcome kept separate from analysis and project overrides."""

    source_id: str
    result: "CopyExportResult | None" = None
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id doit être une chaîne non vide.")
        from tpstudio.export import CopyExportResult

        if self.result is not None and type(self.result) is not CopyExportResult:
            raise TypeError("result doit être un CopyExportResult ou None.")
        if self.error_type is not None and (not isinstance(self.error_type, str) or not self.error_type.strip()):
            raise ValueError("error_type doit être une chaîne non vide ou None.")
        if self.error_message is not None and (not isinstance(self.error_message, str) or not self.error_message.strip()):
            raise ValueError("error_message doit être une chaîne non vide ou None.")
        if self.result is not None and (self.error_type is not None or self.error_message is not None):
            raise ValueError("Un export réussi ne peut pas porter d'erreur.")
        if self.result is None and (self.error_type is None or self.error_message is None):
            raise ValueError("Un export en erreur doit porter son type et son message.")


class TeacherScientificSeverity(str, Enum):
    """Presentation-only severity for the compact teacher overview."""

    OK = "ok"
    REVIEW = "review"
    ERROR = "error"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class TeacherScientificOverviewRow:
    key: str
    label: str
    summary: str
    severity: TeacherScientificSeverity
    details: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("key", "label", "summary"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} doit être une chaîne non vide.")
        if type(self.severity) is not TeacherScientificSeverity:
            raise TypeError("severity doit être une TeacherScientificSeverity.")
        if any(not isinstance(item, str) or not item.strip() for item in self.details):
            raise ValueError("Chaque détail doit être une chaîne non vide.")
        object.__setattr__(self, "details", tuple(self.details))


@dataclass(frozen=True, slots=True)
class TeacherScientificOverview:
    rows: tuple[TeacherScientificOverviewRow, ...]

    def __post_init__(self) -> None:
        rows = tuple(self.rows)
        if any(type(row) is not TeacherScientificOverviewRow for row in rows):
            raise TypeError("Chaque ligne doit être une TeacherScientificOverviewRow.")
        keys = tuple(row.key for row in rows)
        if len(keys) != len(set(keys)):
            raise ValueError("Les clés de synthèse doivent être uniques.")
        object.__setattr__(self, "rows", rows)
