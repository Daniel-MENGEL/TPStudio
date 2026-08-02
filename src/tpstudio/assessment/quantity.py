"""Orchestration of the complete assessment of one textual quantity."""

from __future__ import annotations

from dataclasses import dataclass

from tpstudio.diagnostics import (
    QuantityDiagnostic,
    QuantityDiagnosticSet,
    build_quantity_diagnostics,
)
from tpstudio.evaluation import (
    QuantityStructuralEvaluation,
    QuantityUncertaintyEvaluation,
    evaluate_quantity_structure,
    evaluate_quantity_uncertainty,
)
from tpstudio.expectations import (
    ExpectedQuantity,
    QuantityExpectationSet,
    ScientificProductionSpec,
    UncertaintyQualityExpectationSet,
)
from tpstudio.feedback import (
    QuantityFeedbackCatalog,
    QuantityFeedbackItem,
    QuantityFeedbackSet,
    render_quantity_feedback,
)
from tpstudio.reasoning import (
    QuantityDetection,
    QuantityObservation,
    extract_expected_quantity,
)


@dataclass(frozen=True, slots=True)
class QuantityAssessmentResult:
    """Auditable results of assessing one expected textual quantity."""

    quantity_expectation_set: QuantityExpectationSet
    expectation: ExpectedQuantity
    detection: QuantityDetection
    structural_evaluation: QuantityStructuralEvaluation
    uncertainty_evaluation: QuantityUncertaintyEvaluation | None
    diagnostic_set: QuantityDiagnosticSet
    feedback_set: QuantityFeedbackSet | None

    def __post_init__(self) -> None:
        if not isinstance(self.quantity_expectation_set, QuantityExpectationSet):
            raise TypeError("Les quantités doivent former un QuantityExpectationSet.")
        if not isinstance(self.expectation, ExpectedQuantity):
            raise TypeError("L'attendu doit être une ExpectedQuantity.")
        if not isinstance(self.detection, QuantityDetection):
            raise TypeError("La détection doit être une QuantityDetection.")
        if not isinstance(self.structural_evaluation, QuantityStructuralEvaluation):
            raise TypeError("L'évaluation structurelle doit être valide.")
        if self.uncertainty_evaluation is not None and not isinstance(
            self.uncertainty_evaluation, QuantityUncertaintyEvaluation
        ):
            raise TypeError("L'évaluation d'incertitude doit être valide ou absente.")
        if not isinstance(self.diagnostic_set, QuantityDiagnosticSet):
            raise TypeError("Les diagnostics doivent former un QuantityDiagnosticSet.")
        if self.feedback_set is not None and not isinstance(
            self.feedback_set, QuantityFeedbackSet
        ):
            raise TypeError("Les feedbacks doivent former un QuantityFeedbackSet.")

        registered = self.quantity_expectation_set.get(
            self.expectation.production_id
        )
        if registered is not self.expectation:
            raise ValueError("L'attendu doit appartenir au jeu de quantités.")
        if self.detection.expectation is not self.expectation:
            raise ValueError("La détection doit réutiliser exactement l'attendu.")
        if self.detection.production_id != self.expectation.production_id:
            raise ValueError("La détection ne correspond pas à la production attendue.")
        if self.structural_evaluation.detection is not self.detection:
            raise ValueError("L'évaluation structurelle doit réutiliser la détection.")
        if (
            self.structural_evaluation.expectation_set
            is not self.quantity_expectation_set
        ):
            raise ValueError("L'évaluation structurelle doit réutiliser les attentes.")
        if self.uncertainty_evaluation is not None:
            if (
                self.uncertainty_evaluation.structural_evaluation
                is not self.structural_evaluation
            ):
                raise ValueError(
                    "L'évaluation d'incertitude doit réutiliser l'évaluation structurelle."
                )
            if (
                self.uncertainty_evaluation.expectation_set.quantity_expectation_set
                is not self.quantity_expectation_set
            ):
                raise ValueError("Les jeux d'attendus de quantités sont incohérents.")
        if self.diagnostic_set.structural_evaluation is not self.structural_evaluation:
            raise ValueError("Les diagnostics doivent réutiliser l'évaluation structurelle.")
        if self.diagnostic_set.uncertainty_evaluation is not self.uncertainty_evaluation:
            raise ValueError("Les diagnostics doivent réutiliser l'évaluation d'incertitude.")
        if (
            self.feedback_set is not None
            and self.feedback_set.diagnostic_set is not self.diagnostic_set
        ):
            raise ValueError("Les feedbacks doivent réutiliser les diagnostics.")

    @property
    def production_id(self) -> str:
        return self.expectation.production_id

    @property
    def production_spec(self) -> ScientificProductionSpec:
        production = self.quantity_expectation_set.plan.get(self.production_id)
        if production is None:  # Protected by QuantityExpectationSet.
            raise ValueError("La production est absente du plan.")
        return production

    @property
    def selected_observation(self) -> QuantityObservation | None:
        return self.structural_evaluation.selected_observation

    @property
    def diagnostics(self) -> tuple[QuantityDiagnostic, ...]:
        return self.diagnostic_set.diagnostics

    @property
    def student_feedback(self) -> tuple[QuantityFeedbackItem, ...]:
        return self.feedback_set.student_items if self.feedback_set else ()

    @property
    def teacher_feedback(self) -> tuple[QuantityFeedbackItem, ...]:
        return self.feedback_set.teacher_items if self.feedback_set else ()

    @property
    def has_observation(self) -> bool:
        return self.selected_observation is not None

    @property
    def has_failures(self) -> bool:
        return self.diagnostic_set.has_failures

    @property
    def has_deferred(self) -> bool:
        return self.diagnostic_set.has_deferred

    @property
    def has_student_feedback(self) -> bool:
        return bool(self.student_feedback)

    @property
    def has_teacher_feedback(self) -> bool:
        return bool(self.teacher_feedback)

    @property
    def is_structurally_satisfied(self) -> bool:
        return self.structural_evaluation.satisfied


class QuantityAssessmentPipeline:
    """Run the validated quantity components for one production."""

    def assess(
        self,
        text: str,
        production_id: str,
        quantity_expectation_set: QuantityExpectationSet,
        uncertainty_expectation_set: UncertaintyQualityExpectationSet | None = None,
        feedback_catalog: QuantityFeedbackCatalog | None = None,
    ) -> QuantityAssessmentResult:
        if not isinstance(text, str):
            raise TypeError("Le texte étudiant doit être une chaîne.")
        if not isinstance(production_id, str):
            raise TypeError("L'identifiant de production doit être une chaîne.")
        if not production_id.strip():
            raise ValueError("L'identifiant de production ne peut pas être vide.")
        if not isinstance(quantity_expectation_set, QuantityExpectationSet):
            raise TypeError("Les quantités doivent former un QuantityExpectationSet.")
        if uncertainty_expectation_set is not None and not isinstance(
            uncertainty_expectation_set, UncertaintyQualityExpectationSet
        ):
            raise TypeError("La politique doit être un UncertaintyQualityExpectationSet.")
        if feedback_catalog is not None and not isinstance(
            feedback_catalog, QuantityFeedbackCatalog
        ):
            raise TypeError("Le catalogue doit être un QuantityFeedbackCatalog.")
        if (
            uncertainty_expectation_set is not None
            and uncertainty_expectation_set.quantity_expectation_set
            is not quantity_expectation_set
        ):
            raise ValueError("La politique et les quantités doivent partager le même jeu.")

        expectation = quantity_expectation_set.get(production_id)
        if expectation is None:
            raise ValueError(f"Production quantitative inconnue : {production_id!r}.")
        detection = extract_expected_quantity(text, expectation)
        structural_evaluation = evaluate_quantity_structure(
            detection, quantity_expectation_set
        )
        uncertainty_evaluation = None
        if (
            uncertainty_expectation_set is not None
            and uncertainty_expectation_set.get(production_id) is not None
        ):
            uncertainty_evaluation = evaluate_quantity_uncertainty(
                structural_evaluation, uncertainty_expectation_set
            )
        diagnostic_set = build_quantity_diagnostics(
            structural_evaluation, uncertainty_evaluation
        )
        feedback_set = (
            render_quantity_feedback(diagnostic_set, feedback_catalog)
            if feedback_catalog is not None
            else None
        )
        return QuantityAssessmentResult(
            quantity_expectation_set,
            expectation,
            detection,
            structural_evaluation,
            uncertainty_evaluation,
            diagnostic_set,
            feedback_set,
        )


def assess_quantity_text(
    text: str,
    production_id: str,
    quantity_expectation_set: QuantityExpectationSet,
    uncertainty_expectation_set: UncertaintyQualityExpectationSet | None = None,
    feedback_catalog: QuantityFeedbackCatalog | None = None,
) -> QuantityAssessmentResult:
    """Assess one textual quantity through :class:`QuantityAssessmentPipeline`."""

    return QuantityAssessmentPipeline().assess(
        text,
        production_id,
        quantity_expectation_set,
        uncertainty_expectation_set,
        feedback_catalog,
    )
