"""Generic multi-project copy dispatch without export side effects."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from tpstudio.projects import TeacherProjectConfiguration

from .copy_analysis import (
    AnalysisReadiness,
    CopyAnalysisDispatchResult,
    CopyAnalysisOptions,
    ProjectSelectionProvenance,
    analyze_copy,
)
from .notebook_inspection import NotebookCopySource


class BatchCopyDispatchStatus(str, Enum):
    """Outcome of dispatching one copy in a generic analysis batch."""

    ANALYZED = "analyzed"
    UNRESOLVED = "unresolved"
    RESOLVED_NOT_READY = "resolved_not_ready"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class BatchCopyRequest:
    """One source and its optional explicit project contract."""

    source_id: str
    source: NotebookCopySource
    project: TeacherProjectConfiguration | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id doit être une chaîne non vide.")
        if type(self.source) is not NotebookCopySource:
            raise TypeError("source doit être exactement un NotebookCopySource.")
        if self.project is not None and type(self.project) is not TeacherProjectConfiguration:
            raise TypeError("project doit être un TeacherProjectConfiguration ou None.")


@dataclass(frozen=True, slots=True)
class BatchCopyDispatchResult:
    """One ordered batch outcome, retaining the A75a2 dispatch unchanged."""

    source_id: str
    status: BatchCopyDispatchStatus
    dispatch: CopyAnalysisDispatchResult | None = None
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id doit être une chaîne non vide.")
        if type(self.status) is not BatchCopyDispatchStatus:
            raise TypeError("Le statut de dispatch est invalide.")
        if self.dispatch is not None and type(self.dispatch) is not CopyAnalysisDispatchResult:
            raise TypeError("Le dispatch de copie est invalide.")
        if self.error_type is not None and (not isinstance(self.error_type, str) or not self.error_type.strip()):
            raise ValueError("error_type doit être une chaîne non vide ou None.")
        if self.error_message is not None and (not isinstance(self.error_message, str) or not self.error_message.strip()):
            raise ValueError("error_message doit être une chaîne non vide ou None.")

        if self.status is BatchCopyDispatchStatus.ANALYZED:
            if self.dispatch is None or self.dispatch.analysis is None:
                raise ValueError("ANALYZED exige une analyse.")
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("ANALYZED ne peut pas porter d'erreur.")
        elif self.status is BatchCopyDispatchStatus.UNRESOLVED:
            if self.dispatch is None or self.dispatch.analysis is not None:
                raise ValueError("UNRESOLVED exige un dispatch sans analyse.")
            if self.dispatch.provenance is not ProjectSelectionProvenance.UNRESOLVED:
                raise ValueError("UNRESOLVED exige la provenance correspondante.")
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("UNRESOLVED ne peut pas porter d'erreur.")
        elif self.status is BatchCopyDispatchStatus.RESOLVED_NOT_READY:
            if self.dispatch is None or self.dispatch.analysis is not None:
                raise ValueError("RESOLVED_NOT_READY exige un dispatch sans analyse.")
            if self.dispatch.provenance is ProjectSelectionProvenance.UNRESOLVED:
                raise ValueError("RESOLVED_NOT_READY exige une résolution aboutie.")
            if self.dispatch.readiness is not AnalysisReadiness.NOT_READY:
                raise ValueError("RESOLVED_NOT_READY exige une readiness NOT_READY.")
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("RESOLVED_NOT_READY ne peut pas porter d'erreur.")
        elif self.status is BatchCopyDispatchStatus.ERROR:
            if self.dispatch is not None or self.error_type is None or self.error_message is None:
                raise ValueError("ERROR exige une erreur et aucun dispatch.")
        elif self.status is BatchCopyDispatchStatus.SKIPPED:
            if self.dispatch is not None or self.error_type is not None or self.error_message is None:
                raise ValueError("SKIPPED exige une raison et aucun dispatch.")


@dataclass(frozen=True, slots=True)
class BatchDispatchResult:
    """Ordered outcomes for a generic multi-project analysis batch."""

    copies: tuple[BatchCopyDispatchResult, ...]

    def __post_init__(self) -> None:
        copies = tuple(self.copies)
        if any(type(item) is not BatchCopyDispatchResult for item in copies):
            raise TypeError("Le résultat contient une copie invalide.")
        source_ids = tuple(item.source_id for item in copies)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Les source_id doivent être uniques dans un batch.")
        object.__setattr__(self, "copies", copies)

    @property
    def analyzed_count(self) -> int:
        return sum(item.status is BatchCopyDispatchStatus.ANALYZED for item in self.copies)

    @property
    def unresolved_count(self) -> int:
        return sum(item.status is BatchCopyDispatchStatus.UNRESOLVED for item in self.copies)

    @property
    def error_count(self) -> int:
        return sum(item.status is BatchCopyDispatchStatus.ERROR for item in self.copies)

    @property
    def resolved_not_ready_count(self) -> int:
        return sum(item.status is BatchCopyDispatchStatus.RESOLVED_NOT_READY for item in self.copies)

    @property
    def skipped_count(self) -> int:
        return sum(item.status is BatchCopyDispatchStatus.SKIPPED for item in self.copies)

    @property
    def project_ids(self) -> tuple[str, ...]:
        """Return analyzed project identifiers in first-seen order."""
        values: list[str] = []
        for item in self.copies:
            if item.dispatch is None or item.dispatch.analysis is None:
                continue
            project_id = item.dispatch.analysis.project_id
            if project_id not in values:
                values.append(project_id)
        return tuple(values)

    def get(self, source_id: str) -> BatchCopyDispatchResult | None:
        return next((item for item in self.copies if item.source_id == source_id), None)


def run_batch(
    requests: Iterable[BatchCopyRequest],
    *,
    options: CopyAnalysisOptions | None = None,
    continue_on_error: bool = True,
) -> BatchDispatchResult:
    """Analyze requests sequentially, without exporting or selecting a global project."""
    requests = tuple(requests)
    if any(type(item) is not BatchCopyRequest for item in requests):
        raise TypeError("Chaque requête doit être exactement un BatchCopyRequest.")
    source_ids = tuple(item.source_id for item in requests)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Les source_id doivent être uniques dans un batch.")
    if type(continue_on_error) is not bool:
        raise TypeError("continue_on_error doit être un booléen exact.")
    if options is not None and type(options) is not CopyAnalysisOptions:
        raise TypeError("options doit être un CopyAnalysisOptions ou None.")

    results: list[BatchCopyDispatchResult] = []
    stopped = False
    for request in requests:
        if stopped:
            results.append(BatchCopyDispatchResult(
                request.source_id,
                BatchCopyDispatchStatus.SKIPPED,
                error_message="Copie non traitée après une erreur technique.",
            ))
            continue
        try:
            dispatch = analyze_copy(request.source, project=request.project, options=options)
        except Exception as exc:
            results.append(BatchCopyDispatchResult(
                request.source_id,
                BatchCopyDispatchStatus.ERROR,
                error_type=type(exc).__name__,
                error_message=str(exc) or type(exc).__name__,
            ))
            if not continue_on_error:
                stopped = True
            continue
        if dispatch.analysis is not None:
            status = BatchCopyDispatchStatus.ANALYZED
        elif dispatch.provenance is ProjectSelectionProvenance.UNRESOLVED:
            status = BatchCopyDispatchStatus.UNRESOLVED
        else:
            status = BatchCopyDispatchStatus.RESOLVED_NOT_READY
        results.append(BatchCopyDispatchResult(request.source_id, status, dispatch=dispatch))
    return BatchDispatchResult(tuple(results))
