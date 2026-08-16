"""End-to-end, read-only orchestration of one Snell-Descartes copy."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from tpstudio.assessment import (
    NotebookQuantityAssessmentItem,
    NotebookQuantityAssessmentSet,
    NotebookQuantityAssessmentStatus,
    assess_quantity_text,
)
from tpstudio.diagnostics import (
    build_comparison_interpretation_diagnostics,
    build_comparison_justification_diagnostics,
    build_quantity_comparison_diagnostics,
)
from tpstudio.evaluation import (
    ComparisonInterpretationEvaluationStatus,
    ComparisonJustificationEvaluationStatus,
    QuantityComparisonEvaluationStatus,
    evaluate_comparison_interpretations,
    evaluate_comparison_justifications,
    evaluate_quantity_comparisons,
    evaluate_student_normalized_errors,
)
from tpstudio.expectations import ScientificProductionKind
from tpstudio.feedback import (
    ComparisonInterpretationFeedbackCatalog,
    ComparisonJustificationFeedbackCatalog,
    FeedbackAudience,
    QuantityComparisonFeedbackCatalog,
    QuantityFeedbackCatalog,
    render_comparison_interpretation_feedback,
    render_comparison_justification_feedback,
    render_quantity_comparison_feedback,
)
from tpstudio.notebooks import (
    NotebookBindingResolution,
    NotebookBindingResolutionSet,
    NotebookBindingResolutionStatus,
    resolve_notebook_bindings,
)
from tpstudio.projects import (
    TeacherProjectConfiguration,
    snells_laws_teacher_project,
    validate_teacher_project_configuration,
)
from tpstudio.protocol import (
    ProtocolDiagnostic,
    ProtocolEvaluation,
    ProtocolFeedbackItem,
    ProtocolStatus,
    evaluate_protocol_cells,
)
from tpstudio.conclusion import (
    ConclusionEvaluation,
    build_conclusion_diagnostics,
    build_conclusion_feedback,
    evaluate_conclusion_cells,
    build_conclusion_contexts,
)
from tpstudio.interpretation import (
    InterpretationFeedbackItem,
    InterpretationEvaluation,
    InterpretationReviewTrace,
    build_interpretation_contexts,
    build_interpretation_diagnostics,
    build_interpretation_feedback,
    build_interpretation_review_traces,
    evaluate_interpretation_cells,
)
from tpstudio.reasoning import extract_expected_quantity

from .graph_adapter import GraphEvaluation, GraphSeriesData, evaluate_saved_graph, observe_saved_graph, extract_all_graph_series_data
from tpstudio.graph_analysis import GraphAnalysis, analyze_graph_series_collection
from tpstudio.regression import RegressionObservation, extract_regression_observations
from tpstudio.regression_matching import RegressionSeriesMatch, match_regressions_to_series
from tpstudio.regression_model import RegressionModelAnalysis, analyze_regression_models
from tpstudio.regression_plot_matching import RegressionPlotMatch, match_regressions_to_plots
from tpstudio.regression_plot_consistency import (
    RegressionPlotConsistencyAnalysis,
    compare_regression_plots,
)
from .notebook_inspection import (
    NotebookCopySource,
    NotebookTechnicalInspection,
    inspect_notebook,
    load_notebook_copy,
)
from .observed_values import (
    ObservedValueDetection,
    ObservedValueSource,
    detect_observed_values,
)


@dataclass(frozen=True, slots=True)
class CopyAnalysisOptions:
    execute_notebook: bool = False
    inspect_saved_outputs: bool = True
    inspect_graphs: bool = True
    build_diagnostics: bool = True
    render_feedback: bool = True
    student_feedback: bool = True
    teacher_feedback: bool = True

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"L'option {name!r} doit être un booléen exact.")


class ProductionResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class CopyProductionResolution:
    resolution: NotebookBindingResolution

    @property
    def production_id(self) -> str:
        return self.resolution.production_id

    @property
    def cell_index(self) -> int | None:
        return self.resolution.cell.index if self.resolution.cell else None

    @property
    def status(self) -> ProductionResolutionStatus:
        if self.resolution.status in (
            NotebookBindingResolutionStatus.CELL_AMBIGUOUS,
            NotebookBindingResolutionStatus.TEXT_MARKER_AMBIGUOUS,
        ):
            return ProductionResolutionStatus.AMBIGUOUS
        if self.resolution.resolved:
            return ProductionResolutionStatus.RESOLVED
        return ProductionResolutionStatus.MISSING


@dataclass(frozen=True, slots=True)
class CopyProductionResolutionSet:
    resolution_set: NotebookBindingResolutionSet
    resolutions: tuple[CopyProductionResolution, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.resolution_set, NotebookBindingResolutionSet):
            raise TypeError("Le jeu de résolutions A69c est invalide.")
        values = tuple(self.resolutions)
        if len(values) != len(self.resolution_set):
            raise ValueError("Chaque binding exige une résolution de copie.")
        if any(item.resolution is not resolution for item, resolution in zip(values, self.resolution_set)):
            raise ValueError("Les résolutions doivent être réutilisées par identité.")
        object.__setattr__(self, "resolutions", values)

    def __iter__(self) -> Iterator[CopyProductionResolution]:
        return iter(self.resolutions)

    def __len__(self) -> int:
        return len(self.resolutions)

    def get(self, production_id: str) -> CopyProductionResolution | None:
        return next((item for item in self.resolutions if item.production_id == production_id), None)

    def for_cell(self, cell_index: int) -> tuple[CopyProductionResolution, ...]:
        return tuple(item for item in self.resolutions if item.cell_index == cell_index)

    @property
    def resolved(self):
        return tuple(item for item in self.resolutions if item.status is ProductionResolutionStatus.RESOLVED)

    @property
    def missing(self):
        return tuple(item for item in self.resolutions if item.status is ProductionResolutionStatus.MISSING)

    @property
    def ambiguous(self):
        return tuple(item for item in self.resolutions if item.status is ProductionResolutionStatus.AMBIGUOUS)

    @property
    def has_missing(self) -> bool:
        return bool(self.missing)

    @property
    def has_ambiguous(self) -> bool:
        return bool(self.ambiguous)


class RelationObservationStatus(str, Enum):
    OBSERVED = "observed"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class RelationEvaluation:
    relation_id: str
    status: RelationObservationStatus
    resolution: NotebookBindingResolution | None


@dataclass(frozen=True, slots=True)
class FinalConclusionObservation:
    production_id: str
    candidates: tuple[NotebookBindingResolution, ...]
    source_resolution: NotebookBindingResolution | None
    text: str | None

    @property
    def absent(self) -> bool:
        return not any(item.resolved for item in self.candidates) and not self.ambiguous

    @property
    def unique(self) -> bool:
        return self.source_resolution is not None

    @property
    def ambiguous(self) -> bool:
        resolved = sum(item.resolved for item in self.candidates)
        return resolved > 1 or any(
            item.status in (
                NotebookBindingResolutionStatus.CELL_AMBIGUOUS,
                NotebookBindingResolutionStatus.TEXT_MARKER_AMBIGUOUS,
            )
            for item in self.candidates
        )


@dataclass(frozen=True, slots=True)
class CopyAnalysisResult:
    project: TeacherProjectConfiguration
    source: NotebookCopySource
    options: CopyAnalysisOptions
    technical_inspection: NotebookTechnicalInspection
    production_resolutions: CopyProductionResolutionSet
    observed_value_detections: tuple[ObservedValueDetection, ...]
    quantity_evaluations: NotebookQuantityAssessmentSet
    uncertainty_evaluations: tuple[object, ...]
    relation_evaluations: tuple[RelationEvaluation, ...]
    graph_evaluations: tuple[GraphEvaluation, ...]
    quantity_comparison_evaluations: object
    student_normalized_error_evaluations: object
    comparison_interpretation_evaluations: object
    comparison_justification_evaluations: object
    diagnostics: tuple[object, ...]
    feedback: tuple[object, ...]
    final_conclusion: FinalConclusionObservation
    limitations: tuple[str, ...] = ()
    protocol_evaluations: tuple[ProtocolEvaluation, ...] = ()
    conclusion_evaluations: tuple[ConclusionEvaluation, ...] = ()
    interpretation_response_evaluations: tuple[InterpretationEvaluation, ...] = ()
    interpretation_review_traces: tuple[InterpretationReviewTrace, ...] = ()
    graph_series_data: tuple[GraphSeriesData, ...] = ()
    graph_analyses: tuple[GraphAnalysis, ...] = ()
    regression_observations: tuple[RegressionObservation, ...] = ()
    regression_series_matches: tuple[RegressionSeriesMatch, ...] = ()
    regression_model_analyses: tuple[RegressionModelAnalysis, ...] = ()
    all_graph_series_data: tuple[GraphSeriesData, ...] = ()
    regression_plot_matches: tuple[RegressionPlotMatch, ...] = ()
    regression_plot_consistency_analyses: tuple[RegressionPlotConsistencyAnalysis, ...] = ()

    def __post_init__(self) -> None:
        detections = tuple(self.observed_value_detections)
        object.__setattr__(self, "observed_value_detections", detections)
        object.__setattr__(self, "protocol_evaluations", tuple(self.protocol_evaluations))
        object.__setattr__(self, "conclusion_evaluations", tuple(self.conclusion_evaluations))
        object.__setattr__(self, "interpretation_response_evaluations", tuple(self.interpretation_response_evaluations))
        object.__setattr__(self, "interpretation_review_traces", tuple(self.interpretation_review_traces))
        object.__setattr__(self, "graph_series_data", tuple(self.graph_series_data))
        object.__setattr__(self, "graph_analyses", tuple(self.graph_analyses))
        object.__setattr__(self, "regression_observations", tuple(self.regression_observations))
        object.__setattr__(self, "regression_series_matches", tuple(self.regression_series_matches))
        object.__setattr__(self, "regression_model_analyses", tuple(self.regression_model_analyses))
        object.__setattr__(self, "all_graph_series_data", tuple(self.all_graph_series_data))
        object.__setattr__(self, "regression_plot_matches", tuple(self.regression_plot_matches))
        object.__setattr__(self, "regression_plot_consistency_analyses", tuple(self.regression_plot_consistency_analyses))
        expected_ids = tuple(item.production_id for item in self.quantity_evaluations)
        observed_ids = tuple(item.production.id for item in detections)
        if observed_ids != expected_ids:
            raise ValueError(
                "Une détection observée est requise pour chaque production quantitative, dans l'ordre."
            )

    @property
    def project_id(self) -> str:
        return self.project.identity.project_id

    @property
    def source_id(self) -> str:
        return self.source.source_id

    def get_observed_value_detection(
        self, production_id: str
    ) -> ObservedValueDetection | None:
        return next(
            (
                item for item in self.observed_value_detections
                if item.production.id == production_id
            ),
            None,
        )

    @property
    def has_technical_errors(self) -> bool:
        return bool(self.technical_inspection.error_output_cell_indices)

    @property
    def has_unexecuted_code(self) -> bool:
        return bool(self.technical_inspection.unexecuted_code_cell_indices)

    @property
    def has_placeholders(self) -> bool:
        return bool(self.technical_inspection.question_mark_code_cell_indices)

    @property
    def has_missing_productions(self) -> bool:
        return self.production_resolutions.has_missing

    @property
    def has_ambiguous_productions(self) -> bool:
        return self.production_resolutions.has_ambiguous

    @property
    def has_graph_issues(self) -> bool:
        return any(item.has_issues for item in self.graph_evaluations)

    @property
    def has_comparison_issues(self) -> bool:
        return any(
            item.status is not QuantityComparisonEvaluationStatus.COHERENT
            for item in self.quantity_comparison_evaluations
        )

    @property
    def has_interpretation_issues(self) -> bool:
        return any(
            item.status is not ComparisonInterpretationEvaluationStatus.MATCHES_OBJECTIVE_CLASSIFICATION
            for item in self.comparison_interpretation_evaluations
        )

    @property
    def has_justification_issues(self) -> bool:
        return any(
            item.status is not ComparisonJustificationEvaluationStatus.COMPLETE
            for item in self.comparison_justification_evaluations
        )

    @property
    def has_feedback(self) -> bool:
        return bool(self.feedback)

    @property
    def has_protocol_issues(self) -> bool:
        return any(item.status is not ProtocolStatus.PRESENT for item in self.protocol_evaluations)

    @property
    def has_conclusion_issues(self) -> bool:
        return any(
            item.status is not ProtocolStatus.PRESENT
            or getattr(item, "quality", None) is not None
            and getattr(item.quality, "value", item.quality) in {"AB", "À revoir"}
            for item in self.conclusion_evaluations
        )

    @property
    def has_interpretation_response_issues(self) -> bool:
        return any(
            (item.status is not ProtocolStatus.PRESENT and item.classification is None)
            or item.requires_human_review
            for item in self.interpretation_response_evaluations
        )

    @property
    def requires_human_review(self) -> bool:
        return any((
            self.has_technical_errors,
            self.has_placeholders,
            self.has_missing_productions,
            self.has_ambiguous_productions,
            any(item.ambiguous for item in self.observed_value_detections),
            self.has_graph_issues,
            self.has_comparison_issues,
            self.has_interpretation_issues,
            self.has_justification_issues,
            self.has_protocol_issues,
            self.has_conclusion_issues,
            self.has_interpretation_response_issues,
        ))

    def __repr__(self) -> str:
        return (
            f"CopyAnalysisResult(project_id={self.project_id!r}, source_id={self.source_id!r}, "
            f"requires_human_review={self.requires_human_review!r})"
        )


def _catalog(project: TeacherProjectConfiguration, expected_type):
    return next((item for item in project.feedback_catalogs if type(item) is expected_type), None)


def _audience_allowed(item: object, options: CopyAnalysisOptions) -> bool:
    audience = getattr(item, "audience", None)
    return (
        (audience is FeedbackAudience.STUDENT and options.student_feedback)
        or (audience is FeedbackAudience.TEACHER and options.teacher_feedback)
    )


def _adapted_quantity_text(
    resolution: NotebookBindingResolution,
    detection: ObservedValueDetection,
    expectation,
) -> str:
    selected = detection.selected
    if selected is None:
        return "" if detection.candidates else (resolution.text or "")
    if selected.source is ObservedValueSource.MARKDOWN_TEXT:
        return resolution.text or ""
    extracted = extract_expected_quantity(selected.raw_text, expectation)
    if extracted.observations:
        return selected.raw_text
    return f"{expectation.canonical_symbol} = {selected.value}"


def _assess_adapted_quantities(
    resolution_set: NotebookBindingResolutionSet,
    project: TeacherProjectConfiguration,
    detections: tuple[ObservedValueDetection, ...],
    feedback_catalog: QuantityFeedbackCatalog | None,
) -> NotebookQuantityAssessmentSet:
    by_production = {item.production.id: item for item in detections}
    items = []
    for resolution in resolution_set:
        production = project.scientific_production_plan.get(resolution.production_id)
        assert production is not None
        if production.kind is not ScientificProductionKind.QUANTITY:
            continue
        if resolution.failed:
            items.append(NotebookQuantityAssessmentItem(
                resolution, production,
                NotebookQuantityAssessmentStatus.RESOLUTION_FAILED,
            ))
            continue
        expectation = project.quantity_expectation_set.get(production.id)
        assert expectation is not None
        assessment = assess_quantity_text(
            _adapted_quantity_text(
                resolution, by_production[production.id], expectation
            ),
            production.id,
            project.quantity_expectation_set,
            project.uncertainty_expectation_set,
            feedback_catalog,
        )
        items.append(NotebookQuantityAssessmentItem(
            resolution, production, NotebookQuantityAssessmentStatus.ASSESSED,
            assessment,
        ))
    return NotebookQuantityAssessmentSet(resolution_set, tuple(items))


class SnellsLawsCopyAnalyzer:
    def analyze(
        self,
        source: NotebookCopySource,
        project: TeacherProjectConfiguration | None = None,
        options: CopyAnalysisOptions | None = None,
    ) -> CopyAnalysisResult:
        project = snells_laws_teacher_project() if project is None else project
        options = CopyAnalysisOptions() if options is None else options
        if type(source) is not NotebookCopySource:
            raise TypeError("La source de copie est invalide.")
        if type(options) is not CopyAnalysisOptions:
            raise TypeError("Les options d'analyse sont invalides.")
        if options.execute_notebook:
            raise NotImplementedError("A71c n'exécute jamais automatiquement un notebook.")
        validate_teacher_project_configuration(project)
        notebook = load_notebook_copy(source)
        technical = inspect_notebook(notebook)
        resolution_set = resolve_notebook_bindings(
            notebook, project.notebook_binding_plan
        )
        protocol_evaluations = evaluate_protocol_cells(
            notebook, tuple(project.experimental_manipulations)
        )
        conclusion_evaluations = evaluate_conclusion_cells(
            notebook, contexts=build_conclusion_contexts(notebook)
        )
        interpretation_contexts = build_interpretation_contexts(notebook)
        interpretation_response_evaluations = evaluate_interpretation_cells(
            notebook, contexts=interpretation_contexts
        )
        regression_observations = tuple(
            observation
            for cell_index, cell in enumerate(notebook.cells)
            if cell.cell_type == "code"
            for observation in extract_regression_observations(
                cell.source, cell_index, cell.get("id")
            )
        )
        quantity_catalog = (
            _catalog(project, QuantityFeedbackCatalog)
            if options.build_diagnostics and options.render_feedback else None
        )
        production_resolutions = CopyProductionResolutionSet(
            resolution_set, tuple(CopyProductionResolution(item) for item in resolution_set)
        )
        stale_cells = set(technical.unexecuted_code_cell_indices) | set(technical.error_output_cell_indices)
        value_detections = []
        for expectation in project.quantity_expectation_set:
            candidates = resolution_set.for_production(expectation.production_id)
            if len(candidates) != 1:
                raise ValueError("A71c exige un binding quantitatif unique par production.")
            resolution = candidates[0]
            production = project.scientific_production_plan.get(expectation.production_id)
            assert production is not None
            dependencies = tuple(
                dependency_resolution
                for dependency_id in production.depends_on
                for dependency_resolution in resolution_set.for_production(dependency_id)
            )
            relevant_cells = tuple(
                item.cell.index
                for item in (resolution, *dependencies)
                if item.cell is not None
            )
            value_detections.append(detect_observed_values(
                notebook,
                resolution,
                production,
                expectation=expectation,
                associated_resolutions=dependencies,
                saved_output_may_be_stale=(
                    bool(stale_cells.intersection(relevant_cells))
                ),
                inspect_saved_outputs=options.inspect_saved_outputs,
            ))
        quantity_set = _assess_adapted_quantities(
            resolution_set, project, tuple(value_detections), quantity_catalog
        )
        graph_evaluations = []
        if options.inspect_graphs and project.graph_expectation_set is not None:
            for expectation in project.graph_expectation_set:
                candidates = resolution_set.for_production(expectation.production_id)
                resolved = tuple(item for item in candidates if item.resolved)
                observation = observe_saved_graph(notebook, resolved[0]) if len(resolved) == 1 else None
                graph_evaluations.append(evaluate_saved_graph(expectation, observation))

        comparison_set = evaluate_quantity_comparisons(
            quantity_set, project.quantity_comparison_expectation_set
        )
        student_errors = evaluate_student_normalized_errors(
            comparison_set, project.student_normalized_error_expectation_set
        )
        interpretations = evaluate_comparison_interpretations(
            comparison_set, project.comparison_interpretation_expectation_set, student_errors
        )
        justifications = evaluate_comparison_justifications(
            interpretations, project.comparison_justification_expectation_set, student_errors
        )

        diagnostics: list[object] = []
        feedback: list[object] = []
        if options.build_diagnostics:
            comparison_diagnostics = build_quantity_comparison_diagnostics(comparison_set)
            interpretation_diagnostics = build_comparison_interpretation_diagnostics(interpretations)
            justification_diagnostics = build_comparison_justification_diagnostics(justifications)
            diagnostics.extend(quantity_set.diagnostics)
            diagnostics.extend(comparison_diagnostics)
            diagnostics.extend(interpretation_diagnostics)
            diagnostics.extend(justification_diagnostics)
            for item in protocol_evaluations:
                if item.status is not ProtocolStatus.PRESENT:
                    diagnostics.append(ProtocolDiagnostic(
                        item.expectation_id, item.manipulation_id, item.cell_index,
                        item.status,
                        "PROTOCOL_EXPECTED_MISSING" if item.status is ProtocolStatus.MISSING else "PROTOCOL_NOT_EVALUABLE",
                        "Le protocole expérimental de cette manipulation n'est pas décrit."
                        if item.status is ProtocolStatus.MISSING
                        else "La cellule de protocole ne peut pas être évaluée automatiquement.",
                    ))
                    target_index = item.cell_index if item.cell_index is not None else item.anchor_cell_index
                    if options.render_feedback and item.status is ProtocolStatus.MISSING and target_index is not None:
                        feedback.append(ProtocolFeedbackItem(
                            item.expectation_id, item.manipulation_id,
                            "Le protocole expérimental de cette manipulation n'est pas décrit.",
                            target_index,
                            item.cell_type or "markdown",
                        ))
            conclusion_diagnostics = build_conclusion_diagnostics(conclusion_evaluations)
            diagnostics.extend(conclusion_diagnostics)
            if options.render_feedback:
                feedback.extend(build_conclusion_feedback(conclusion_evaluations))
            diagnostics.extend(build_interpretation_diagnostics(interpretation_response_evaluations))
            if options.render_feedback:
                feedback.extend(build_interpretation_feedback(interpretation_response_evaluations))
            if options.render_feedback:
                feedback.extend(quantity_set.student_feedback)
                feedback.extend(quantity_set.teacher_feedback)
                comparison_catalog = _catalog(project, QuantityComparisonFeedbackCatalog)
                interpretation_catalog = _catalog(project, ComparisonInterpretationFeedbackCatalog)
                justification_catalog = _catalog(project, ComparisonJustificationFeedbackCatalog)
                if comparison_catalog is not None:
                    feedback.extend(render_quantity_comparison_feedback(comparison_diagnostics, comparison_catalog))
                if interpretation_catalog is not None:
                    feedback.extend(render_comparison_interpretation_feedback(interpretation_diagnostics, interpretation_catalog))
                if justification_catalog is not None:
                    feedback.extend(render_comparison_justification_feedback(justification_diagnostics, justification_catalog))
        feedback = [item for item in feedback if _audience_allowed(item, options)]
        source_sha256 = hashlib.sha256(source.path.read_bytes()).hexdigest()
        interpretation_review_traces = build_interpretation_review_traces(
            notebook, tuple(interpretation_response_evaluations), interpretation_contexts,
            tuple(item for item in feedback if isinstance(item, InterpretationFeedbackItem)),
            copy_id=source.source_id, copy_sha256=source_sha256,
        )

        relation_evaluations = []
        for relation in project.relation_expectation_set.relations:
            candidates = resolution_set.for_production(relation.id)
            resolved = tuple(item for item in candidates if item.resolved)
            status = (
                RelationObservationStatus.OBSERVED if len(resolved) == 1
                else RelationObservationStatus.AMBIGUOUS if len(resolved) > 1
                else RelationObservationStatus.MISSING
            )
            relation_evaluations.append(RelationEvaluation(
                relation.id, status, resolved[0] if len(resolved) == 1 else None
            ))

        conclusion_candidates = resolution_set.for_production("final_conclusion")
        resolved_conclusions = tuple(item for item in conclusion_candidates if item.resolved)
        has_ambiguous_conclusion = any(
            item.status in (
                NotebookBindingResolutionStatus.CELL_AMBIGUOUS,
                NotebookBindingResolutionStatus.TEXT_MARKER_AMBIGUOUS,
            )
            for item in conclusion_candidates
        )
        conclusion_source = (
            resolved_conclusions[0]
            if len(resolved_conclusions) == 1 and not has_ambiguous_conclusion else None
        )
        conclusion = FinalConclusionObservation(
            "final_conclusion", conclusion_candidates, conclusion_source,
            conclusion_source.text if conclusion_source else None,
        )
        uncertainty_evaluations = tuple(
            item.assessment.uncertainty_evaluation
            for item in quantity_set
            if item.assessment is not None and item.assessment.uncertainty_evaluation is not None
        )
        limitations = [
            "Les outputs enregistrés ne prouvent pas qu'ils correspondent au code courant.",
            "L'analyse du graphe est structurelle et n'inspecte aucun pixel.",
            "La conclusion finale est conservée séparément des comparaisons.",
            "A70b exige actuellement une unité observée, y compris pour les indices sans dimension configurés sans unité.",
        ]
        graph_series_data = tuple(
            series
            for evaluation in graph_evaluations
            for series in (evaluation.observation.series_data if evaluation.observation else ())
        )
        graph_analyses = analyze_graph_series_collection(graph_series_data)
        all_graph_series_data = extract_all_graph_series_data(notebook)
        regression_series_matches = match_regressions_to_series(
            notebook, regression_observations, all_graph_series_data
        )
        regression_model_analyses = analyze_regression_models(
            regression_observations, regression_series_matches, all_graph_series_data
        )
        regression_plot_matches = match_regressions_to_plots(
            notebook, regression_observations, regression_model_analyses, all_graph_series_data
        )
        regression_plot_consistency_analyses = compare_regression_plots(
            regression_model_analyses, regression_plot_matches, all_graph_series_data,
            regression_observations, notebook,
        )
        return CopyAnalysisResult(
            project, source, options, technical, production_resolutions,
            tuple(value_detections), quantity_set, uncertainty_evaluations,
            tuple(relation_evaluations), tuple(graph_evaluations), comparison_set,
            student_errors, interpretations, justifications, tuple(diagnostics),
            tuple(feedback), conclusion, tuple(limitations),
            tuple(protocol_evaluations),
            tuple(conclusion_evaluations),
            tuple(interpretation_response_evaluations),
            tuple(interpretation_review_traces),
            graph_series_data=graph_series_data,
            graph_analyses=graph_analyses,
            regression_observations=regression_observations,
            regression_series_matches=regression_series_matches,
            regression_model_analyses=regression_model_analyses,
            all_graph_series_data=all_graph_series_data,
            regression_plot_matches=regression_plot_matches,
            regression_plot_consistency_analyses=regression_plot_consistency_analyses,
        )


def analyze_snells_laws_copy(source, project=None, options=None) -> CopyAnalysisResult:
    return SnellsLawsCopyAnalyzer().analyze(source, project, options)


def summarize_copy_analysis(result: CopyAnalysisResult) -> str:
    if type(result) is not CopyAnalysisResult:
        raise TypeError("Le résultat doit être exactement un CopyAnalysisResult.")
    technical = result.technical_inspection
    student = sum(getattr(item, "audience", None) is FeedbackAudience.STUDENT for item in result.feedback)
    teacher = sum(getattr(item, "audience", None) is FeedbackAudience.TEACHER for item in result.feedback)
    lines = (
        f"Projet : {result.project_id}",
        f"Source : {result.source_id}",
        f"Technique : {technical.cell_count} cellules, {len(technical.error_output_cell_indices)} erreur(s), {len(technical.unexecuted_code_cell_indices)} code(s) non exécuté(s)",
        f"Productions : {len(result.production_resolutions.resolved)} résolue(s), {len(result.production_resolutions.missing)} absente(s), {len(result.production_resolutions.ambiguous)} ambiguë(s)",
        f"Quantités : {len(result.quantity_evaluations.assessed)} évaluée(s)",
        f"Graphes : {len(result.graph_evaluations)} analysé(s), problèmes={result.has_graph_issues}",
        f"Comparaisons : {len(result.quantity_comparison_evaluations)}",
        f"En étudiant : {len(result.student_normalized_error_evaluations)}",
        f"Interprétations : {len(result.comparison_interpretation_evaluations)}",
        f"Justifications : {len(result.comparison_justification_evaluations)}",
        f"Diagnostics : {len(result.diagnostics)}",
        f"Feedbacks : étudiant={student}, professeur={teacher}",
        "Limites : " + " | ".join(result.limitations),
        f"Revue humaine : {result.requires_human_review}",
    )
    return "\n".join(lines)
