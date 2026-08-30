"""Formative grading policy for the guided first laboratory session."""

from decimal import Decimal

from tpstudio.grading import (
    FormativeGradingProfile,
    RubricCriterion,
    RubricDecision,
    RubricLevel,
    RubricSuggestion,
)
from tpstudio.semantic_analysis import (
    SemanticCriterionImportance,
    SemanticCriterionStatus,
    SemanticRole,
)


FIRST_LAB_FORMATIVE_GRADING_PROFILE = FormativeGradingProfile(
    "first-lab-formative-v1",
    "first-lab-measurements",
    "Barème formatif — première séance",
    Decimal("16"),
    Decimal("4"),
    Decimal("12"),
    (
        RubricCriterion(
            "manipulation_objectives",
            "Problématique des manipulations",
            "Grandeur recherchée, méthode envisagée et finalité de chaque manipulation.",
            Decimal("0.15"),
        ),
        RubricCriterion(
            "protocols",
            "Protocoles",
            "Description reproductible, réglages, précautions et figure lorsqu'elle est demandée.",
            Decimal("0.20"),
        ),
        RubricCriterion(
            "results_presentation",
            "Résultats et présentation",
            "Tableaux, graphes, unités, incertitudes, arrondis et lisibilité.",
            Decimal("0.25"),
        ),
        RubricCriterion(
            "interpretation",
            "Exploitation et interprétation",
            "Modèles, régression, comparaison quantitative, limites et conclusions.",
            Decimal("0.30"),
        ),
        RubricCriterion(
            "completion",
            "Travail traité",
            "Part des productions obligatoires réellement abordées.",
            Decimal("0.10"),
        ),
    ),
)


def _semantic_suggestion(analyses, roles, criterion_id: str) -> RubricSuggestion:
    accepted_roles = (roles,) if type(roles) is SemanticRole else tuple(roles)
    relevant = tuple(
        item for item in analyses if item.contract.semantic_role in accepted_roles
    )
    answered = tuple(item for item in relevant if (item.student_response or "").strip())
    if not answered:
        return RubricSuggestion(
            RubricDecision(criterion_id, RubricLevel.ABSENT),
            "Aucune réponse correspondante n’a été repérée.",
        )
    if len(answered) < len(relevant):
        return RubricSuggestion(
            RubricDecision(criterion_id, RubricLevel.PARTIAL),
            f"{len(answered)} réponse(s) présente(s) sur {len(relevant)} attendue(s).",
        )
    results = tuple(item.result for item in answered if item.result is not None)
    provider_evaluable = bool(results) and all(
        not any(code.startswith("SEMANTIC_") for code in result.diagnostics)
        for result in results
    )
    if not provider_evaluable:
        return RubricSuggestion(
            RubricDecision(criterion_id, RubricLevel.GOOD),
            "Toutes les réponses sont présentes, mais leur qualité reste à confirmer par le professeur.",
        )
    statuses = tuple(
        (criterion.importance, result.status)
        for analysis in answered
        for criterion in analysis.contract.criteria
        for result in analysis.result.criterion_results
        if result.criterion_id == criterion.criterion_id
    )
    required = tuple(status for importance, status in statuses if importance is SemanticCriterionImportance.REQUIRED)
    all_required = bool(required) and all(status is SemanticCriterionStatus.SATISFIED for status in required)
    all_criteria = bool(statuses) and all(status is SemanticCriterionStatus.SATISFIED for _, status in statuses)
    contradictions = any(analysis.result.contradictions for analysis in answered)
    if all_criteria and not contradictions:
        level = RubricLevel.VERY_GOOD
        rationale = "Tous les critères attendus ont été repérés sans contradiction."
    elif all_required and not contradictions:
        level = RubricLevel.GOOD
        rationale = "Tous les critères requis ont été repérés ; certains éléments recommandés restent incomplets."
    else:
        required_found = any(
            status in (SemanticCriterionStatus.SATISFIED, SemanticCriterionStatus.PARTIAL)
            for status in required
        )
        level = RubricLevel.PARTIAL if required_found and not contradictions else RubricLevel.TO_REVIEW
        rationale = (
            "Une ou plusieurs attentes requises sont partielles ou absentes."
            if level is RubricLevel.PARTIAL
            else "La réponse est présente, mais ses éléments essentiels sont absents ou contradictoires."
        )
    return RubricSuggestion(RubricDecision(criterion_id, level), rationale)


def _results_suggestion(analysis) -> RubricSuggestion:
    quantities = tuple(analysis.quantity_evaluations)
    present = tuple(
        item for item in quantities
        if item.assessment is not None and item.assessment.selected_observation is not None
    )
    graphs = tuple(analysis.graph_evaluations)
    graph_present = tuple(
        item for item in graphs
        if item.observation is not None and item.observation.figure_output_present
    )
    expected_count = len(quantities) + len(graphs)
    present_count = len(present) + len(graph_present)
    structurally_incomplete = tuple(
        item for item in present if not item.assessment.is_structurally_satisfied
    )
    formatting_criterion_ids = {
        "period_with_uncertainty",
        "dynamic_stiffness_with_uncertainty",
        "static_stiffness_with_uncertainty",
    }
    formatting_statuses = tuple(
        criterion_result.status
        for semantic_analysis in analysis.semantic_response_analyses
        if semantic_analysis.result is not None
        and not any(
            diagnostic.startswith("SEMANTIC_")
            for diagnostic in semantic_analysis.result.diagnostics
        )
        for criterion_result in semantic_analysis.result.criterion_results
        if criterion_result.criterion_id in formatting_criterion_ids
    )
    incomplete_formatting = tuple(
        status for status in formatting_statuses
        if status is not SemanticCriterionStatus.SATISFIED
    )
    insufficient_linear_regression = any(
        item.degree == 1
        and "trop_peu_de_points_pour_regression_lineaire" in item.diagnostics
        for item in getattr(analysis, "regression_model_analyses", ())
    )
    if present_count == 0:
        level = RubricLevel.ABSENT
    elif formatting_statuses and len(incomplete_formatting) == len(formatting_statuses):
        level = RubricLevel.TO_REVIEW
    elif present and len(structurally_incomplete) == len(present):
        level = RubricLevel.TO_REVIEW
    elif incomplete_formatting or structurally_incomplete:
        level = RubricLevel.PARTIAL
    elif present_count < expected_count:
        level = RubricLevel.PARTIAL
    elif insufficient_linear_regression:
        level = RubricLevel.PARTIAL
    elif not insufficient_linear_regression and all(
        item.assessment.is_structurally_satisfied for item in present
    ) and all(
        item.orientation_status.value == "matches"
        and item.label_status.value == "matches"
        and (
            not item.expectation.regression_required
            or item.regression_status.value == "matches"
        )
        for item in graph_present
    ):
        level = RubricLevel.VERY_GOOD
    else:
        level = RubricLevel.GOOD
    if formatting_statuses and len(incomplete_formatting) == len(formatting_statuses):
        rationale = "Les résultats rédigés omettent les unités ou incertitudes attendues."
    elif incomplete_formatting:
        rationale = "Au moins un résultat rédigé omet une unité ou une incertitude attendue."
    elif structurally_incomplete:
        rationale = "Au moins un résultat numérique est incomplet : valeur, unité ou incertitude attendue manquante."
    elif insufficient_linear_regression:
        rationale = "La régression linéaire comporte moins de cinq couples de mesures."
    else:
        rationale = f"{present_count} production(s) quantitative ou graphique présente(s) sur {expected_count} attendue(s)."
    return RubricSuggestion(
        RubricDecision("results_presentation", level),
        rationale,
    )


def _completion_suggestion(analysis) -> RubricSuggestion:
    semantic = tuple(analysis.semantic_response_analyses)
    answered = sum(bool((item.student_response or "").strip()) for item in semantic)
    quantities = tuple(analysis.quantity_evaluations)
    observed = sum(
        item.assessment is not None and item.assessment.selected_observation is not None
        for item in quantities
    )
    graphs = tuple(analysis.graph_evaluations)
    plotted = sum(
        item.observation is not None and item.observation.figure_output_present
        for item in graphs
    )
    completed = answered + observed + plotted
    expected = len(semantic) + len(quantities) + len(graphs)
    ratio = completed / expected if expected else 0
    if completed == 0:
        level = RubricLevel.ABSENT
    elif ratio < 0.5 or (analysis.has_placeholders and ratio < 0.75):
        level = RubricLevel.TO_REVIEW
    elif ratio < 0.75 or analysis.has_placeholders:
        level = RubricLevel.PARTIAL
    elif ratio < 1 or analysis.has_unexecuted_code:
        level = RubricLevel.GOOD
    else:
        level = RubricLevel.VERY_GOOD
    return RubricSuggestion(
        RubricDecision("completion", level),
        f"{completed} production(s) renseignée(s) sur {expected} observables.",
    )


def suggest_first_lab_rubric(analysis) -> tuple[RubricSuggestion, ...]:
    """Build conservative, auditable defaults without deciding the final grade."""

    if getattr(analysis, "project_id", None) != FIRST_LAB_FORMATIVE_GRADING_PROFILE.project_id:
        raise ValueError("Le barème de la séance 1 exige l’analyse du projet correspondant.")
    semantic = tuple(analysis.semantic_response_analyses)
    suggestions = {
        "manipulation_objectives": _semantic_suggestion(
            semantic, SemanticRole.OBJECTIVE, "manipulation_objectives"
        ),
        "protocols": _semantic_suggestion(semantic, SemanticRole.PROTOCOL, "protocols"),
        "results_presentation": _results_suggestion(analysis),
        "interpretation": _semantic_suggestion(
            semantic, (SemanticRole.INTERPRETATION, SemanticRole.CONCLUSION), "interpretation"
        ),
        "completion": _completion_suggestion(analysis),
    }
    return tuple(
        suggestions[criterion.criterion_id]
        for criterion in FIRST_LAB_FORMATIVE_GRADING_PROFILE.criteria
    )
