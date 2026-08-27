"""Teacher configuration for the aligned optical-instruments focometry TP."""

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


STATEMENT_FILENAME = "Instruments-doptique-et-application-a-la-focometrie.ipynb"
CORRECTION_FILENAME = "Correction-Instruments-doptique-et-application-a-la-focometrie.ipynb"


def _criterion(
    identifier: str,
    description: str,
    importance: SemanticCriterionImportance = SemanticCriterionImportance.REQUIRED,
) -> SemanticCriterion:
    return SemanticCriterion(identifier, description, importance)


SEMANTIC_RESPONSE_EXPECTATIONS = (
    ExpectedSemanticResponse(
        "autocollimation_protocol",
        SemanticRole.PROTOCOL,
        (
            _criterion("autocollimation_objective", "Identifier la détermination de la distance focale de la lentille convergente +5 comme objectif."),
            _criterion("mirror_behind_lens", "Placer le miroir plan juste derrière la lentille, sur le même support."),
            _criterion("image_superposition", "Rechercher une image nette, de même taille et superposée à l'objet."),
            _criterion("position_measurements", "Relever les positions de l'objet et de la lentille."),
            _criterion("position_intervals", "Expliquer comment sont estimés les intervalles d'incertitude de position."),
        ),
    ),
    ExpectedSemanticResponse(
        "autocollimation_result_comment",
        SemanticRole.INTERPRETATION,
        (
            _criterion("autocollimation_result", "Donner la distance focale avec son incertitude et un arrondi cohérent."),
            _criterion("autocollimation_normalized_error", "Interpréter l'écart normalisé avec la valeur constructeur et le seuil 2."),
            _criterion("autocollimation_limit", "Discuter le critère de netteté ou de superposition comme limite expérimentale."),
        ),
    ),
    ExpectedSemanticResponse(
        "diverging_box_protocol",
        SemanticRole.PROTOCOL,
        (
            _criterion("diverging_objective", "Identifier la détermination de la distance focale de la lentille divergente −2 comme objectif."),
            _criterion("lens_association", "Associer la lentille divergente −2 à la lentille convergente +5."),
            _criterion("combined_autocollimation", "Mesurer la focale de l'ensemble convergent par autocollimation."),
            _criterion("vergence_subtraction", "Prévoir de soustraire la vergence +5 pour isoler celle de la lentille divergente."),
        ),
    ),
    ExpectedSemanticResponse(
        "diverging_box_result_comment",
        SemanticRole.INTERPRETATION,
        (
            _criterion("negative_focal_length", "Donner une distance focale négative avec son incertitude."),
            _criterion("diverging_normalized_error", "Interpréter l'écart normalisé avec la valeur constructeur et le seuil 2."),
            _criterion("indirect_method_limit", "Identifier le caractère indirect de la méthode ou l'association imparfaite des lentilles comme limite."),
        ),
    ),
    ExpectedSemanticResponse(
        "bessel_protocol",
        SemanticRole.PROTOCOL,
        (
            _criterion("bessel_objective", "Identifier la détermination de la focale de la lentille +3,3 par la méthode de Bessel comme objectif."),
            _criterion("fixed_object_screen", "Fixer l'objet et l'écran avec une distance supérieure à quatre fois la focale attendue."),
            _criterion("two_sharp_positions", "Rechercher les deux positions de lentille donnant une image nette."),
            _criterion("four_positions", "Relever les positions de l'objet, des deux positions de lentille et de l'écran."),
            _criterion("sharpness_intervals", "Estimer les intervalles de position à partir de la plage de netteté."),
        ),
    ),
    ExpectedSemanticResponse(
        "bessel_result_comment",
        SemanticRole.INTERPRETATION,
        (
            _criterion("bessel_condition", "Vérifier la condition D supérieure à quatre fois la distance focale."),
            _criterion("bessel_result", "Donner la distance focale de Bessel avec son incertitude."),
            _criterion("bessel_normalized_error", "Interpréter l'écart normalisé avec la valeur constructeur et le seuil 2."),
            _criterion("bessel_limit", "Discuter le repérage des deux positions de netteté comme limite."),
        ),
    ),
    ExpectedSemanticResponse(
        "collimator_protocol",
        SemanticRole.PROTOCOL,
        (
            _criterion("collimator_objective", "Identifier la mesure de la focale de la lentille +3,3 dans un faisceau parallèle comme objectif."),
            _criterion("parallel_beam", "Utiliser le collimateur préalablement réglé pour produire un faisceau parallèle."),
            _criterion("lens_screen_positions", "Relever les positions de la lentille et de l'écran lorsque l'image est nette."),
        ),
    ),
    ExpectedSemanticResponse(
        "collimator_result_comment",
        SemanticRole.INTERPRETATION,
        (
            _criterion("collimator_result", "Donner la distance focale au collimateur avec son incertitude."),
            _criterion("collimator_theory_comparison", "Interpréter la comparaison à la valeur constructeur."),
            _criterion("bessel_collimator_comparison", "Comparer les résultats de Bessel et du collimateur avec l'écart normalisé."),
            _criterion("collimator_limit", "Discuter l'influence du réglage du collimateur ou du critère de netteté."),
        ),
    ),
    ExpectedSemanticResponse(
        "final_conclusion",
        SemanticRole.CONCLUSION,
        (
            _criterion("reported_focal_lengths", "Présenter les distances focales mesurées avec leurs incertitudes."),
            _criterion("method_comparisons", "Résumer les comparaisons entre méthodes et avec les valeurs constructeur."),
            _criterion("method_domains", "Distinguer l'intérêt ou le domaine d'emploi des méthodes de focométrie utilisées."),
            _criterion("main_limitations", "Mentionner les principales limites expérimentales."),
            _criterion("optional_vff", "Mentionner le résultat au viseur si cette partie a été réalisée.", SemanticCriterionImportance.RECOMMENDED),
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

    def spec(identifier, label, kind, bases, depends_on=(), required=True):
        return ScientificProductionSpec(identifier, label, kind, bases, depends_on, required)

    return ScientificProductionPlan(
        "focometry-productions",
        "Productions scientifiques — Instruments d'optique et focométrie",
        (
            spec("autocollimation_protocol", "Protocole d'autocollimation", interpretation, (semantic,)),
            spec("autocollimation_focal_length", "Focale par autocollimation", quantity, (structural,)),
            spec("plus5_theoretical_focal_length", "Focale théorique +5", quantity, (structural,)),
            spec("compare_autocollimation_theory", "Comparaison autocollimation / constructeur", comparison, (cross,), ("autocollimation_focal_length", "plus5_theoretical_focal_length")),
            spec("autocollimation_result_comment", "Commentaire de l'autocollimation", interpretation, (semantic,), ("compare_autocollimation_theory",)),
            spec("diverging_box_protocol", "Protocole de la boîte de verre", interpretation, (semantic,)),
            spec("diverging_box_focal_length", "Focale divergente par boîte de verre", quantity, (structural,)),
            spec("minus2_theoretical_focal_length", "Focale théorique −2", quantity, (structural,)),
            spec("compare_diverging_box_theory", "Comparaison boîte de verre / constructeur", comparison, (cross,), ("diverging_box_focal_length", "minus2_theoretical_focal_length")),
            spec("diverging_box_result_comment", "Commentaire de la boîte de verre", interpretation, (semantic,), ("compare_diverging_box_theory",)),
            spec("bessel_protocol", "Protocole de Bessel", interpretation, (semantic,)),
            spec("bessel_focal_length", "Focale par Bessel", quantity, (structural,)),
            spec("plus33_theoretical_focal_length", "Focale théorique +3,3", quantity, (structural,)),
            spec("compare_bessel_theory", "Comparaison Bessel / constructeur", comparison, (cross,), ("bessel_focal_length", "plus33_theoretical_focal_length")),
            spec("bessel_result_comment", "Commentaire de Bessel", interpretation, (semantic,), ("compare_bessel_theory",)),
            spec("collimator_protocol", "Protocole au collimateur", interpretation, (semantic,)),
            spec("collimator_focal_length", "Focale au collimateur", quantity, (structural,)),
            spec("compare_collimator_theory", "Comparaison collimateur / constructeur", comparison, (cross,), ("collimator_focal_length", "plus33_theoretical_focal_length")),
            spec("compare_bessel_collimator", "Comparaison Bessel / collimateur", comparison, (cross,), ("bessel_focal_length", "collimator_focal_length")),
            spec("collimator_result_comment", "Commentaire du collimateur", interpretation, (semantic,), ("compare_collimator_theory", "compare_bessel_collimator")),
            spec("vff_focal_length", "Focale au viseur à frontale fixe", quantity, (structural,), required=False),
            spec("minus66_theoretical_focal_length", "Focale théorique −6,6", quantity, (structural,), required=False),
            spec("compare_vff_theory", "Comparaison viseur / constructeur", comparison, (cross,), ("vff_focal_length", "minus66_theoretical_focal_length"), required=False),
            spec("final_conclusion", "Conclusion générale", interpretation, (semantic,), ("collimator_result_comment",)),
        ),
        "Contrat aligné sur le TP de deux heures ; la mesure au viseur reste facultative.",
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
        "focometry-bindings",
        "Associations du TP de focométrie",
        plan,
        (
            _binding("autocollimation-protocol-response", "autocollimation_protocol", "autocollimation-protocol-response"),
            _binding("autocollimation-focal-cell", "autocollimation_focal_length", "f1 = f1_values.mean()"),
            _binding("plus5-theory-cell", "plus5_theoretical_focal_length", "f1_constructeur = 100 / 5"),
            _binding("autocollimation-comparison-cell", "compare_autocollimation_theory", "E_n_f1 = ecart_normalise"),
            _binding("autocollimation-result-response", "autocollimation_result_comment", "autocollimation-result-response"),
            _binding("diverging-box-protocol-response", "diverging_box_protocol", "diverging-box-protocol-response"),
            _binding("diverging-box-focal-cell", "diverging_box_focal_length", "f2 = f2_values.mean()"),
            _binding("minus2-theory-cell", "minus2_theoretical_focal_length", "f2_constructeur = 100 / (-2)"),
            _binding("diverging-box-comparison-cell", "compare_diverging_box_theory", "E_n_f2 = ecart_normalise"),
            _binding("diverging-box-result-response", "diverging_box_result_comment", "diverging-box-result-response"),
            _binding("bessel-protocol-response", "bessel_protocol", "bessel-protocol-response"),
            _binding("bessel-focal-cell", "bessel_focal_length", "f3_bessel = f3_bessel_values.mean()"),
            _binding("plus33-theory-cell", "plus33_theoretical_focal_length", "f3_constructeur = 100 / 3.3"),
            _binding("bessel-comparison-cell", "compare_bessel_theory", "E_n_bessel = ecart_normalise"),
            _binding("bessel-result-response", "bessel_result_comment", "bessel-result-response"),
            _binding("collimator-protocol-response", "collimator_protocol", "collimator-protocol-response"),
            _binding("collimator-focal-cell", "collimator_focal_length", "f3_collimateur = f3_collimateur_values.mean()"),
            _binding("collimator-comparison-cell", "compare_collimator_theory", "E_n_collimateur_constructeur = ecart_normalise"),
            _binding("methods-comparison-cell", "compare_bessel_collimator", "E_n_bessel_collimateur = ecart_normalise"),
            _binding("collimator-result-response", "collimator_result_comment", "collimator-result-response"),
            _binding("vff-focal-cell", "vff_focal_length", "f4 = f4_values.mean()"),
            _binding("minus66-theory-cell", "minus66_theoretical_focal_length", "f4_constructeur = 100 / (-6.6)"),
            _binding("vff-comparison-cell", "compare_vff_theory", "E_n_f4 = ecart_normalise"),
            _binding("final-conclusion-response", "final_conclusion", "focometry-final-conclusion-response"),
        ),
        "Les cellules du viseur sont facultatives mais leurs marqueurs restent stables.",
    )


def focometry_teacher_project() -> TeacherProjectConfiguration:
    """Build the immutable project configuration for the focometry TP."""
    plan = _plan()
    required = PresenceRequirement.REQUIRED
    optional = PresenceRequirement.OPTIONAL
    ignored = PresenceRequirement.IGNORE
    quantities = QuantityExpectationSet(
        plan,
        (
            ExpectedQuantity("autocollimation_focal_length", "f'_1", ("f1", "f'1"), "cm", (), required, required),
            ExpectedQuantity("plus5_theoretical_focal_length", "f'_{+5}", ("f1_constructeur", "Valeur constructeur"), "cm", (), required, ignored),
            ExpectedQuantity("diverging_box_focal_length", "f'_2", ("f2", "f'2"), "cm", (), required, required),
            ExpectedQuantity("minus2_theoretical_focal_length", "f'_{-2}", ("f2_constructeur", "Valeur constructeur"), "cm", (), required, ignored),
            ExpectedQuantity("bessel_focal_length", "f'_{Bessel}", ("f3_bessel", "f'3 par Bessel"), "cm", (), required, required),
            ExpectedQuantity("plus33_theoretical_focal_length", "f'_{+3,3}", ("f3_constructeur", "Valeur constructeur"), "cm", (), required, ignored),
            ExpectedQuantity("collimator_focal_length", "f'_{collimateur}", ("f3_collimateur", "f'3 au collimateur"), "cm", (), required, required),
            ExpectedQuantity("vff_focal_length", "f'_{VFF}", ("f4", "f'4 au viseur"), "cm", (), optional, optional),
            ExpectedQuantity("minus66_theoretical_focal_length", "f'_{-6,6}", ("f4_constructeur", "Valeur constructeur"), "cm", (), optional, ignored),
        ),
    )
    comparisons = QuantityComparisonExpectationSet(
        plan,
        quantities,
        (
            ExpectedQuantityComparison("compare_autocollimation_theory", "autocollimation_focal_length", "plus5_theoretical_focal_length", pedagogical_context=ComparisonPedagogicalContext.COHERENCE_EXPECTED),
            ExpectedQuantityComparison("compare_diverging_box_theory", "diverging_box_focal_length", "minus2_theoretical_focal_length", pedagogical_context=ComparisonPedagogicalContext.COHERENCE_EXPECTED),
            ExpectedQuantityComparison("compare_bessel_theory", "bessel_focal_length", "plus33_theoretical_focal_length", pedagogical_context=ComparisonPedagogicalContext.COHERENCE_EXPECTED),
            ExpectedQuantityComparison("compare_collimator_theory", "collimator_focal_length", "plus33_theoretical_focal_length", pedagogical_context=ComparisonPedagogicalContext.COHERENCE_EXPECTED),
            ExpectedQuantityComparison("compare_bessel_collimator", "bessel_focal_length", "collimator_focal_length", pedagogical_context=ComparisonPedagogicalContext.COHERENCE_EXPECTED),
            ExpectedQuantityComparison("compare_vff_theory", "vff_focal_length", "minus66_theoretical_focal_length", pedagogical_context=ComparisonPedagogicalContext.COHERENCE_EXPECTED),
        ),
    )
    student_errors = StudentNormalizedErrorExpectationSet(
        comparisons,
        tuple(
            ExpectedStudentNormalizedError(comparison_id, aliases, Decimal("0.05"))
            for comparison_id, aliases in (
                ("compare_autocollimation_theory", ("E_n_f1", "Écart normalisé")),
                ("compare_diverging_box_theory", ("E_n_f2", "Écart normalisé")),
                ("compare_bessel_theory", ("E_n_bessel", "Écart normalisé")),
                ("compare_collimator_theory", ("E_n_collimateur_constructeur", "Écart normalisé")),
                ("compare_bessel_collimator", ("E_n_bessel_collimateur", "Écart normalisé")),
                ("compare_vff_theory", ("E_n_f4", "Écart normalisé")),
            )
        ),
    )
    uncertainties = UncertaintyQualityExpectationSet(
        quantities,
        tuple(
            UncertaintyQualitySpec(identifier)
            for identifier in (
                "autocollimation_focal_length",
                "diverging_box_focal_length",
                "bessel_focal_length",
                "collimator_focal_length",
                "vff_focal_length",
            )
        ),
    )
    return TeacherProjectConfiguration(
        TeacherProjectIdentity(
            "optical-instruments-focometry",
            "Instruments d'optique et application à la focométrie",
            "Physique",
            "Lycée",
            "A79g1",
            "fr",
            "Méthodes de focométrie et réglage d'instruments optiques.",
        ),
        (
            NotebookReference("statement", NotebookReferenceRole.STATEMENT, STATEMENT_FILENAME),
            NotebookReference("correction", NotebookReferenceRole.CORRECTION, CORRECTION_FILENAME),
        ),
        plan,
        _bindings(plan),
        quantities,
        ExpectationSet("focometry-relations", "Relations attendues — Focométrie", relations=()),
        uncertainties,
        None,
        comparisons,
        student_errors,
        ComparisonInterpretationExpectationSet(comparisons, ()),
        ComparisonJustificationExpectationSet(comparisons, ()),
        (french_quantity_feedback_catalog(), french_quantity_comparison_feedback_catalog()),
        "Les valeurs du corrigé illustrent un jeu de mesures plausible et ne sont pas des cibles imposées aux binômes.",
        semantic_response_expectations=SEMANTIC_RESPONSE_EXPECTATIONS,
    )
