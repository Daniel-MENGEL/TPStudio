"""Immutable teacher-facing projection of one copy analysis."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from tpstudio.feedback import FeedbackAudience
from tpstudio.orchestration import CopyAnalysisResult, ProductionResolutionStatus

from .priorities import (
    TeacherReportCategory,
    TeacherReportPriority,
    TeacherReportSeverity,
    order_teacher_report_priorities,
)
from .graph_teacher_summary import GraphTeacherSummary, build_graph_teacher_summaries


def _value(value: object) -> str:
    return getattr(value, "value", str(value))


def _reason_values(values: object) -> tuple[str, ...]:
    return tuple(_value(item) for item in (values or ()))


@dataclass(frozen=True, slots=True)
class TeacherReportOverview:
    project_id: str
    source_id: str
    notebook_valid: bool
    cell_count: int
    resolved_productions: int
    missing_productions: int
    ambiguous_productions: int
    technical_error_count: int
    placeholder_count: int
    unexecuted_code_count: int
    evaluable_quantity_count: int
    non_evaluable_quantity_count: int
    graph_issue_count: int
    comparison_issue_count: int
    normalized_error_issue_count: int
    interpretation_issue_count: int
    justification_issue_count: int
    diagnostic_count: int
    teacher_feedback_count: int
    student_feedback_count: int
    limitation_count: int
    priority_count: int
    requires_human_review: bool


@dataclass(frozen=True, slots=True)
class TeacherTechnicalReport:
    notebook_valid: bool
    nbformat_version: str
    cell_count: int
    markdown_cell_count: int
    code_cell_count: int
    raw_cell_count: int
    executed_code_cell_count: int
    unexecuted_code_cell_indices: tuple[int, ...]
    error_output_cell_indices: tuple[int, ...]
    placeholder_cell_indices: tuple[int, ...]
    empty_code_cell_indices: tuple[int, ...]
    stored_output_cell_indices: tuple[int, ...]
    kernel_name: str | None
    has_attachments: bool
    external_path_reference_count: int


@dataclass(frozen=True, slots=True)
class TeacherProductionReport:
    production_id: str
    title: str
    kind: str
    required: bool
    status: str
    cell_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class TeacherValueReport:
    production_id: str
    status: str
    value: Decimal | None
    unit: str | None
    source: str | None
    cell_index: int | None
    evidence_count: int
    raw_evidence: str | None
    saved_output_may_be_stale: bool


@dataclass(frozen=True, slots=True)
class TeacherQuantityReport:
    production_id: str
    status: str
    evaluable: bool
    value: Decimal | None
    unit: str | None
    uncertainty: Decimal | None
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TeacherRelationReport:
    relation_id: str
    status: str
    cell_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class TeacherGraphReport:
    production_id: str
    cell_index: int | None
    figure_output_present: bool
    x_expression: str | None
    y_expression: str | None
    x_label: str | None
    y_label: str | None
    regression_present: bool
    regression_x_expression: str | None
    regression_y_expression: str | None
    slope_target: str | None
    orientation_status: str
    label_status: str
    regression_status: str
    slope_relation_status: str
    evaluable: bool
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TeacherComparisonReport:
    comparison_id: str
    left_quantity_id: str
    right_quantity_id: str
    objective_status: str
    normalized_error: Decimal | None
    objective_reasons: tuple[str, ...]
    student_error_status: str | None
    student_error_value: Decimal | None
    student_error_reasons: tuple[str, ...]
    interpretation_status: str | None
    interpretation_excerpt: str | None
    interpretation_reasons: tuple[str, ...]
    justification_status: str | None
    observed_justification_elements: tuple[str, ...]
    missing_required_elements: tuple[str, ...]
    satisfied_alternative_groups: tuple[str, ...]
    missing_alternative_groups: tuple[str, ...]
    justification_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TeacherFinalConclusionReport:
    production_id: str
    status: str
    cell_indices: tuple[int, ...]
    has_text: bool
    excerpt: str | None


@dataclass(frozen=True, slots=True)
class TeacherDiagnosticReportItem:
    diagnostic_id: str
    source_key: str
    category: TeacherReportCategory
    severity: TeacherReportSeverity
    production_id: str | None
    comparison_id: str | None
    code: str
    message_key: str


@dataclass(frozen=True, slots=True)
class TeacherFeedbackReportItem:
    feedback_id: str
    source_key: str
    audience: FeedbackAudience
    production_id: str | None
    comparison_id: str | None
    priority: str
    text: str
    cell_index: int | None = None
    cell_type: str | None = None


@dataclass(frozen=True, slots=True)
class TeacherHumanReviewReport:
    required: bool
    reasons: tuple[str, ...]
    categories: tuple[TeacherReportCategory, ...]


@dataclass(frozen=True, slots=True)
class TeacherCopyReport:
    project_id: str
    source_id: str
    title: str
    overview: TeacherReportOverview
    priorities: tuple[TeacherReportPriority, ...]
    technical: TeacherTechnicalReport
    productions: tuple[TeacherProductionReport, ...]
    values: tuple[TeacherValueReport, ...]
    quantities: tuple[TeacherQuantityReport, ...]
    relations: tuple[TeacherRelationReport, ...]
    graph: tuple[TeacherGraphReport, ...]
    comparisons: tuple[TeacherComparisonReport, ...]
    final_conclusion: TeacherFinalConclusionReport
    diagnostics: tuple[TeacherDiagnosticReportItem, ...]
    feedback: tuple[TeacherFeedbackReportItem, ...]
    limitations: tuple[str, ...]
    human_review: TeacherHumanReviewReport
    regression_graphs: tuple[GraphTeacherSummary, ...] = ()

    def __post_init__(self) -> None:
        if not self.project_id.strip() or not self.source_id.strip() or not self.title.strip():
            raise ValueError("L'identité du rapport ne peut pas être vide.")
        for name in ("priorities", "productions", "values", "quantities", "relations", "graph", "comparisons", "diagnostics", "feedback", "limitations", "regression_graphs"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        production_ids = {item.production_id for item in self.productions}
        if any(item.production_id not in production_ids for item in self.values):
            raise ValueError("Une valeur vise une production étrangère.")


def _diagnostic_category(item: object) -> TeacherReportCategory:
    name = type(item).__name__.lower()
    if "protocol" in name:
        return TeacherReportCategory.PROTOCOL
    if "conclusion" in name:
        return TeacherReportCategory.CONCLUSION
    if "interpretation" in name:
        return TeacherReportCategory.INTERPRETATION
    if "justification" in name:
        return TeacherReportCategory.JUSTIFICATION
    if "comparison" in name:
        return TeacherReportCategory.COMPARISON
    return TeacherReportCategory.QUANTITY


def _identity_value(value: object | None) -> str:
    if value is None:
        return "-"
    return str(getattr(value, "value", value))


def feedback_source_key(item: object) -> str:
    """Return the stable business identity of one rendered feedback."""

    return ":".join((
        "feedback", type(item).__name__,
        _identity_value(getattr(item, "code", None)),
        _identity_value(getattr(item, "audience", None)),
        _identity_value(getattr(item, "production_id", None)),
        _identity_value(getattr(item, "comparison_id", None)),
        _identity_value(getattr(item, "expectation_id", None)),
        _identity_value(getattr(item, "variant", None)),
    ))


def diagnostic_source_key(item: object) -> str:
    """Return the stable business identity of one diagnostic."""

    return ":".join((
        "diagnostic", type(item).__name__,
        _identity_value(getattr(item, "code", None)),
        _identity_value(getattr(item, "message_key", None)),
        _identity_value(getattr(item, "production_id", None)),
        _identity_value(getattr(item, "comparison_id", None)),
        _identity_value(getattr(item, "expectation_id", None)),
        _identity_value(getattr(item, "source", None)),
    ))


def _diagnostic_severity(item: object) -> TeacherReportSeverity:
    text = f"{_value(getattr(item, 'code', ''))} {_value(getattr(item, 'status', ''))}".lower()
    if "not_evaluable" in text:
        return TeacherReportSeverity.BLOCKING
    if any(word in text for word in ("contradict", "missing", "strongly")):
        return TeacherReportSeverity.IMPORTANT
    return TeacherReportSeverity.ATTENTION


def _short(text: str | None, limit: int = 120) -> str | None:
    if text is None:
        return None
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _build_priorities(result: CopyAnalysisResult, diagnostics, feedback):
    priorities: list[TeacherReportPriority] = []
    def add(severity, category, title, message, production_id=None, comparison_id=None, cells=(), diagnostic_ids=(), feedback_ids=()):
        priorities.append(TeacherReportPriority(
            f"priority-{len(priorities)+1:03d}", severity, category, title, message,
            production_id, comparison_id, tuple(cells), tuple(diagnostic_ids), tuple(feedback_ids), True,
        ))
    tech = result.technical_inspection
    for index in tech.error_output_cell_indices:
        add(TeacherReportSeverity.BLOCKING, TeacherReportCategory.TECHNICAL, "Erreur enregistrée", "Une sortie d'erreur est enregistrée ; TPStudio n'a pas réexécuté la cellule.", cells=(index,))
    for index in tech.question_mark_code_cell_indices:
        add(TeacherReportSeverity.IMPORTANT, TeacherReportCategory.TECHNICAL, "Code à compléter", "Un marqueur ? subsiste dans une cellule de code.", cells=(index,))
    for index in tech.unexecuted_code_cell_indices:
        add(TeacherReportSeverity.ATTENTION, TeacherReportCategory.TECHNICAL, "Cellule non exécutée", "La cellule ne possède pas d'exécution enregistrée.", cells=(index,))
    for item in result.production_resolutions:
        production = result.project.get_production(item.production_id)
        if item.status is ProductionResolutionStatus.MISSING and production and production.required:
            add(TeacherReportSeverity.IMPORTANT, TeacherReportCategory.PRODUCTION, "Production absente", "La production obligatoire n'a pas été résolue.", item.production_id)
        elif item.status is ProductionResolutionStatus.AMBIGUOUS:
            add(TeacherReportSeverity.BLOCKING, TeacherReportCategory.PRODUCTION, "Production ambiguë", "Plusieurs sources possibles empêchent une sélection déterministe.", item.production_id)
    for item in result.observed_value_detections:
        if item.ambiguous:
            add(TeacherReportSeverity.BLOCKING, TeacherReportCategory.QUANTITY, "Valeur ambiguë", "Plusieurs valeurs–unités incompatibles ont été observées.", item.production.id)
        elif item.saved_output_may_be_stale:
            add(TeacherReportSeverity.ATTENTION, TeacherReportCategory.QUANTITY, "Output potentiellement obsolète", "La provenance enregistrée peut ne pas correspondre au code courant.", item.production.id)
    for item in result.graph_evaluations:
        if item.has_issues:
            add(TeacherReportSeverity.IMPORTANT, TeacherReportCategory.GRAPH, "Graphe à examiner", "L'analyse structurelle du graphe signale une incohérence ou une limite.", item.expectation.production_id, cells=((item.observation.cell_index,) if item.observation else ()))
    for diag in diagnostics:
        add(diag.severity, diag.category, "Diagnostic", diag.message_key, diag.production_id, diag.comparison_id, diagnostic_ids=(diag.diagnostic_id,))
    for limitation in result.limitations:
        add(TeacherReportSeverity.ATTENTION, TeacherReportCategory.LIMITATION, "Limite de l'analyse", limitation)
    order = tuple(item.id for item in result.project.scientific_production_plan.evaluation_order)
    return order_teacher_report_priorities(tuple(priorities), order)


def build_teacher_copy_report(result: CopyAnalysisResult) -> TeacherCopyReport:
    """Project an A71c result into an immutable teacher report."""

    if type(result) is not CopyAnalysisResult:
        raise TypeError("Le reporting exige exactement un CopyAnalysisResult.")
    technical_source = result.technical_inspection
    technical = TeacherTechnicalReport(
        technical_source.notebook_valid, technical_source.nbformat_version,
        technical_source.cell_count, technical_source.markdown_cell_count,
        technical_source.code_cell_count, technical_source.raw_cell_count,
        technical_source.executed_code_cell_count,
        technical_source.unexecuted_code_cell_indices,
        technical_source.error_output_cell_indices,
        technical_source.question_mark_code_cell_indices,
        technical_source.empty_code_cell_indices,
        technical_source.stored_output_cell_indices, technical_source.kernel_name,
        technical_source.has_attachments,
        len(technical_source.referenced_external_paths),
    )
    productions = tuple(TeacherProductionReport(
        item.production_id,
        result.project.get_production(item.production_id).label,
        result.project.get_production(item.production_id).kind.value,
        result.project.get_production(item.production_id).required,
        item.status.value,
        (item.cell_index,) if item.cell_index is not None else (),
    ) for item in result.production_resolutions)
    values = tuple(TeacherValueReport(
        item.production.id,
        "unique" if item.unique else "ambiguous" if item.ambiguous else "absent",
        item.selected.value if item.selected else None,
        item.selected.unit if item.selected else None,
        item.selected.source.value if item.selected else None,
        item.selected.cell_index if item.selected else None,
        len(item.candidates), _short(item.selected.raw_text) if item.selected else None,
        item.saved_output_may_be_stale,
    ) for item in result.observed_value_detections)
    quantities = []
    for item in result.quantity_evaluations:
        observation = item.assessment.selected_observation if item.assessment else None
        reasons = tuple(_value(diag.code) for diag in item.diagnostics)
        evaluable = bool(
            item.assessed
            and item.assessment is not None
            and item.assessment.is_structurally_satisfied
        )
        quantities.append(TeacherQuantityReport(
            item.production_id, item.status.value, evaluable,
            observation.value if observation else None,
            observation.unit if observation else None,
            observation.uncertainty if observation else None,
            reasons,
        ))
    relations = tuple(TeacherRelationReport(
        item.relation_id, item.status.value,
        (item.resolution.cell.index,) if item.resolution and item.resolution.cell else (),
    ) for item in result.relation_evaluations)
    graphs = tuple(TeacherGraphReport(
        item.expectation.production_id,
        item.observation.cell_index if item.observation else None,
        item.observation.figure_output_present if item.observation else False,
        item.observation.x_expression if item.observation else None,
        item.observation.y_expression if item.observation else None,
        item.observation.x_label if item.observation else None,
        item.observation.y_label if item.observation else None,
        item.observation.regression_present if item.observation else False,
        item.observation.regression_x_expression if item.observation else None,
        item.observation.regression_y_expression if item.observation else None,
        item.observation.slope_target if item.observation else None,
        item.orientation_status.value, item.label_status.value,
        item.regression_status.value, item.slope_relation_status.value,
        item.evaluable, tuple(item.reasons) + (item.observation.analysis_limitations if item.observation else ()),
    ) for item in result.graph_evaluations)
    student_by_id = {item.comparison_id: item for item in result.student_normalized_error_evaluations}
    interpretation_by_id = {item.comparison_id: item for item in result.comparison_interpretation_evaluations}
    justification_by_id = {item.comparison_id: item for item in result.comparison_justification_evaluations}
    comparisons = []
    for item in result.quantity_comparison_evaluations:
        student = student_by_id.get(item.production_id)
        interpretation = interpretation_by_id.get(item.production_id)
        justification = justification_by_id.get(item.production_id)
        comparisons.append(TeacherComparisonReport(
            item.production_id, item.left_quantity_id, item.right_quantity_id,
            item.status.value, item.normalized_error, _reason_values(item.not_evaluable_reasons),
            student.status.value if student else None,
            student.student_observation.value if student and student.student_observation else None,
            _reason_values(student.not_evaluable_reasons) if student else (),
            interpretation.status.value if interpretation else None,
            _short(interpretation.observation.phrase) if interpretation and interpretation.observation else None,
            _reason_values(interpretation.not_evaluable_reasons) if interpretation else (),
            justification.status.value if justification else None,
            justification.observed_element_ids if justification else (),
            justification.missing_required_element_ids if justification else (),
            justification.satisfied_alternative_groups if justification else (),
            justification.missing_alternative_groups if justification else (),
            _reason_values(justification.not_evaluable_reasons) if justification else (),
        ))
    diagnostics = tuple(TeacherDiagnosticReportItem(
        f"diagnostic-{index:03d}", diagnostic_source_key(item),
        _diagnostic_category(item), _diagnostic_severity(item),
        getattr(item, "production_id", None), getattr(item, "comparison_id", None),
        _value(getattr(item, "code", type(item).__name__)),
        getattr(item, "message_key", _value(getattr(item, "code", type(item).__name__))),
    ) for index, item in enumerate(result.diagnostics, 1))
    feedback = tuple(TeacherFeedbackReportItem(
        f"feedback-{index:03d}", feedback_source_key(item), item.audience,
        getattr(item, "production_id", None), getattr(item, "comparison_id", None),
        _value(getattr(item, "priority", "normal")), item.text,
        getattr(item, "cell_index", None), getattr(item, "cell_type", None),
    ) for index, item in enumerate(result.feedback, 1))
    priorities = _build_priorities(result, diagnostics, feedback)
    conclusion = result.final_conclusion
    final = TeacherFinalConclusionReport(
        conclusion.production_id,
        "unique" if conclusion.unique else "ambiguous" if conclusion.ambiguous else "absent",
        tuple(item.cell.index for item in conclusion.candidates if item.cell is not None),
        bool(conclusion.text and conclusion.text.strip()), _short(conclusion.text),
    )
    review_reasons = tuple(dict.fromkeys(item.title for item in priorities if item.requires_human_review))
    review_categories = tuple(dict.fromkeys(item.category for item in priorities if item.requires_human_review))
    human = TeacherHumanReviewReport(result.requires_human_review, review_reasons, review_categories)
    regression_graphs = build_graph_teacher_summaries(result)
    teacher_count = sum(item.audience is FeedbackAudience.TEACHER for item in feedback)
    student_count = sum(item.audience is FeedbackAudience.STUDENT for item in feedback)
    evaluable_quantities = sum(item.evaluable for item in quantities)
    overview = TeacherReportOverview(
        result.project_id, result.source_id, technical.notebook_valid, technical.cell_count,
        len(result.production_resolutions.resolved), len(result.production_resolutions.missing),
        len(result.production_resolutions.ambiguous), len(technical.error_output_cell_indices),
        len(technical.placeholder_cell_indices), len(technical.unexecuted_code_cell_indices),
        evaluable_quantities, len(quantities) - evaluable_quantities,
        sum(item.has_issues for item in result.graph_evaluations),
        sum(not item.coherent for item in result.quantity_comparison_evaluations),
        sum(_value(item.status) != "matches_reference" for item in result.student_normalized_error_evaluations),
        sum(_value(item.status) != "matches_objective_classification" for item in result.comparison_interpretation_evaluations),
        sum(_value(item.status) != "complete" for item in result.comparison_justification_evaluations),
        len(diagnostics), teacher_count, student_count, len(result.limitations), len(priorities),
        result.requires_human_review,
    )
    return TeacherCopyReport(
        result.project_id, result.source_id, result.project.identity.title, overview,
        priorities, technical, productions, values, tuple(quantities), relations, graphs,
        tuple(comparisons), final, diagnostics, feedback, tuple(result.limitations), human,
        regression_graphs,
    )
