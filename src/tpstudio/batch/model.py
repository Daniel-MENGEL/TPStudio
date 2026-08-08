"""Immutable contracts for controlled A71g batches."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from tpstudio.export import CopyExportOptions


def validate_output_stem(output_stem: str) -> str:
    if not isinstance(output_stem, str) or not output_stem or output_stem != output_stem.strip():
        raise ValueError("output_stem doit être un stem non vide sans espaces périphériques.")
    if output_stem in {".", ".."} or "/" in output_stem or "\\" in output_stem or "\x00" in output_stem:
        raise ValueError("output_stem doit être un nom logique sans chemin.")
    if output_stem.lower().endswith((".ipynb", ".html")):
        raise ValueError("output_stem ne doit pas contenir de suffixe de fichier.")
    return output_stem


@dataclass(frozen=True, slots=True)
class BatchCopySource:
    source_id: str
    path: Path
    display_name: str = ""
    output_stem: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id ne peut pas être vide.")
        if not isinstance(self.path, Path):
            raise TypeError("path doit être un pathlib.Path.")
        if self.display_name and not isinstance(self.display_name, str):
            raise TypeError("display_name doit être une chaîne.")
        if self.output_stem is not None:
            validate_output_stem(self.output_stem)


@dataclass(frozen=True, slots=True)
class BatchOptions:
    overwrite: bool = False
    continue_on_error: bool = True
    include_teacher_feedback: bool = False
    include_diagnostics: bool = False
    hide_code: bool = False
    hide_outputs: bool = False

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"L'option {name!r} doit être un booléen exact.")

    def export_options(self) -> CopyExportOptions:
        return CopyExportOptions(
            overwrite=self.overwrite,
            include_teacher_feedback=self.include_teacher_feedback,
            include_diagnostics=self.include_diagnostics,
            include_code=not self.hide_code,
            include_outputs=not self.hide_outputs,
        )


class BatchCopyStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class BatchCopyResult:
    source_id: str
    status: BatchCopyStatus
    notebook_path: Path | None = None
    html_path: Path | None = None
    annotation_count: int = 0
    requires_human_review: bool | None = None
    limitations: tuple[str, ...] = ()
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id ne peut pas être vide.")
        if type(self.status) is not BatchCopyStatus:
            raise TypeError("Le statut de copie est invalide.")
        if type(self.annotation_count) is not int or self.annotation_count < 0:
            raise ValueError("annotation_count doit être positif ou nul.")
        object.__setattr__(self, "limitations", tuple(self.limitations))
        if self.status is BatchCopyStatus.SUCCESS:
            if not isinstance(self.notebook_path, Path) or not isinstance(self.html_path, Path):
                raise ValueError("Une copie réussie doit référencer ses deux artefacts.")
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("Une copie réussie ne porte pas d'erreur.")
        elif self.status is BatchCopyStatus.FAILED:
            if self.notebook_path is not None or self.html_path is not None:
                raise ValueError("Une copie échouée ne doit annoncer aucun artefact.")
            if not self.error_type or not self.error_message:
                raise ValueError("Une copie échouée doit expliquer son erreur.")
        elif self.status is BatchCopyStatus.SKIPPED:
            if self.notebook_path is not None or self.html_path is not None:
                raise ValueError("Une copie ignorée ne doit annoncer aucun artefact.")
            if not self.error_message:
                raise ValueError("Une copie ignorée doit fournir une raison.")


@dataclass(frozen=True, slots=True)
class PlannedBatchOutput:
    source_id: str
    notebook_path: Path
    html_path: Path


@dataclass(frozen=True, slots=True)
class BatchPlan:
    sources: tuple[BatchCopySource, ...]
    output_dir: Path
    options: BatchOptions
    planned_outputs: tuple[PlannedBatchOutput, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "planned_outputs", tuple(self.planned_outputs))
        if not isinstance(self.output_dir, Path) or type(self.options) is not BatchOptions:
            raise TypeError("Le plan de lot est invalide.")
        if len(self.sources) != len(self.planned_outputs):
            raise ValueError("Le plan doit associer chaque source à une sortie.")
        source_ids = tuple(item.source_id for item in self.sources)
        output_ids = tuple(item.source_id for item in self.planned_outputs)
        if len(set(source_ids)) != len(source_ids) or len(set(output_ids)) != len(output_ids):
            raise ValueError("Les identifiants du plan doivent être uniques.")
        if source_ids != output_ids:
            raise ValueError("Les sources et sorties du plan doivent avoir les mêmes source_id.")


@dataclass(frozen=True, slots=True)
class BatchRunResult:
    project_id: str
    results: tuple[BatchCopyResult, ...]
    output_dir: Path
    started_count: int
    success_count: int
    failed_count: int
    skipped_count: int
    total_annotation_count: int
    human_review_count: int

    def __post_init__(self) -> None:
        results = tuple(self.results)
        object.__setattr__(self, "results", results)
        if any(type(item) is not BatchCopyResult for item in results):
            raise TypeError("Le résultat de lot contient une copie invalide.")
        if any(item.status is BatchCopyStatus.PENDING for item in results):
            raise ValueError("Un résultat final ne peut pas contenir de copie PENDING.")
        counts = {
            BatchCopyStatus.SUCCESS: sum(item.status is BatchCopyStatus.SUCCESS for item in results),
            BatchCopyStatus.FAILED: sum(item.status is BatchCopyStatus.FAILED for item in results),
            BatchCopyStatus.SKIPPED: sum(item.status is BatchCopyStatus.SKIPPED for item in results),
        }
        if type(self.started_count) is not int or self.started_count < 0 or self.started_count > len(results):
            raise ValueError("started_count est incohérent.")
        if (self.success_count, self.failed_count, self.skipped_count) != (counts[BatchCopyStatus.SUCCESS], counts[BatchCopyStatus.FAILED], counts[BatchCopyStatus.SKIPPED]):
            raise ValueError("Les compteurs de statut sont incohérents.")
        if self.started_count != counts[BatchCopyStatus.SUCCESS] + counts[BatchCopyStatus.FAILED]:
            raise ValueError("started_count est incohérent avec les statuts.")
        if self.total_annotation_count != sum(item.annotation_count for item in results):
            raise ValueError("total_annotation_count est incohérent.")
        if self.human_review_count != sum(item.requires_human_review is True for item in results):
            raise ValueError("human_review_count est incohérent.")

    @property
    def success(self) -> bool:
        return bool(self.results) and self.success_count == len(self.results)

    @property
    def has_failures(self) -> bool:
        return self.failed_count > 0

    @property
    def successful_results(self) -> tuple[BatchCopyResult, ...]:
        return tuple(item for item in self.results if item.status is BatchCopyStatus.SUCCESS)

    @property
    def failed_results(self) -> tuple[BatchCopyResult, ...]:
        return tuple(item for item in self.results if item.status is BatchCopyStatus.FAILED)

    def get(self, source_id: str) -> BatchCopyResult | None:
        return next((item for item in self.results if item.source_id == source_id), None)
