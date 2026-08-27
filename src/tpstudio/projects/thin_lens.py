"""Declarative teacher configuration for the thin-lens imaging TP."""

from __future__ import annotations

from decimal import Decimal

from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    ComparisonInterpretationExpectationSet,
    ComparisonInterpretationKind,
    ComparisonJustificationElementKind,
    ComparisonJustificationExpectationSet,
    ComparisonJustificationRequirement,
    ExpectedComparisonInterpretation,
    ExpectedComparisonJustification,
    ExpectedComparisonJustificationElement,
    ExpectedQuantity,
    ExpectedQuantityComparison,
    ExpectedRelation,
    ExpectedStudentNormalizedError,
    ExpectationSet,
    EvaluationBasis,
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
)
from tpstudio.feedback import (
    french_comparison_interpretation_feedback_catalog,
    french_comparison_justification_feedback_catalog,
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
    ExpectedGraphModel,
    GraphExpectation,
    GraphExpectationSet,
    NotebookReference,
    NotebookReferenceRole,
    TeacherProjectConfiguration,
    TeacherProjectIdentity,
    validate_teacher_project_configuration,
)


def _plan() -> ScientificProductionPlan:
    structural = EvaluationBasis.STRUCTURAL
    declared = EvaluationBasis.DECLARED_CONTENT
    cross = EvaluationBasis.CROSS_PRODUCTION
    semantic = EvaluationBasis.SEMANTIC
    quantity = ScientificProductionKind.QUANTITY
    relation = ScientificProductionKind.RELATION
    plot = ScientificProductionKind.PLOT
    comparison = ScientificProductionKind.COMPARISON
    interpretation = ScientificProductionKind.INTERPRETATION
    justification = ScientificProductionKind.JUSTIFICATION
    return ScientificProductionPlan(
        "thin-lens-image-productions",
        "Productions scientifiques — Formation d'une image par une lentille mince",
        (
            ScientificProductionSpec("lens_identification", "Identification des lentilles", interpretation, (semantic,)),
            ScientificProductionSpec("real_image_protocol", "Protocole de formation d'une image réelle", interpretation, (semantic,)),
            ScientificProductionSpec("gauss_observation", "Observation hors conditions de Gauss", interpretation, (semantic,)),
            ScientificProductionSpec("conjugation_relation", "Relation de conjugaison", relation, (declared,)),
            ScientificProductionSpec("single_focal_length", "Distance focale — mesure unique", quantity, (structural,)),
            ScientificProductionSpec("theoretical_focal_length", "Distance focale théorique", quantity, (structural,)),
            ScientificProductionSpec(
                "compare_single_theory", "Comparaison mesure unique / théorie",
                comparison, (cross, semantic), ("single_focal_length", "theoretical_focal_length"),
            ),
            ScientificProductionSpec("single_uncertainty_justification", "Justification des incertitudes de position", justification, (semantic,)),
            ScientificProductionSpec("single_result_comment", "Commentaire de la mesure unique", interpretation, (semantic,), ("compare_single_theory",)),
            ScientificProductionSpec("multiple_protocol", "Protocole des mesures multiples", interpretation, (semantic,)),
            ScientificProductionSpec(
                "conjugation_graph", "Graphe de conjugaison", plot,
                (structural, declared), ("conjugation_relation",),
            ),
            ScientificProductionSpec(
                "conjugation_slope", "Pente de la régression", quantity,
                (structural,), ("conjugation_graph",),
            ),
            ScientificProductionSpec(
                "focal_intercept", "Ordonnée à l'origine", quantity,
                (structural,), ("conjugation_graph",),
            ),
            ScientificProductionSpec("theoretical_slope", "Pente théorique", quantity, (structural,)),
            ScientificProductionSpec(
                "compare_conjugation", "Comparaison de la relation de conjugaison",
                comparison, (cross, semantic), ("conjugation_slope", "theoretical_slope"),
            ),
            ScientificProductionSpec("graph_analysis", "Analyse du graphe de conjugaison", interpretation, (semantic,), ("compare_conjugation", "focal_intercept")),
            ScientificProductionSpec("multiple_focal_length", "Distance focale — mesures multiples", quantity, (structural,)),
            ScientificProductionSpec(
                "compare_multiple_theory", "Comparaison mesures multiples / théorie",
                comparison, (cross, semantic), ("multiple_focal_length", "theoretical_focal_length"),
            ),
            ScientificProductionSpec(
                "compare_single_multiple", "Comparaison des deux méthodes",
                comparison, (cross, semantic), ("single_focal_length", "multiple_focal_length"),
            ),
            ScientificProductionSpec("multiple_result_comment", "Commentaire des mesures multiples", interpretation, (semantic,), ("compare_multiple_theory", "compare_single_multiple")),
            ScientificProductionSpec(
                "final_conclusion", "Conclusion finale", interpretation,
                (semantic,), ("graph_analysis", "multiple_result_comment"),
            ),
            ScientificProductionSpec(
                "method_limitations", "Limites de la méthode", justification,
                (semantic,), ("final_conclusion",),
            ),
        ),
        "Contrat aligné sur l'énoncé TeX et fondé sur 1/OA' - 1/OA = 1/f'.",
    )


def _bindings(plan: ScientificProductionPlan) -> NotebookBindingPlan:
    def marker(identifier: str, production_id: str, value: str) -> CellProductionBinding:
        return CellProductionBinding(
            identifier, production_id,
            NotebookCellSelector(NotebookCellSelectorKind.SOURCE_MARKER, value),
            CellTextScope.full_source(),
            "Association par marqueur source stable, indépendante de l'indice de cellule.",
        )

    return NotebookBindingPlan(
        "thin-lens-image-bindings",
        "Associations du TP lentille mince",
        plan,
        (
            marker("identification-response", "lens_identification", "lens-identification-response"),
            marker("real-image-protocol-response", "real_image_protocol", "real-image-protocol-response"),
            marker("gauss-observation-response", "gauss_observation", "gauss-observation-response"),
            marker("conjugation-relation-cell", "conjugation_relation", "1/OA' - 1/OA = 1/f'"),
            marker("single-focal-cell", "single_focal_length", "f1 = f_single_samples.mean()"),
            marker("theoretical-focal-cell", "theoretical_focal_length", "f_th = 100 / 3.3"),
            marker("single-theory-comparison-cell", "compare_single_theory", "En_single_theory ="),
            marker("single-uncertainty-response", "single_uncertainty_justification", "single-uncertainty-response"),
            marker("single-result-response", "single_result_comment", "single-result-response"),
            marker("multiple-protocol-response", "multiple_protocol", "multiple-protocol-response"),
            marker("conjugation-graph-cell", "conjugation_graph", "plt.plot(invOA, invOAp"),
            marker("conjugation-slope-cell", "conjugation_slope", "a, b = np.polyfit(invOA, invOAp, 1)"),
            marker("focal-intercept-cell", "focal_intercept", "a, b = np.polyfit(invOA, invOAp, 1)"),
            marker("theoretical-slope-cell", "theoretical_slope", "La pente attendue vaut 1"),
            marker("conjugation-comparison-response", "compare_conjugation", "conjugation-graph-analysis-response"),
            marker("graph-analysis-response", "graph_analysis", "conjugation-graph-analysis-response"),
            marker("multiple-focal-cell", "multiple_focal_length", "f2 = f_multiple.mean()"),
            marker("multiple-theory-comparison-cell", "compare_multiple_theory", "En_multiple_theory ="),
            marker("methods-comparison-cell", "compare_single_multiple", "En_single_multiple ="),
            marker("multiple-result-response", "multiple_result_comment", "multiple-result-response"),
            marker("conclusion-cell", "final_conclusion", "lens-final-conclusion-response"),
            marker("limitations-cell", "method_limitations", "lens-final-conclusion-response"),
        ),
        "Marqueurs dérivés des cellules du support Lentille réel.",
    )


def _quantities(plan: ScientificProductionPlan) -> QuantityExpectationSet:
    required = PresenceRequirement.REQUIRED
    optional = PresenceRequirement.OPTIONAL
    ignored = PresenceRequirement.IGNORE
    return QuantityExpectationSet(
        plan,
        (
            ExpectedQuantity("single_focal_length", "f_1", ("f1", "f' par mesure unique"), "cm", (), required, required),
            ExpectedQuantity("theoretical_focal_length", "f_th", ("Valeur attendue",), "cm", (), required, required),
            ExpectedQuantity("conjugation_slope", "a", ("pente",), None, (), ignored, optional),
            ExpectedQuantity("focal_intercept", "b", ("Ordonnée à l'origine b", "ordonnée à l'origine", "ordonnee a l origine"), "cm^-1", (), optional, optional),
            ExpectedQuantity("theoretical_slope", "a_th", ("pente théorique",), None, (), ignored, ignored),
            ExpectedQuantity("multiple_focal_length", "f_2", ("f2", "f' moyen"), "cm", (), required, required),
        ),
    )


def _relations() -> ExpectationSet:
    return ExpectationSet(
        "thin-lens-image-relations",
        "Relations attendues — Lentille mince",
        relations=(
            ExpectedRelation(
                "conjugation_relation",
                "Relation de conjugaison",
                "1/OA' - 1/OA = 1/f'",
                ("1/OA' = 1/OA + 1/f'",),
            ),
        ),
    )


def _graphs(plan: ScientificProductionPlan) -> GraphExpectationSet:
    return GraphExpectationSet(
        plan,
        (
            GraphExpectation(
                "conjugation_graph",
                "1/OA",
                "1/OA'",
                ("1/OA", "1/OA (inverse object distance)"),
                ("1/OA'", "1/OA' (inverse image distance)"),
                True,
                "conjugation_slope",
                None,
                "conjugation_relation",
                False,
                True,
                "Graphe de 1/OA' en fonction de 1/OA ; pente théorique 1 et intercept 1/f'.",
                ExpectedGraphModel.AFFINE,
            ),
        ),
    )


def _criterion(identifier, description, importance=SemanticCriterionImportance.REQUIRED):
    return SemanticCriterion(identifier, description, importance)


SEMANTIC_RESPONSE_EXPECTATIONS = (
    ExpectedSemanticResponse(
        "lens_identification", SemanticRole.INTERPRETATION,
        (
            _criterion("identification_objective", "Identifier la distinction expérimentale entre lentilles convergentes et divergentes comme objectif."),
            _criterion("converging_close_object_image", "Décrire l'image virtuelle droite et agrandie observée avec une lentille convergente proche."),
            _criterion("diverging_close_object_image", "Décrire l'image virtuelle droite et réduite observée avec une lentille divergente."),
            _criterion("sign_and_thickness", "Relier signe inscrit, épaisseur relative et nature convergente ou divergente."),
        ),
    ),
    ExpectedSemanticResponse(
        "real_image_protocol", SemanticRole.PROTOCOL,
        (
            _criterion("real_image_objective", "Identifier la formation d'une image réelle de bonne qualité comme objectif de la manipulation."),
            _criterion("own_annotated_diagram", "Présenter le schéma personnel annoté du montage objet-lentille-écran."),
            _criterion("condenser_adjustment", "Décrire le réglage du condenseur pour éclairer le centre de la lentille."),
            _criterion("sharpness_search", "Décrire la recherche d'une position donnant une image nette."),
            _criterion("alignment_precautions", "Préciser le centrage, la hauteur et la perpendicularité de la lentille."),
        ),
    ),
    ExpectedSemanticResponse(
        "gauss_observation", SemanticRole.INTERPRETATION,
        (
            _criterion("degraded_image_observation", "Décrire la dégradation ou les aberrations lorsque la lentille est décentrée ou inclinée."),
            _criterion("gauss_quality_conclusion", "Relier les conditions de Gauss à l'obtention d'une image de bonne qualité."),
        ),
    ),
    ExpectedSemanticResponse(
        "single_uncertainty_justification", SemanticRole.INTERPRETATION,
        (
            _criterion("single_measurement_objective", "Identifier la détermination de la distance focale par une mesure unique et sa comparaison à la théorie comme objectifs."),
            _criterion("object_position_uncertainty", "Justifier l'incertitude sur la position de l'objet."),
            _criterion("lens_position_uncertainty", "Justifier l'incertitude sur la position de la lentille."),
            _criterion("screen_position_uncertainty", "Justifier l'incertitude sur la position de l'écran en tenant compte de la plage de netteté."),
        ),
    ),
    ExpectedSemanticResponse(
        "single_result_comment", SemanticRole.INTERPRETATION,
        (
            _criterion("single_result_with_uncertainty", "Donner la distance focale issue de la mesure unique avec son incertitude et un arrondi cohérent."),
            _criterion("single_theory_normalized_error", "Utiliser l'écart normalisé et le seuil 2 pour comparer à la valeur théorique."),
            _criterion("single_measurement_limitation", "Discuter une limite de la mesure unique.", SemanticCriterionImportance.RECOMMENDED),
        ),
    ),
    ExpectedSemanticResponse(
        "multiple_protocol", SemanticRole.PROTOCOL,
        (
            _criterion("multiple_measurement_objective", "Identifier la validation graphique de la relation de conjugaison et une détermination statistique de la distance focale comme objectifs."),
            _criterion("several_screen_positions", "Prévoir plusieurs positions de l'écran."),
            _criterion("two_lens_positions", "Rechercher les deux positions de lentille donnant une image nette lorsque cela est possible."),
            _criterion("about_ten_pairs", "Prévoir environ dix couples de positions."),
            _criterion("consistent_alignment_sharpness", "Conserver l'alignement et un critère de netteté cohérent."),
        ),
    ),
    ExpectedSemanticResponse(
        "graph_analysis", SemanticRole.INTERPRETATION,
        (
            _criterion("point_alignment", "Examiner l'alignement des points expérimentaux."),
            _criterion("unit_slope", "Comparer la pente expérimentale à la valeur théorique 1."),
            _criterion("intercept_as_inverse_focal", "Interpréter l'ordonnée à l'origine comme l'inverse de la distance focale."),
            _criterion("validate_conjugation", "Conclure sur la validation de la relation de conjugaison."),
        ),
    ),
    ExpectedSemanticResponse(
        "multiple_result_comment", SemanticRole.INTERPRETATION,
        (
            _criterion("multiple_result_with_uncertainty", "Donner la distance focale moyenne avec son incertitude."),
            _criterion("both_normalized_errors", "Interpréter les comparaisons à la théorie et à la mesure unique avec les écarts normalisés et le seuil 2."),
            _criterion("method_precision_comparison", "Comparer la précision et la fiabilité des deux méthodes."),
        ),
    ),
    ExpectedSemanticResponse(
        "final_conclusion", SemanticRole.CONCLUSION,
        (
            _criterion("quality_real_image", "Conclure sur la formation d'une image réelle de bonne qualité."),
            _criterion("conjugation_validation", "Conclure sur la validation expérimentale de la relation de conjugaison."),
            _criterion("retained_focal_length", "Présenter la distance focale finalement retenue avec son incertitude."),
            _criterion("limitations_and_improvement", "Mentionner les principales limites et une amélioration possible."),
        ),
    ),
)


def thin_lens_teacher_project() -> TeacherProjectConfiguration:
    """Build the explicit, immutable Lentille teacher configuration."""
    plan = _plan()
    quantities = _quantities(plan)
    comparisons = QuantityComparisonExpectationSet(
        plan, quantities,
        (
            ExpectedQuantityComparison("compare_single_theory", "single_focal_length", "theoretical_focal_length"),
            ExpectedQuantityComparison("compare_conjugation", "conjugation_slope", "theoretical_slope"),
            ExpectedQuantityComparison("compare_multiple_theory", "multiple_focal_length", "theoretical_focal_length"),
            ExpectedQuantityComparison("compare_single_multiple", "single_focal_length", "multiple_focal_length"),
        ),
    )
    interpretations = ComparisonInterpretationExpectationSet(
        comparisons,
        tuple(ExpectedComparisonInterpretation(
            item.production_id,
            ((ComparisonInterpretationKind.COHERENT, "Les mesures sont compatibles"),
             (ComparisonInterpretationKind.COHERENT, "les résultats sont compatibles"),
             (ComparisonInterpretationKind.INCOHERENT, "Les mesures ne sont pas compatibles"),
             (ComparisonInterpretationKind.INCOHERENT, "les résultats ne sont pas compatibles")),
        ) for item in comparisons),
    )
    errors = StudentNormalizedErrorExpectationSet(
        comparisons,
        (
            ExpectedStudentNormalizedError("compare_single_theory", ("En_single_theory", "E_n", "En"), Decimal("0.05")),
            ExpectedStudentNormalizedError("compare_multiple_theory", ("En_multiple_theory", "E_n", "En"), Decimal("0.05")),
            ExpectedStudentNormalizedError("compare_single_multiple", ("En_single_multiple", "E_n", "En"), Decimal("0.05")),
        ),
    )
    justifications = ComparisonJustificationExpectationSet(
        comparisons,
        tuple(ExpectedComparisonJustification(
            comparison_id,
            (ExpectedComparisonJustificationElement(
                "normalized_error_value", ComparisonJustificationElementKind.NORMALIZED_ERROR_VALUE,
                ComparisonJustificationRequirement.REQUIRED,
                (label + " =", "E_n =", "En ="),
            ),),
        ) for comparison_id, label in (
            ("compare_single_theory", "En_single_theory"),
            ("compare_multiple_theory", "En_multiple_theory"),
            ("compare_single_multiple", "En_single_multiple"),
        )),
    )
    project = TeacherProjectConfiguration(
        TeacherProjectIdentity(
            "thin-lens-image",
            "Formation d'une image par une lentille mince",
            "Physique", "Lycée", "A79f1", "fr",
            "Configuration déclarative du notebook aligné avec l'énoncé TeX.",
        ),
        (
            NotebookReference("statement", NotebookReferenceRole.STATEMENT, "Formation-dune-image-par-une-lentille-mince.ipynb"),
            NotebookReference("correction", NotebookReferenceRole.CORRECTION, "Correction-Formation-dune-image-par-une-lentille-mince.ipynb"),
            NotebookReference("control-copy", NotebookReferenceRole.CONTROL_COPY, "TP_physique_2_Galaad-Louis_Louis[]Galaad.ipynb"),
        ),
        plan,
        _bindings(plan),
        quantities,
        _relations(),
        None,
        _graphs(plan),
        comparisons,
        errors,
        interpretations,
        justifications,
        (
            french_quantity_feedback_catalog(),
            french_quantity_comparison_feedback_catalog(),
            french_comparison_interpretation_feedback_catalog(),
            french_comparison_justification_feedback_catalog(),
        ),
        "Projet Lentille réel : y = 1/OA' et x = 1/OA, relation affine.",
        semantic_response_expectations=SEMANTIC_RESPONSE_EXPECTATIONS,
    )
    validate_teacher_project_configuration(project)
    return project
