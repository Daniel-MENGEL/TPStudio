"""Immutable contracts for controlled TPStudio notebook annotations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tpstudio.feedback import FeedbackAudience
from tpstudio.reporting import TeacherReportSeverity


class AnnotationKind(str, Enum):
    FEEDBACK = "feedback"
    DIAGNOSTIC = "diagnostic"
    LIMITATION = "limitation"
    REVIEW = "review"


class AnnotationPlacement(str, Enum):
    AFTER_CELL = "after_cell"
    BEFORE_CELL = "before_cell"
    APPEND_TO_MARKDOWN = "append_to_markdown"


class SkippedAnnotationReason(str, Enum):
    TARGET_UNAVAILABLE = "target_unavailable"
    TARGET_AMBIGUOUS = "target_ambiguous"
    AUDIENCE_EXCLUDED = "audience_excluded"
    DUPLICATE = "duplicate"
    PLACEMENT_DISABLED = "placement_disabled"


@dataclass(frozen=True, slots=True)
class NotebookAnnotation:
    annotation_id: str
    kind: AnnotationKind
    audience: FeedbackAudience
    message: str
    source_ids: tuple[str, ...]
    production_id: str | None
    comparison_id: str | None
    target_cell_index: int
    placement: AnnotationPlacement
    severity: TeacherReportSeverity
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in ("annotation_id", "message"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} ne peut pas être vide.")
        if type(self.kind) is not AnnotationKind:
            raise TypeError("Le type d'annotation est invalide.")
        if type(self.audience) is not FeedbackAudience:
            raise TypeError("L'audience est invalide.")
        if type(self.placement) is not AnnotationPlacement:
            raise TypeError("Le placement est invalide.")
        if type(self.severity) is not TeacherReportSeverity:
            raise TypeError("La sévérité de présentation est invalide.")
        if type(self.target_cell_index) is not int or self.target_cell_index < 0:
            raise ValueError("L'indice de cellule doit être un entier positif ou nul.")
        sources = tuple(self.source_ids)
        if not sources or any(not isinstance(item, str) or not item.strip() for item in sources):
            raise ValueError("Une annotation exige au moins une source non vide.")
        metadata = tuple(self.metadata)
        if any(
            not isinstance(item, tuple) or len(item) != 2
            or not all(isinstance(value, str) for value in item)
            for item in metadata
        ):
            raise TypeError("Les métadonnées doivent être des paires de chaînes.")
        object.__setattr__(self, "source_ids", sources)
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class SkippedAnnotation:
    source_id: str
    kind: AnnotationKind
    audience: FeedbackAudience
    reason: SkippedAnnotationReason
    production_id: str | None = None
    comparison_id: str | None = None


@dataclass(frozen=True, slots=True)
class AnnotationOptions:
    include_student_feedback: bool = True
    include_teacher_feedback: bool = False
    include_diagnostics: bool = False
    include_limitations: bool = False
    annotate_code_by_adjacent_markdown: bool = True
    replace_existing_tpstudio_annotations: bool = True

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"L'option {name!r} doit être un booléen exact.")


@dataclass(frozen=True, slots=True)
class AnnotationPlan:
    project_id: str
    source_id: str
    annotations: tuple[NotebookAnnotation, ...]
    skipped: tuple[SkippedAnnotation, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.project_id, str) or not self.project_id.strip():
            raise ValueError("project_id ne peut pas être vide.")
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id ne peut pas être vide.")
        annotations = tuple(self.annotations)
        skipped = tuple(self.skipped)
        limitations = tuple(self.limitations)
        if any(type(item) is not NotebookAnnotation for item in annotations):
            raise TypeError("Une annotation du plan est invalide.")
        if any(type(item) is not SkippedAnnotation for item in skipped):
            raise TypeError("Une annotation ignorée est invalide.")
        if len({item.annotation_id for item in annotations}) != len(annotations):
            raise ValueError("Les identifiants d'annotation doivent être uniques.")
        object.__setattr__(self, "annotations", annotations)
        object.__setattr__(self, "skipped", skipped)
        object.__setattr__(self, "limitations", limitations)

    def for_cell(self, cell_index: int) -> tuple[NotebookAnnotation, ...]:
        return tuple(item for item in self.annotations if item.target_cell_index == cell_index)

    @property
    def student_annotations(self) -> tuple[NotebookAnnotation, ...]:
        return tuple(item for item in self.annotations if item.audience is FeedbackAudience.STUDENT)

    @property
    def teacher_annotations(self) -> tuple[NotebookAnnotation, ...]:
        return tuple(item for item in self.annotations if item.audience is FeedbackAudience.TEACHER)

    @property
    def has_skipped(self) -> bool:
        return bool(self.skipped)

    @property
    def count(self) -> int:
        return len(self.annotations)

    @property
    def is_empty(self) -> bool:
        return not self.annotations


class ExistingAnnotationMode(str, Enum):
    APPENDED_BLOCK = "appended_block"
    DEDICATED_CELL = "dedicated_cell"


@dataclass(frozen=True, slots=True)
class ExistingNotebookAnnotation:
    annotation_id: str
    cell_index: int
    mode: ExistingAnnotationMode
    start: int | None = None
    end: int | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class AnnotatedNotebookResult:
    notebook: object
    applied_annotation_ids: tuple[str, ...]
    skipped_annotation_ids: tuple[str, ...]
    removed_annotation_ids: tuple[str, ...]
    original_cell_count: int
    final_cell_count: int
    changed: bool
