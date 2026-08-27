"""Teacher configuration for the aligned prism-goniometer TP."""

from __future__ import annotations

from decimal import Decimal

from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    ComparisonInterpretationExpectationSet,
    ComparisonJustificationExpectationSet,
    ComparisonPedagogicalContext,
    EvaluationBasis,
    ExpectedQuantity,
    ExpectedQuantityComparison,
    ExpectedStudentNormalizedError,
    ExpectationSet,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
    PresenceRequirement,
    QuantityComparisonExpectationSet,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
    StudentNormalizedErrorExpectationSet,
    UncertaintyQualityExpectationSet,
    UncertaintyQualitySpec,
)
from tpstudio.feedback import (
    french_quantity_comparison_feedback_catalog,
    french_quantity_feedback_catalog,
)
from tpstudio.semantic_analysis import (
    ExpectedSemanticResponse,
    SemanticCriterion,
    SemanticCriterionImportance,
    SemanticRole,
)

from .model import (
    NotebookReference,
    NotebookReferenceRole,
    TeacherProjectConfiguration,
    TeacherProjectIdentity,
)


STATEMENT_FILENAME = "Mesure-dindice-au-goniometre-a-prisme.ipynb"
CORRECTION_FILENAME = "Correction-Mesure-dindice-au-goniometre-a-prisme.ipynb"


def _criterion(
    identifier: str,
    description: str,
    importance: SemanticCriterionImportance = SemanticCriterionImportance.REQUIRED,
) -> SemanticCriterion:
    return SemanticCriterion(identifier, description, importance)


SEMANTIC_RESPONSE_EXPECTATIONS = (
    ExpectedSemanticResponse(
        "goniometer_settings",
        SemanticRole.PROTOCOL,
        (
            _criterion("settings_objective", "Relier les réglages à une observation à l'infini et à des mesures angulaires fiables."),
            _criterion("own_instrument", "Décrire les réglages réellement effectués par le binôme sur son propre goniomètre."),
            _criterion("eyepiece_and_autocollimation", "Mentionner le réglage de l'oculaire puis celui de l'objectif par autocollimation."),
            _criterion("mechanical_alignment", "Décrire le réglage mécanique de la lunette ou du plateau porte-prisme."),
            _criterion("collimator_criterion", "Régler le collimateur pour obtenir une fente fine et nette à l'infini, sans parallaxe perceptible."),
            _criterion("setting_difficulty", "Signaler une difficulté ou une limite rencontrée lors des réglages.", SemanticCriterionImportance.RECOMMENDED),
        ),
    ),
    ExpectedSemanticResponse(
        "prism_angle_protocol",
        SemanticRole.PROTOCOL,
        (
            _criterion("angle_objective", "Identifier la mesure de l'angle au sommet A comme objectif."),
            _criterion("two_face_autocollimation", "Viser successivement les deux faces du prisme par autocollimation."),
            _criterion("two_vernier_readings", "Relever les deux positions angulaires au vernier."),
            _criterion("reading_intervals", "Expliquer le choix des demi-largeurs d'intervalle associées aux lectures."),
        ),
    ),
    ExpectedSemanticResponse(
        "prism_angle_result",
        SemanticRole.INTERPRETATION,
        (
            _criterion("angle_result", "Donner A avec son incertitude et un arrondi cohérent."),
            _criterion("angle_normalized_error", "Interpréter l'écart normalisé avec 60 degrés en utilisant le seuil 2."),
            _criterion("angle_limit", "Discuter la superposition du réticule, l'autocollimation ou la lecture du vernier comme limite."),
        ),
    ),
    ExpectedSemanticResponse(
        "minimum_deviation_protocol",
        SemanticRole.PROTOCOL,
        (
            _criterion("minimum_objective", "Identifier la mesure du minimum de déviation afin de déterminer l'indice."),
            _criterion("direction_reversal", "Repérer le minimum par le changement de sens de déplacement de l'image."),
            _criterion("two_symmetric_positions", "Effectuer la recherche dans les deux orientations symétriques du prisme."),
            _criterion("minimum_vernier_readings", "Relever les deux positions de la lunette et leurs intervalles d'incertitude."),
        ),
    ),
    ExpectedSemanticResponse(
        "prism_index_result",
        SemanticRole.INTERPRETATION,
        (
            _criterion("minimum_result", "Donner D_m avec son incertitude."),
            _criterion("index_result", "Donner l'indice n avec son incertitude et un arrondi cohérent."),
            _criterion("index_normalized_error", "Interpréter l'écart normalisé avec la valeur constructeur et le seuil 2."),
            _criterion("index_limit", "Discuter la recherche du minimum ou la lecture du vernier comme limite expérimentale."),
        ),
    ),
    ExpectedSemanticResponse(
        "final_conclusion",
        SemanticRole.CONCLUSION,
        (
            _criterion("objectives_summary", "Rappeler les objectifs de réglage et de mesure de l'indice."),
            _criterion("reported_results", "Présenter A, D_m et n avec leurs incertitudes."),
            _criterion("constructor_compatibility", "Conclure sur la compatibilité avec les valeurs constructeur."),
            _criterion("main_limitations", "Résumer les principales limites liées aux réglages et aux critères visuels."),
        ),
    ),
)


def _plan() -> ScientificProductionPlan:
    structural = EvaluationBasis.STRUCTURAL
    cross = EvaluationBasis.CROSS_PRODUCTION
    semantic = EvaluationBasis.SEMANTIC
    quantity = ScientificProductionKind.QUANTITY
    comparison = ScientificProductionKind.COMPARISON
    interpretation = ScientificProductionKind.INTERPRETATION

    def spec(identifier, label, kind, bases, depends_on=()):
        return ScientificProductionSpec(identifier, label, kind, bases, depends_on)

    return ScientificProductionPlan(
        "prism-goniometer-productions",
        "Productions scientifiques — Mesure d'indice au goniomètre",
        (
            spec("goniometer_settings", "Réglages du goniomètre", interpretation, (semantic,)),
            spec("prism_angle_protocol", "Protocole de mesure de A", interpretation, (semantic,)),
            spec("prism_angle", "Angle au sommet du prisme", quantity, (structural,)),
            spec("prism_angle_reference", "Angle constructeur", quantity, (structural,)),
            spec("compare_prism_angle", "Comparaison de A au constructeur", comparison, (cross,), ("prism_angle", "prism_angle_reference")),
            spec("prism_angle_result", "Interprétation de A", interpretation, (semantic,), ("compare_prism_angle",)),
            spec("minimum_deviation_protocol", "Protocole du minimum de déviation", interpretation, (semantic,)),
            spec("minimum_deviation", "Angle minimum de déviation", quantity, (structural,)),
            spec("refractive_index", "Indice mesuré du prisme", quantity, (structural,)),
            spec("refractive_index_reference", "Indice constructeur", quantity, (structural,)),
            spec("compare_refractive_index", "Comparaison de l'indice au constructeur", comparison, (cross,), ("refractive_index", "refractive_index_reference")),
            spec("prism_index_result", "Interprétation de l'indice", interpretation, (semantic,), ("compare_refractive_index",)),
            spec("final_conclusion", "Conclusion générale", interpretation, (semantic,), ("prism_angle_result", "prism_index_result")),
        ),
        "Les valeurs doivent provenir du goniomètre réglé et utilisé par le binôme.",
    )


def _binding(identifier: str, production_id: str, marker: str) -> CellProductionBinding:
    return CellProductionBinding(
        identifier,
        production_id,
        NotebookCellSelector(NotebookCellSelectorKind.SOURCE_MARKER, marker),
        CellTextScope.full_source(),
        "Association par marqueur source stable du notebook aligné.",
    )


def _bindings(plan: ScientificProductionPlan) -> NotebookBindingPlan:
    return NotebookBindingPlan(
        "prism-goniometer-bindings",
        "Associations du TP Goniomètre à prisme",
        plan,
        (
            _binding("goniometer-settings-response", "goniometer_settings", "goniometer-settings-response"),
            _binding("prism-angle-protocol-response", "prism_angle_protocol", "prism-angle-protocol-response"),
            _binding("prism-angle-cell", "prism_angle", "A = A_values.mean()"),
            _binding("prism-angle-reference-cell", "prism_angle_reference", "A_constructeur = 60"),
            _binding("prism-angle-comparison-cell", "compare_prism_angle", "E_n_A = ecart_normalise"),
            _binding("prism-angle-result-response", "prism_angle_result", "prism-angle-result-response"),
            _binding("minimum-deviation-protocol-response", "minimum_deviation_protocol", "minimum-deviation-protocol-response"),
            _binding("minimum-deviation-cell", "minimum_deviation", "Dm = Dm_values.mean()"),
            _binding("refractive-index-cell", "refractive_index", "n = n_values.mean()"),
            _binding("refractive-index-reference-cell", "refractive_index_reference", "n_constructeur = 1.76"),
            _binding("refractive-index-comparison-cell", "compare_refractive_index", "E_n_n = ecart_normalise"),
            _binding("prism-index-result-response", "prism_index_result", "prism-index-result-response"),
            _binding("prism-final-conclusion-response", "final_conclusion", "prism-final-conclusion-response"),
        ),
        "Les cellules de réponse et de calcul possèdent des marqueurs stables.",
    )


def prism_goniometer_teacher_project() -> TeacherProjectConfiguration:
    """Build the immutable project configuration for the prism goniometer."""
    plan = _plan()
    required = PresenceRequirement.REQUIRED
    ignored = PresenceRequirement.IGNORE
    quantities = QuantityExpectationSet(
        plan,
        (
            ExpectedQuantity("prism_angle", "A", (), "°", ("deg",), required, required),
            ExpectedQuantity("prism_angle_reference", "A_constructeur", ("Valeur constructeur",), "°", ("deg",), ignored, ignored),
            ExpectedQuantity("minimum_deviation", "D_m", ("Dm",), "°", ("deg",), required, required),
            ExpectedQuantity("refractive_index", "n", (), None, (), ignored, required),
            ExpectedQuantity("refractive_index_reference", "n_constructeur", ("Valeur constructeur",), None, (), ignored, ignored),
        ),
    )
    comparisons = QuantityComparisonExpectationSet(
        plan,
        quantities,
        (
            ExpectedQuantityComparison(
                "compare_prism_angle",
                "prism_angle",
                "prism_angle_reference",
                pedagogical_context=ComparisonPedagogicalContext.COHERENCE_EXPECTED,
            ),
            ExpectedQuantityComparison(
                "compare_refractive_index",
                "refractive_index",
                "refractive_index_reference",
                pedagogical_context=ComparisonPedagogicalContext.COHERENCE_EXPECTED,
            ),
        ),
    )
    student_errors = StudentNormalizedErrorExpectationSet(
        comparisons,
        (
            ExpectedStudentNormalizedError("compare_prism_angle", ("E_n_A", "Écart normalisé"), Decimal("0.05")),
            ExpectedStudentNormalizedError("compare_refractive_index", ("E_n_n", "Écart normalisé"), Decimal("0.05")),
        ),
    )
    uncertainties = UncertaintyQualityExpectationSet(
        quantities,
        tuple(
            UncertaintyQualitySpec(identifier)
            for identifier in ("prism_angle", "minimum_deviation", "refractive_index")
        ),
    )
    return TeacherProjectConfiguration(
        TeacherProjectIdentity(
            "prism-goniometer-index",
            "Mesure de l'indice au goniomètre à prisme",
            "Physique",
            "Lycée",
            "A79h1",
            "fr",
            "Réglage du goniomètre, mesure du minimum de déviation et détermination de l'indice d'un prisme.",
        ),
        (
            NotebookReference("statement", NotebookReferenceRole.STATEMENT, STATEMENT_FILENAME),
            NotebookReference("correction", NotebookReferenceRole.CORRECTION, CORRECTION_FILENAME),
        ),
        plan,
        _bindings(plan),
        quantities,
        ExpectationSet("prism-goniometer-relations", "Relations attendues — Goniomètre à prisme", relations=()),
        uncertainties,
        None,
        comparisons,
        student_errors,
        ComparisonInterpretationExpectationSet(comparisons, ()),
        ComparisonJustificationExpectationSet(comparisons, ()),
        (french_quantity_feedback_catalog(), french_quantity_comparison_feedback_catalog()),
        "La démonstration du professeur guide les réglages ; toutes les mesures évaluées restent celles du binôme.",
        semantic_response_expectations=SEMANTIC_RESPONSE_EXPECTATIONS,
    )
