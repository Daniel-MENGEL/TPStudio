"""Immutable contracts for A71f export artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ExportArtifactKind(str, Enum):
    NOTEBOOK = "notebook"
    HTML = "html"


@dataclass(frozen=True, slots=True)
class CopyExportOptions:
    overwrite: bool = False
    include_teacher_feedback: bool = False
    include_diagnostics: bool = False
    include_limitations: bool = False
    execute_notebook: bool = False
    embed_images: bool = True
    include_code: bool = True
    include_outputs: bool = True
    include_input_prompts: bool = False
    include_output_prompts: bool = False

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"L'option {name!r} doit être un booléen exact.")
        if self.execute_notebook:
            raise NotImplementedError("A71f ne prend pas en charge l'exécution du notebook.")


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    kind: ExportArtifactKind
    path: Path
    created: bool
    overwritten: bool
    media_type: str
    source_id: str
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if type(self.kind) is not ExportArtifactKind:
            raise TypeError("Le type d'artefact est invalide.")
        if not isinstance(self.path, Path):
            raise TypeError("Le chemin d'artefact doit être un pathlib.Path.")
        if type(self.created) is not bool or type(self.overwritten) is not bool:
            raise TypeError("Les indicateurs d'artefact doivent être booléens.")
        for name in ("media_type", "source_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} ne peut pas être vide.")
        object.__setattr__(self, "metadata", tuple(self.metadata))


@dataclass(frozen=True, slots=True)
class NotebookExportValidation:
    valid: bool
    cell_count: int
    annotation_count: int
    nbformat: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CopyExportResult:
    project_id: str
    source_id: str
    notebook_artifact: ExportArtifact
    html_artifact: ExportArtifact
    annotation_count: int
    student_annotation_count: int
    teacher_annotation_count: int
    source_preserved: bool
    notebook_valid: bool
    html_generated: bool
    limitations: tuple[str, ...] = ()

    @property
    def output_paths(self) -> tuple[Path, Path]:
        return self.notebook_artifact.path, self.html_artifact.path

    @property
    def success(self) -> bool:
        return self.source_preserved and self.notebook_valid and self.html_generated

    @property
    def has_limitations(self) -> bool:
        return bool(self.limitations)
