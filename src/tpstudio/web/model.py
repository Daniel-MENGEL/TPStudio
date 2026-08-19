"""Small immutable UI-domain models; no Streamlit dependency."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .identity import CopyIdentity
    from tpstudio.orchestration import CopyAnalysisResult


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
