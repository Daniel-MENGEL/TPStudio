"""Pure, privacy-conscious presentation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from pathlib import Path

from tpstudio.batch import BatchPlan
from tpstudio.batch import BatchCopyStatus, BatchRunResult
from tpstudio.orchestration import (
    BatchCopyDispatchStatus, BatchDispatchResult, ProjectSelectionProvenance,
    SemanticResponseAnalysis,
)
from tpstudio.projects import known_project_ids, project_descriptor
from tpstudio.semantic_analysis import (
    SemanticAnalysisResult,
    SemanticCriterionImportance,
    SemanticCriterionStatus,
)
from tpstudio.interpretation import InterpretationClassification, InterpretationReviewTrace
from tpstudio.reporting import TeacherCopyReport, TeacherGraphHeadlineStatus
from .model import WebCopyOverride
from tpstudio.review_store import (
    latest_interpretation_review, load_interpretation_reviews, review_store_path,
)


@dataclass(frozen=True, slots=True)
class BatchPlanRow:
    copy_label: str
    source_id: str
    original_filename: str
    students_display: str
    identity_status: str
    identity_source: str
    notebook_output_name: str
    html_output_name: str


def batch_plan_rows(plan: BatchPlan, identities: Mapping[str, object] | None = None) -> tuple[BatchPlanRow, ...]:
    identities = identities or {}
    labels = {"confirmed": "Confirmée", "to_review": "À vérifier", "missing": "Non renseignée"}
    return tuple(
        BatchPlanRow(
            f"Copie {index}", source.source_id, source.display_name or source.path.name,
            " · ".join(student.display_name for student in getattr(identities.get(source.source_id), "students", ())) or "—",
            labels.get(getattr(getattr(identities.get(source.source_id), "status", None), "value", ""), "Non renseignée"),
            {"notebook": "Notebook", "filename": "Nom du fichier"}.get(getattr(getattr(identities.get(source.source_id), "source", None), "value", ""), "—"),
            output.notebook_path.name, output.html_path.name,
        )
        for index, (source, output) in enumerate(zip(plan.sources, plan.planned_outputs), 1)
    )


def has_output_name_collision(plan: BatchPlan) -> bool:
    source_names = [source.display_name or source.path.name for source in plan.sources]
    return len(source_names) != len(set(source_names))


def identity_resolution_candidates(copies, roster=()) -> tuple:
    """Return the deduplicated student identities known in the current lot."""
    if roster:
        return tuple(student.to_identity() for student in roster)
    by_name = {
        student.display_name: student
        for item in copies
        if getattr(item, "identity", None) is not None
        for student in item.identity.students
    }
    return tuple(by_name[name] for name in sorted(by_name))


@dataclass(frozen=True, slots=True)
class BatchRunRow:
    copy_label: str
    source_id: str
    students_display: str
    status: str
    notebook_output_name: str
    html_output_name: str
    annotation_count: int
    human_review: str
    limitations: str
    error: str
    problem: str


@dataclass(frozen=True, slots=True)
class BatchDispatchRow:
    source_id: str
    display_name: str
    status: str
    project_id: str | None
    project_title: str | None
    confidence: str | None
    provenance: str
    requires_teacher_choice: bool
    error_message: str | None
    evidence: tuple[tuple[str, str], ...]
    validated_by_teacher: bool = False


@dataclass(frozen=True, slots=True)
class SemanticCriterionRow:
    criterion_id: str
    description: str
    importance: str
    importance_label: str
    status: str
    status_label: str
    evidence: str
    stable_key: str


@dataclass(frozen=True, slots=True)
class SemanticResponseRow:
    source_id: str
    production_id: str
    role: str
    role_label: str
    binding_status: str
    binding_label: str
    student_response: str | None
    criteria: tuple[SemanticCriterionRow, ...]
    contradictions: tuple[str, ...]
    confidence: str | None
    diagnostics: tuple[str, ...]
    stable_key: str


_SEMANTIC_STATUS_LABELS = {
    SemanticCriterionStatus.SATISFIED: "Présent",
    SemanticCriterionStatus.PARTIAL: "Partiel",
    SemanticCriterionStatus.NOT_FOUND: "Non repéré",
    SemanticCriterionStatus.UNCERTAIN: "À vérifier",
}
_SEMANTIC_IMPORTANCE_LABELS = {
    SemanticCriterionImportance.REQUIRED: "Requis",
    SemanticCriterionImportance.RECOMMENDED: "Recommandé",
}
_SEMANTIC_BINDING_LABELS = {
    "resolved": "Réponse localisée",
    "absent": "Cellule de réponse introuvable",
    "ambiguous": "Cellule de réponse ambiguë",
}
_SEMANTIC_ROLE_LABELS = {
    "objective": "Objectif",
    "protocol": "Protocole",
    "interpretation": "Interprétation",
    "conclusion": "Conclusion",
}


def _semantic_stable_key(source_id: str, production_id: str, criterion_id: str | None = None) -> str:
    import re

    parts = [source_id, production_id]
    if criterion_id is not None:
        parts.append(criterion_id)
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", "-".join(parts)).strip("-") or "copy"
    return f"semantic-{safe}"


def _safe_semantic_diagnostic(value: str) -> str:
    if value == "EMPTY_RESPONSE":
        return "Réponse vide."
    if value == "SEMANTIC_PROVIDER_UNAVAILABLE":
        return "Fournisseur sémantique indisponible."
    if value.startswith("SEMANTIC_PROVIDER_ERROR:"):
        return "Erreur contrôlée du fournisseur sémantique."
    if value == "SEMANTIC_INVALID_PROVIDER_RESULT":
        return "Résultat sémantique invalide."
    if value == "SEMANTIC_PRODUCTION_MISMATCH":
        return "Résultat sémantique incohérent avec la production."
    if value == "SEMANTIC_CRITERIA_MISMATCH":
        return "Critères sémantiques incomplets ou incohérents."
    return "Diagnostic sémantique contrôlé."


def _semantic_confidence_label(value: str | None) -> str | None:
    if value is None:
        return None
    return {
        "high": "Haute",
        "medium": "Moyenne",
        "low": "Faible",
        "none": "Non renseignée",
        "unknown": "Non renseignée",
    }.get(value.casefold(), "Non renseignée")


def semantic_response_rows(
    analyses: tuple[SemanticResponseAnalysis, ...] | list[SemanticResponseAnalysis],
    *,
    source_id: str,
) -> tuple[SemanticResponseRow, ...]:
    """Build immutable, non-scoring views of semantic response analyses."""
    rows: list[SemanticResponseRow] = []
    for analysis in tuple(analyses):
        if type(analysis) is not SemanticResponseAnalysis:
            raise TypeError("Les analyses sémantiques sont invalides.")
        result: SemanticAnalysisResult | None = analysis.result
        result_by_id = {item.criterion_id: item for item in result.criterion_results} if result else {}
        criteria = tuple(
            SemanticCriterionRow(
                criterion.criterion_id,
                criterion.description,
                criterion.importance.value,
                _SEMANTIC_IMPORTANCE_LABELS[criterion.importance],
                result_by_id[criterion.criterion_id].status.value
                if result is not None and criterion.criterion_id in result_by_id
                else "not_evaluated",
                _SEMANTIC_STATUS_LABELS.get(
                    result_by_id[criterion.criterion_id].status if result is not None and criterion.criterion_id in result_by_id else "not_evaluated",
                    "Non évalué",
                ),
                result_by_id[criterion.criterion_id].evidence if criterion.criterion_id in result_by_id else "",
                _semantic_stable_key(source_id, analysis.contract.production_id, criterion.criterion_id),
            )
            for criterion in analysis.contract.criteria
        )
        if result is not None:
            diagnostics = tuple(_safe_semantic_diagnostic(item) for item in result.diagnostics)
        elif analysis.binding_absent:
            diagnostics = ("La cellule contenant la réponse n’a pas été trouvée.",)
        elif analysis.binding_ambiguous:
            diagnostics = ("Plusieurs cellules peuvent correspondre à cette réponse.",)
        else:
            diagnostics = ()
        rows.append(SemanticResponseRow(
            source_id,
            analysis.contract.production_id,
            analysis.contract.semantic_role.value,
            _SEMANTIC_ROLE_LABELS.get(analysis.contract.semantic_role.value, analysis.contract.semantic_role.value),
            "resolved" if analysis.binding_resolved else "ambiguous" if analysis.binding_ambiguous else "absent",
            _SEMANTIC_BINDING_LABELS["resolved" if analysis.binding_resolved else "ambiguous" if analysis.binding_ambiguous else "absent"],
            analysis.student_response,
            criteria,
            result.contradictions if result else (),
            _semantic_confidence_label(result.confidence) if result else None,
            diagnostics,
            _semantic_stable_key(source_id, analysis.contract.production_id),
        ))
    return tuple(rows)


def _confidence_label(value) -> str | None:
    return {"high": "Haute", "medium": "Moyenne", "low": "Faible", None: None}.get(getattr(value, "value", value), None)


def _provenance_label(value) -> str:
    return {
        ProjectSelectionProvenance.AUTO_RESOLVED: "Détection automatique",
        ProjectSelectionProvenance.EXPLICIT: "Projet imposé",
        ProjectSelectionProvenance.UNRESOLVED: "Non résolu",
    }.get(value, "Non résolu")


def active_analysis_for_source(result: BatchDispatchResult, overrides: Mapping[str, WebCopyOverride], source_id: str):
    override = overrides.get(source_id)
    if override is not None:
        return override.analysis
    item = result.get(source_id)
    return item.dispatch.analysis if item and item.dispatch else None


def exportable_count(result: BatchDispatchResult, overrides: Mapping[str, WebCopyOverride]) -> int:
    return sum(active_analysis_for_source(result, overrides, item.source_id) is not None for item in result.copies)


def non_exportable_count(result: BatchDispatchResult, overrides: Mapping[str, WebCopyOverride]) -> int:
    return len(result.copies) - exportable_count(result, overrides)


def project_choices_for_source(result: BatchDispatchResult, source_id: str) -> tuple[str, ...]:
    item = result.get(source_id)
    candidate_ids = (
        tuple(candidate.project_id for candidate in item.dispatch.resolution.candidates)
        if item and item.dispatch else ()
    )
    known = known_project_ids()
    return tuple(dict.fromkeys(candidate_ids + known))


def batch_dispatch_rows(
    result: BatchDispatchResult,
    selected_copies=(),
    overrides: Mapping[str, WebCopyOverride] | None = None,
) -> tuple[BatchDispatchRow, ...]:
    overrides = overrides or {}
    labels = {
        BatchCopyDispatchStatus.ANALYZED: "Analysée",
        BatchCopyDispatchStatus.UNRESOLVED: "Aucun TP reconnu",
        BatchCopyDispatchStatus.RESOLVED_NOT_READY: "TP reconnu — analyse indisponible",
        BatchCopyDispatchStatus.ERROR: "Erreur technique",
        BatchCopyDispatchStatus.SKIPPED: "Non analysée à cause d'une erreur précédente",
    }
    names = {item.source_id: item.original_filename for item in selected_copies}
    rows = []
    for item in result.copies:
        dispatch = item.dispatch
        resolution = dispatch.resolution if dispatch else None
        override = overrides.get(item.source_id)
        analysis = override.analysis if override else (dispatch.analysis if dispatch else None)
        project_id = analysis.project_id if analysis else (
            resolution.selected_project_id if resolution else None
        )
        candidate = None
        if resolution:
            candidate = next((value for value in resolution.candidates if value.project_id == resolution.selected_project_id), None)
        if candidate is None and resolution:
            candidate = resolution.candidates[0] if resolution.candidates else None
        title = analysis.project.identity.title if analysis else (project_descriptor(candidate.project_id).title if candidate and project_descriptor(candidate.project_id) else None)
        status = "Analysée" if analysis is not None else (
            "TP à confirmer" if item.status is BatchCopyDispatchStatus.UNRESOLVED and candidate else labels[item.status]
        )
        provenance = "Projet choisi par l'enseignant" if override else _provenance_label(dispatch.provenance if dispatch else None)
        confidence = None if override else _confidence_label(candidate.confidence if candidate else None)
        evidence = tuple((e.kind, e.text) for c in (resolution.candidates if resolution else ()) for e in c.evidence)
        rows.append(BatchDispatchRow(
            item.source_id, names.get(item.source_id, item.source_id), status,
            project_id, title, confidence,
            provenance,
            bool(resolution and resolution.requires_teacher_choice),
            item.error_message[:240] if item.error_message else None, evidence,
            bool(override and override.validated_by_teacher),
        ))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class GraphSummaryRow:
    """Streamlit-ready view of one teacher graph summary."""

    icon: str
    headline: str
    summary_lines: tuple[str, ...]
    technical_details: tuple[str, ...]
    requires_human_review: bool
    stable_key: str


_GRAPH_HEADLINE_ICONS = {
    TeacherGraphHeadlineStatus.OK: "✅",
    TeacherGraphHeadlineStatus.PROBLEM: "❌",
    TeacherGraphHeadlineStatus.REVIEW: "⚠️",
    TeacherGraphHeadlineStatus.INFO: "ℹ️",
}


def _stable_graph_key(regression_id: str, key_prefix: str = "") -> str:
    import re

    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", f"{key_prefix}-{regression_id}").strip("-")
    return f"graph-summary-{value or 'regression'}"


def graph_summary_rows(
    report: TeacherCopyReport | None,
    *,
    key_prefix: str = "",
) -> tuple[GraphSummaryRow, ...]:
    """Convert teacher graph summaries into pure, UI-independent rows."""
    if report is None:
        return ()
    return tuple(
        GraphSummaryRow(
            _GRAPH_HEADLINE_ICONS[summary.headline_status],
            summary.headline_text,
            tuple(summary.summary_lines),
            tuple(summary.technical_details),
            summary.requires_human_review,
            _stable_graph_key(summary.regression_id, key_prefix),
        )
        for summary in report.regression_graphs
    )


def _review_label(value: bool | None) -> str:
    return "oui" if value is True else "non" if value is False else "indéterminée"


def batch_run_rows(result: BatchRunResult, selected_copies=()) -> tuple[BatchRunRow, ...]:
    identities = {item.source_id: item.identity for item in selected_copies}
    labels = {BatchCopyStatus.SUCCESS: "Réussie", BatchCopyStatus.FAILED: "Échec", BatchCopyStatus.SKIPPED: "Ignorée"}
    rows = []
    for index, item in enumerate(result.results, 1):
        identity = identities.get(item.source_id)
        students = " · ".join(student.display_name for student in getattr(identity, "students", ())) or "—"
        rows.append(BatchRunRow(
            f"Copie {index}", item.source_id, students, labels[item.status],
            item.notebook_path.name if item.notebook_path else "—",
            item.html_path.name if item.html_path else "—",
            item.annotation_count, _review_label(item.requires_human_review),
            " ; ".join(item.limitations) or "—", item.error_message or "",
            item.error_message or "—" if item.status is not BatchCopyStatus.SUCCESS else "—",
        ))
    return tuple(rows)


def artifact_download_info(item, output_dir: Path, kind: str) -> tuple[str, str, Path]:
    if kind not in {"notebook", "html"}:
        raise ValueError("Type d'artefact invalide.")
    path = item.notebook_path if kind == "notebook" else item.html_path
    if not isinstance(path, Path) or not isinstance(output_dir, Path):
        raise ValueError("Artefact invalide.")
    resolved_output = output_dir.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_output)
    except ValueError as exc:
        raise ValueError("Artefact hors du dossier de sortie.") from exc
    if not resolved_path.is_file():
        raise FileNotFoundError("Artefact indisponible.")
    return path.name, "application/x-ipynb+json" if kind == "notebook" else "text/html", path


@dataclass(frozen=True, slots=True)
class InterpretationReviewItem:
    trace: InterpretationReviewTrace
    copy_label: str
    current_review: InterpretationReviewTrace | None = None
    stale_review: bool = False

    @property
    def key(self) -> str:
        return f"{self.trace.copy_id}:{self.trace.expectation_id}:{self.trace.cell_id}"

    @property
    def status_label(self) -> str:
        if self.current_review is None:
            return "À revoir"
        return "Confirmée" if self.current_review.review_status == "CONFIRMED" else "Remplacée"

    @property
    def proposed_label(self) -> str:
        if self.trace.tpstudio_proposal is None:
            return f"{self.trace.tpstudio_status.name} — aucune classification automatique"
        return _classification_label(self.trace.tpstudio_proposal)


def _classification_label(value: InterpretationClassification | None) -> str:
    return {
        InterpretationClassification.CLEARLY_SUFFICIENT: "CLEARLY_SUFFICIENT",
        InterpretationClassification.CLEARLY_INSUFFICIENT: "CLEARLY_INSUFFICIENT",
        InterpretationClassification.AMBIGUOUS: "AMBIGUOUS",
        None: "—",
    }[value]


def select_interpretation_review_items(
    result: BatchRunResult,
    output_dir: Path,
    *,
    only_pending: bool = True,
    copy_labels: Mapping[str, str] | None = None,
) -> tuple[InterpretationReviewItem, ...]:
    """Select current interpretation proposals without mutating the store."""
    if not isinstance(output_dir, Path):
        raise TypeError("output_dir doit être un Path.")
    history = load_interpretation_reviews(review_store_path(output_dir))
    copy_labels = copy_labels or {}
    rows: list[InterpretationReviewItem] = []
    for index, copy_result in enumerate(result.results, 1):
        for trace in copy_result.interpretation_review_traces:
            if not trace.requires_human_review:
                continue
            current = latest_interpretation_review(
                history, copy_id=trace.copy_id, copy_sha256=trace.copy_sha256,
                expectation_id=trace.expectation_id, cell_id=trace.cell_id,
            )
            stale = current is None and any(
                old.copy_id == trace.copy_id
                and old.expectation_id == trace.expectation_id
                and old.cell_id == trace.cell_id
                and old.copy_sha256 != trace.copy_sha256
                and old.teacher_decision is not None
                for old in history
            )
            if only_pending and current is not None:
                continue
            rows.append(InterpretationReviewItem(
                trace, copy_labels.get(copy_result.source_id, f"Copie {index}"), current, stale,
            ))
    return tuple(rows)


def review_prefill(item: InterpretationReviewItem) -> tuple[InterpretationClassification, str]:
    if item.current_review is not None:
        return item.current_review.teacher_decision, item.current_review.teacher_feedback or ""
    decision = item.trace.tpstudio_proposal or InterpretationClassification.AMBIGUOUS
    return decision, item.trace.tpstudio_feedback or ""
