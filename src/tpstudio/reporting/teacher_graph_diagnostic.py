"""Prudent teacher-facing motifs derived from existing graph facts.

This module only projects already computed analyses.  It does not fit, match,
recompute residuals, or impose corpus-specific thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tpstudio.graph_analysis import GraphScientificClassification
from tpstudio.orchestration import CopyAnalysisResult
from tpstudio.regression_model import RegressionModelTechnicalStatus
from tpstudio.regression_plot_consistency import (
    RegressionPlotConsistencyStatus,
)
from .graph_teacher_summary import (
    GraphTeacherSummary,
    TeacherGraphHeadlineStatus,
    build_graph_teacher_summaries,
)


class TeacherGraphDiagnosticReason(str, Enum):
    ALIGNMENT_COMPATIBLE = "alignment_compatible"
    ALIGNMENT_INCONCLUSIVE = "alignment_inconclusive"
    ALIGNMENT_NONLINEAR = "alignment_nonlinear"
    INFLUENTIAL_POINT_REVIEW = "influential_point_review"
    POSSIBLE_CURVATURE = "possible_curvature"
    MODEL_NOT_EVALUABLE = "model_not_evaluable"
    PLOT_COHERENT = "plot_coherent"
    PLOT_NOT_IDENTIFIED = "plot_not_identified"
    PLOT_REVIEW = "plot_review"
    PLOT_MISMATCH = "plot_mismatch"


@dataclass(frozen=True, slots=True)
class TeacherGraphDiagnostic:
    regression_id: str
    headline_status: TeacherGraphHeadlineStatus
    headline_text: str
    motifs: tuple[TeacherGraphDiagnosticReason, ...]
    summary_lines: tuple[str, ...]
    technical_details: tuple[str, ...]
    requires_human_review: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "motifs", tuple(self.motifs))
        object.__setattr__(self, "summary_lines", tuple(self.summary_lines))
        object.__setattr__(self, "technical_details", tuple(self.technical_details))


_MOTIF_TEXT = {
    TeacherGraphDiagnosticReason.ALIGNMENT_COMPATIBLE:
        "Les points sont compatibles avec une droite.",
    TeacherGraphDiagnosticReason.ALIGNMENT_INCONCLUSIVE:
        "L'alignement des points mérite une vérification visuelle.",
    TeacherGraphDiagnosticReason.ALIGNMENT_NONLINEAR:
        "Les écarts observés ne permettent pas de valider clairement un alignement sur une droite.",
    TeacherGraphDiagnosticReason.INFLUENTIAL_POINT_REVIEW:
        "La conclusion géométrique dépend sensiblement d'un point.",
    TeacherGraphDiagnosticReason.POSSIBLE_CURVATURE:
        "Une courbure possible apparaît dans le nuage de points.",
    TeacherGraphDiagnosticReason.MODEL_NOT_EVALUABLE:
        "Le modèle de régression n'a pas pu être évalué de manière fiable.",
    TeacherGraphDiagnosticReason.PLOT_COHERENT:
        "La courbe tracée correspond au modèle reconstruit.",
    TeacherGraphDiagnosticReason.PLOT_NOT_IDENTIFIED:
        "Aucune courbe de modèle distincte n'a été identifiée.",
    TeacherGraphDiagnosticReason.PLOT_REVIEW:
        "La comparaison de la courbe mérite une vérification.",
    TeacherGraphDiagnosticReason.PLOT_MISMATCH:
        "La courbe tracée ne correspond pas au modèle reconstruit.",
}


def _geometry_motifs(geometry) -> list[TeacherGraphDiagnosticReason]:
    if geometry is None:
        return []
    motifs: list[TeacherGraphDiagnosticReason] = []
    if geometry.scientific_classification is GraphScientificClassification.LINEAR_COMPATIBLE:
        motifs.append(TeacherGraphDiagnosticReason.ALIGNMENT_COMPATIBLE)
    elif geometry.scientific_classification is GraphScientificClassification.INCONCLUSIVE:
        motifs.append(TeacherGraphDiagnosticReason.ALIGNMENT_INCONCLUSIVE)
    elif geometry.scientific_classification is GraphScientificClassification.CLEARLY_NONLINEAR:
        motifs.append(TeacherGraphDiagnosticReason.ALIGNMENT_NONLINEAR)
    if geometry.curvature_indicator == "possible":
        motifs.append(TeacherGraphDiagnosticReason.POSSIBLE_CURVATURE)
    if any("point" in diagnostic for diagnostic in geometry.diagnostics):
        motifs.append(TeacherGraphDiagnosticReason.INFLUENTIAL_POINT_REVIEW)
    return motifs


def _plot_motif(status: RegressionPlotConsistencyStatus) -> TeacherGraphDiagnosticReason:
    if status in {
        RegressionPlotConsistencyStatus.CONSISTENT,
        RegressionPlotConsistencyStatus.NUMERICALLY_EQUIVALENT,
    }:
        return TeacherGraphDiagnosticReason.PLOT_COHERENT
    if status is RegressionPlotConsistencyStatus.PLOTTED_MODEL_MISMATCH:
        return TeacherGraphDiagnosticReason.PLOT_MISMATCH
    if status in {
        RegressionPlotConsistencyStatus.AMBIGUOUS,
        RegressionPlotConsistencyStatus.NOT_EVALUABLE,
    }:
        return TeacherGraphDiagnosticReason.PLOT_REVIEW
    return TeacherGraphDiagnosticReason.PLOT_NOT_IDENTIFIED


def _technical_geometry_details(geometry) -> tuple[str, ...]:
    if geometry is None:
        return ()
    details: list[str] = []
    if geometry.residual_rms is not None:
        details.append(f"RMS des résidus affines : {geometry.residual_rms}")
    if geometry.max_abs_residual is not None:
        details.append(f"Écart affine maximal : {geometry.max_abs_residual}")
    if geometry.residual_range_normalized is not None:
        details.append(f"Étendue normalisée des résidus : {geometry.residual_range_normalized}")
    if geometry.max_leave_one_out_effect is not None:
        details.append(f"Influence maximale : {geometry.max_leave_one_out_effect}")
    residuals = geometry.residual_diagnostics
    if residuals is not None:
        if residuals.constrained_residual_rms is not None:
            details.append(f"RMS autour de y=a*x : {residuals.constrained_residual_rms}")
        if residuals.constrained_mean_signed_residual_normalized is not None:
            details.append(
                "Moyenne signée normalisée autour de y=a*x : "
                f"{residuals.constrained_mean_signed_residual_normalized}"
            )
        if residuals.constrained_sign_imbalance is not None:
            details.append(f"Déséquilibre des signes : {residuals.constrained_sign_imbalance}")
    return tuple(details)


def _headline(
    summary: GraphTeacherSummary,
    motifs: tuple[TeacherGraphDiagnosticReason, ...],
) -> tuple[TeacherGraphHeadlineStatus, str, bool]:
    if TeacherGraphDiagnosticReason.PLOT_MISMATCH in motifs:
        return TeacherGraphHeadlineStatus.PROBLEM, summary.headline_text, summary.requires_human_review
    if TeacherGraphDiagnosticReason.ALIGNMENT_NONLINEAR in motifs:
        return TeacherGraphHeadlineStatus.PROBLEM, summary.headline_text, True
    if (
        TeacherGraphDiagnosticReason.ALIGNMENT_INCONCLUSIVE in motifs
        or TeacherGraphDiagnosticReason.INFLUENTIAL_POINT_REVIEW in motifs
        or TeacherGraphDiagnosticReason.POSSIBLE_CURVATURE in motifs
        or TeacherGraphDiagnosticReason.MODEL_NOT_EVALUABLE in motifs
        or TeacherGraphDiagnosticReason.PLOT_REVIEW in motifs
    ):
        return TeacherGraphHeadlineStatus.REVIEW, summary.headline_text, True
    if (
        summary.headline_status is TeacherGraphHeadlineStatus.INFO
        and TeacherGraphDiagnosticReason.ALIGNMENT_COMPATIBLE in motifs
    ):
        # A missing plotted curve is informational only when the geometry is
        # itself compatible; keep the scientific headline positive.
        return TeacherGraphHeadlineStatus.OK, summary.headline_text, False
    return summary.headline_status, summary.headline_text, summary.requires_human_review


def build_teacher_graph_diagnostics(
    result: CopyAnalysisResult,
    *,
    expected_model: str | None = None,
) -> tuple[TeacherGraphDiagnostic, ...]:
    """Build cautious teacher motifs from existing scientific projections.

    ``expected_model`` is intentionally reserved for a future expectation
    contract.  Until one is supplied by the project, no constrained-origin
    offset motif is inferred from residuals alone.
    """

    if type(result) is not CopyAnalysisResult:
        raise TypeError("Le diagnostic graphique exige exactement un CopyAnalysisResult.")
    summaries = build_graph_teacher_summaries(result)
    geometries = {item.series_id: item for item in result.all_graph_analyses}
    models = {item.regression_id: item for item in result.regression_model_analyses}
    diagnostics: list[TeacherGraphDiagnostic] = []
    for summary in summaries:
        model = models.get(summary.regression_id)
        geometry = geometries.get(model.series_id) if model and model.series_id else None
        motifs = _geometry_motifs(geometry)
        if model is None or model.technical_status is not RegressionModelTechnicalStatus.EVALUABLE:
            motifs.append(TeacherGraphDiagnosticReason.MODEL_NOT_EVALUABLE)
        consistency = summary.plot_consistency_status
        motifs.append(_plot_motif(consistency))
        # expected_model is deliberately not interpreted yet.  In particular,
        # residual bias around y=a*x is never treated as a generic error.
        unique_motifs = tuple(dict.fromkeys(motifs))
        status, headline, requires_review = _headline(summary, unique_motifs)
        lines = list(summary.summary_lines)
        for motif in unique_motifs:
            text = _MOTIF_TEXT[motif]
            if text not in lines:
                lines.append(text)
        details = list(summary.technical_details)
        for detail in _technical_geometry_details(geometry):
            if detail not in details:
                details.append(detail)
        diagnostics.append(TeacherGraphDiagnostic(
            summary.regression_id, status, headline, unique_motifs,
            tuple(lines), tuple(details), requires_review,
        ))
    return tuple(diagnostics)
