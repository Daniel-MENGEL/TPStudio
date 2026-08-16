"""Teacher-facing projection of graph and regression analyses.

This module deliberately contains presentation wording only.  It does not
perform matching, fitting, or numerical analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tpstudio.graph_analysis import GraphAnalysisTechnicalStatus, GraphScientificClassification
from tpstudio.orchestration import CopyAnalysisResult
from tpstudio.regression_matching import RegressionSeriesMatchStatus
from tpstudio.regression_plot_consistency import (
    RegressionPlotComparisonSource,
    RegressionPlotConsistencyStatus,
)
from tpstudio.regression_model import RegressionModelTechnicalStatus
from tpstudio.regression import RegressionMethod


class TeacherGraphHeadlineStatus(str, Enum):
    OK = "ok"
    REVIEW = "review"
    PROBLEM = "problem"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class GraphTeacherSummary:
    regression_id: str
    measured_series_id: str | None
    plotted_series_id: str | None
    method: str | None
    degree: int | None
    model_kind: str
    graph_geometry_status: GraphScientificClassification | GraphAnalysisTechnicalStatus | None
    regression_match_status: RegressionSeriesMatchStatus | None
    plot_consistency_status: RegressionPlotConsistencyStatus
    comparison_source: RegressionPlotComparisonSource
    headline_status: TeacherGraphHeadlineStatus
    headline_text: str
    summary_lines: tuple[str, ...]
    technical_details: tuple[str, ...]
    requires_human_review: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary_lines", tuple(self.summary_lines))
        object.__setattr__(self, "technical_details", tuple(self.technical_details))
        if not self.regression_id.strip() or not self.headline_text.strip():
            raise ValueError("Une synthèse graphique doit avoir une identité et un titre.")


def _model_kind(method: RegressionMethod | None, degree: int | None) -> str:
    if degree == 2:
        return "quadratique"
    if degree == 1 or method is RegressionMethod.SCIPY_LINREGRESS:
        return "affine"
    return "régression"


def _geometry_text(status: GraphScientificClassification | GraphAnalysisTechnicalStatus | None) -> str | None:
    return {
        GraphScientificClassification.LINEAR_COMPATIBLE: "Les points sont compatibles avec un alignement.",
        GraphScientificClassification.CLEARLY_NONLINEAR: "Les points présentent une courbure nette.",
        GraphScientificClassification.INCONCLUSIVE: "La géométrie du nuage demande une vérification.",
        GraphAnalysisTechnicalStatus.NOT_EVALUABLE: "La géométrie du nuage n'est pas évaluable automatiquement.",
    }.get(status)


def _source_text(source: RegressionPlotComparisonSource) -> str | None:
    return {
        RegressionPlotComparisonSource.EXTRACTED_PLOT_VALUES:
            "Comparaison sur les valeurs de courbe directement extraites.",
        RegressionPlotComparisonSource.RECONSTRUCTED_STRUCTURAL_PLOT:
            "Cohérence vérifiée par structure du code et reconstruction déterministe.",
        RegressionPlotComparisonSource.NONE: None,
    }[source]


def _match_text(status: RegressionSeriesMatchStatus | None) -> str | None:
    return {
        RegressionSeriesMatchStatus.EXACT: "Les données de la régression correspondent à la série expérimentale.",
        RegressionSeriesMatchStatus.NUMERIC_EQUIVALENT: "Les données de la régression sont numériquement équivalentes à la série expérimentale.",
        RegressionSeriesMatchStatus.REVERSED: "Les axes utilisés par la régression sont inversés par rapport à la série.",
        RegressionSeriesMatchStatus.AMBIGUOUS: "Plusieurs séries peuvent correspondre à cette régression.",
        RegressionSeriesMatchStatus.UNMATCHED: "Aucune série expérimentale compatible n'a été identifiée.",
        RegressionSeriesMatchStatus.NOT_EVALUABLE: "L'association avec une série expérimentale n'est pas évaluable automatiquement.",
        None: None,
    }[status]


def _status_for(
    match: RegressionSeriesMatchStatus | None,
    consistency: RegressionPlotConsistencyStatus,
    model_status: RegressionModelTechnicalStatus | None,
) -> TeacherGraphHeadlineStatus:
    if consistency is RegressionPlotConsistencyStatus.PLOTTED_MODEL_MISMATCH:
        return TeacherGraphHeadlineStatus.PROBLEM
    if match is RegressionSeriesMatchStatus.REVERSED:
        return TeacherGraphHeadlineStatus.PROBLEM
    if match in {
        RegressionSeriesMatchStatus.AMBIGUOUS,
        RegressionSeriesMatchStatus.NOT_EVALUABLE,
        RegressionSeriesMatchStatus.UNMATCHED,
    }:
        return TeacherGraphHeadlineStatus.REVIEW
    if model_status not in (None, RegressionModelTechnicalStatus.EVALUABLE):
        return TeacherGraphHeadlineStatus.REVIEW
    if consistency in {
        RegressionPlotConsistencyStatus.AMBIGUOUS,
        RegressionPlotConsistencyStatus.NOT_EVALUABLE,
    }:
        return TeacherGraphHeadlineStatus.REVIEW
    if consistency is RegressionPlotConsistencyStatus.UNMATCHED:
        return TeacherGraphHeadlineStatus.INFO
    if consistency in {
        RegressionPlotConsistencyStatus.CONSISTENT,
        RegressionPlotConsistencyStatus.NUMERICALLY_EQUIVALENT,
    }:
        return TeacherGraphHeadlineStatus.OK
    return TeacherGraphHeadlineStatus.INFO


def _headline(kind: str, status: TeacherGraphHeadlineStatus, consistency: RegressionPlotConsistencyStatus) -> str:
    if status is TeacherGraphHeadlineStatus.PROBLEM:
        return f"Ajustement {kind} — courbe incohérente"
    if consistency is RegressionPlotConsistencyStatus.CONSISTENT:
        return f"Ajustement {kind} cohérent"
    if consistency is RegressionPlotConsistencyStatus.NUMERICALLY_EQUIVALENT:
        return f"Ajustement {kind} numériquement équivalent"
    if consistency is RegressionPlotConsistencyStatus.UNMATCHED:
        return f"Régression {kind} détectée"
    if status is TeacherGraphHeadlineStatus.REVIEW:
        return f"Ajustement {kind} — comparaison à vérifier"
    return f"Régression {kind} détectée"


def _requires_review(
    match: RegressionSeriesMatchStatus | None,
    consistency: RegressionPlotConsistencyStatus,
    model_status: RegressionModelTechnicalStatus | None,
) -> bool:
    if match in {
        RegressionSeriesMatchStatus.AMBIGUOUS,
        RegressionSeriesMatchStatus.UNMATCHED,
        RegressionSeriesMatchStatus.NOT_EVALUABLE,
    }:
        return True
    if model_status not in (None, RegressionModelTechnicalStatus.EVALUABLE):
        return True
    return consistency in {
        RegressionPlotConsistencyStatus.AMBIGUOUS,
        RegressionPlotConsistencyStatus.NOT_EVALUABLE,
    }


def build_graph_teacher_summaries(result: CopyAnalysisResult) -> tuple[GraphTeacherSummary, ...]:
    """Project existing graph analyses without performing any new analysis."""
    if type(result) is not CopyAnalysisResult:
        raise TypeError("La projection graphique exige exactement un CopyAnalysisResult.")
    matches = {item.regression_id: item for item in result.regression_series_matches}
    models = {item.regression_id: item for item in result.regression_model_analyses}
    consistencies = {item.regression_id: item for item in result.regression_plot_consistency_analyses}
    geometries = {item.series_id: item for item in result.graph_analyses}
    summaries: list[GraphTeacherSummary] = []
    for regression in result.regression_observations:
        match = matches.get(regression.regression_id)
        model = models.get(regression.regression_id)
        consistency = consistencies.get(regression.regression_id)
        match_status = match.status if match else None
        consistency_status = consistency.consistency_status if consistency else RegressionPlotConsistencyStatus.NOT_EVALUABLE
        model_kind = _model_kind(regression.method, regression.degree)
        geometry = geometries.get(model.series_id) if model and model.series_id else None
        headline_status = _status_for(match_status, consistency_status, model.technical_status if model else None)
        lines = []
        for text in (_match_text(match_status),):
            if text:
                lines.append(text)
        if consistency_status is RegressionPlotConsistencyStatus.CONSISTENT:
            lines.append("La courbe tracée correspond au modèle reconstruit.")
        elif consistency_status is RegressionPlotConsistencyStatus.NUMERICALLY_EQUIVALENT:
            lines.append("La courbe tracée est numériquement équivalente au modèle reconstruit.")
        elif consistency_status is RegressionPlotConsistencyStatus.PLOTTED_MODEL_MISMATCH:
            lines.append("La courbe tracée ne correspond pas au modèle reconstruit.")
        elif consistency_status is RegressionPlotConsistencyStatus.AMBIGUOUS:
            lines.append("Plusieurs courbes candidates ont été identifiées.")
        elif consistency_status is RegressionPlotConsistencyStatus.UNMATCHED:
            lines.append("Aucune courbe de modèle distincte n'a été identifiée.")
        else:
            lines.append("La comparaison de la courbe n'est pas évaluable automatiquement.")
        geometry_status = None
        if geometry:
            geometry_status = geometry.scientific_classification or geometry.technical_status
        geometry_text = _geometry_text(geometry_status)
        if geometry_text:
            lines.append(geometry_text)
        details = [f"Méthode : {regression.method.value}"]
        if regression.degree is not None:
            details.append(f"Degré : {regression.degree}")
        if model:
            if model.coefficients is not None:
                details.append(f"Coefficients reconstruits : {model.coefficients}")
            if model.matrix_rank is not None:
                details.append(f"Rang de la matrice : {model.matrix_rank}")
            if model.condition_number is not None:
                details.append(f"Conditionnement : {model.condition_number}")
            details.extend(f"Diagnostic technique : {item}" for item in model.diagnostics)
        if consistency:
            details.append(f"Points comparés : {consistency.n_compared_points}")
            if consistency.rms_difference is not None:
                details.append(f"Écart RMS : {consistency.rms_difference}")
            if consistency.max_difference is not None:
                details.append(f"Écart maximal : {consistency.max_difference}")
            source_text = _source_text(consistency.comparison_source)
            if source_text:
                details.append(source_text)
            details.extend(f"Diagnostic de comparaison : {item}" for item in consistency.diagnostics)
        summaries.append(GraphTeacherSummary(
            regression.regression_id,
            model.series_id if model else (match.matched_series_id if match else None),
            consistency.plotted_series_id if consistency else None,
            regression.method.value, regression.degree, model_kind,
            geometry_status,
            match_status, consistency_status,
            consistency.comparison_source if consistency else RegressionPlotComparisonSource.NONE,
            headline_status, _headline(model_kind, headline_status, consistency_status),
            tuple(lines), tuple(details),
            _requires_review(match_status, consistency_status, model.technical_status if model else None),
        ))
    return tuple(summaries)
