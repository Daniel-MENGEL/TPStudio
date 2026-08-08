"""Small immutable UI-domain models; no Streamlit dependency."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .identity import CopyIdentity


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
