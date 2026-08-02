"""Assessment of resolved textual quantities in an in-memory notebook."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from nbformat.notebooknode import NotebookNode

from tpstudio.diagnostics import QuantityDiagnostic
from tpstudio.expectations import (
    NotebookBindingPlan,
    QuantityExpectationSet,
    ScientificProductionKind,
    ScientificProductionSpec,
    UncertaintyQualityExpectationSet,
)
from tpstudio.feedback import QuantityFeedbackCatalog, QuantityFeedbackItem
from tpstudio.notebooks import (
    NotebookBindingResolution,
    NotebookBindingResolutionSet,
    resolve_notebook_bindings,
)

from .quantity import QuantityAssessmentResult, assess_quantity_text


class NotebookQuantityAssessmentStatus(str, Enum):
    """Whether one resolved quantity binding could be assessed."""

    ASSESSED = "assessed"
    RESOLUTION_FAILED = "resolution_failed"


@dataclass(frozen=True, slots=True)
class NotebookQuantityAssessmentItem:
    """Assessment outcome for one binding targeting a quantity."""

    resolution: NotebookBindingResolution
    production_spec: ScientificProductionSpec
    status: NotebookQuantityAssessmentStatus
    assessment: QuantityAssessmentResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resolution, NotebookBindingResolution):
            raise TypeError("La résolution doit être une NotebookBindingResolution.")
        if not isinstance(self.production_spec, ScientificProductionSpec):
            raise TypeError("La production doit être une ScientificProductionSpec.")
        if self.production_spec.kind is not ScientificProductionKind.QUANTITY:
            raise ValueError("L'item doit viser une production QUANTITY.")
        if self.production_spec.id != self.resolution.production_id:
            raise ValueError("La production ne correspond pas à la résolution.")
        if not isinstance(self.status, NotebookQuantityAssessmentStatus):
            raise TypeError("Le statut doit être un NotebookQuantityAssessmentStatus.")
        if self.assessment is not None and not isinstance(
            self.assessment, QuantityAssessmentResult
        ):
            raise TypeError("L'évaluation doit être un QuantityAssessmentResult ou None.")

        if self.status is NotebookQuantityAssessmentStatus.ASSESSED:
            if not self.resolution.resolved or not isinstance(self.resolution.text, str):
                raise ValueError("Une évaluation exige une résolution textuelle réussie.")
            if self.assessment is None:
                raise ValueError("Une résolution évaluée exige un résultat A69a.")
            if self.assessment.production_id != self.resolution.production_id:
                raise ValueError("L'évaluation ne correspond pas à la résolution.")
            if self.assessment.production_spec is not self.production_spec:
                raise ValueError("L'évaluation doit réutiliser la production du plan.")
        else:
            if not self.resolution.failed:
                raise ValueError("Un échec exige une résolution A69c en échec.")
            if self.assessment is not None:
                raise ValueError("Un échec de résolution ne possède aucune évaluation.")

    @property
    def binding_id(self) -> str:
        return self.resolution.binding_id

    @property
    def production_id(self) -> str:
        return self.resolution.production_id

    @property
    def assessed(self) -> bool:
        return self.status is NotebookQuantityAssessmentStatus.ASSESSED

    @property
    def resolution_failed(self) -> bool:
        return not self.assessed

    @property
    def diagnostics(self) -> tuple[QuantityDiagnostic, ...]:
        return self.assessment.diagnostics if self.assessment else ()

    @property
    def student_feedback(self) -> tuple[QuantityFeedbackItem, ...]:
        return self.assessment.student_feedback if self.assessment else ()

    @property
    def teacher_feedback(self) -> tuple[QuantityFeedbackItem, ...]:
        return self.assessment.teacher_feedback if self.assessment else ()

    @property
    def has_diagnostics(self) -> bool:
        return bool(self.diagnostics)

    @property
    def has_student_feedback(self) -> bool:
        return bool(self.student_feedback)

    @property
    def has_teacher_feedback(self) -> bool:
        return bool(self.teacher_feedback)


@dataclass(frozen=True, slots=True)
class NotebookQuantityAssessmentSet:
    """Ordered quantity assessments retaining the complete resolution set."""

    resolution_set: NotebookBindingResolutionSet
    items: tuple[NotebookQuantityAssessmentItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.resolution_set, NotebookBindingResolutionSet):
            raise TypeError("Les résolutions doivent former un NotebookBindingResolutionSet.")
        items = tuple(self.items)
        if any(not isinstance(item, NotebookQuantityAssessmentItem) for item in items):
            raise TypeError("Chaque item doit être un NotebookQuantityAssessmentItem.")
        object.__setattr__(self, "items", items)

        plan = self.resolution_set.binding_plan.production_plan
        expected_resolutions = tuple(
            resolution
            for resolution in self.resolution_set
            if (production := plan.get(resolution.production_id)) is not None
            and production.kind is ScientificProductionKind.QUANTITY
        )
        if len(items) != len(expected_resolutions):
            raise ValueError("Un item est requis pour chaque binding QUANTITY.")
        for item, resolution in zip(items, expected_resolutions):
            if item.resolution is not resolution:
                raise ValueError("Chaque item doit réutiliser sa résolution par identité.")
            production = plan.get(resolution.production_id)
            if item.production_spec is not production:
                raise ValueError("Chaque item doit réutiliser la production du plan.")

    def __iter__(self) -> Iterator[NotebookQuantityAssessmentItem]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def get(self, binding_id: str) -> NotebookQuantityAssessmentItem | None:
        for item in self.items:
            if item.binding_id == binding_id:
                return item
        return None

    def for_production(
        self, production_id: str
    ) -> tuple[NotebookQuantityAssessmentItem, ...]:
        """Return quantity items for one known production."""

        production = self.resolution_set.binding_plan.production_plan.get(production_id)
        if production is None:
            raise ValueError(f"Production inconnue : {production_id!r}.")
        if production.kind is not ScientificProductionKind.QUANTITY:
            return ()
        return tuple(item for item in self.items if item.production_id == production_id)

    def for_status(
        self, status: NotebookQuantityAssessmentStatus
    ) -> tuple[NotebookQuantityAssessmentItem, ...]:
        """Return items having one exact orchestration status."""

        if not isinstance(status, NotebookQuantityAssessmentStatus):
            raise TypeError("Le statut doit être un NotebookQuantityAssessmentStatus.")
        return tuple(item for item in self.items if item.status is status)

    @property
    def assessed(self) -> tuple[NotebookQuantityAssessmentItem, ...]:
        return self.for_status(NotebookQuantityAssessmentStatus.ASSESSED)

    @property
    def resolution_failures(self) -> tuple[NotebookQuantityAssessmentItem, ...]:
        return self.for_status(NotebookQuantityAssessmentStatus.RESOLUTION_FAILED)

    @property
    def all_assessed(self) -> bool:
        return not self.resolution_failures

    @property
    def has_resolution_failures(self) -> bool:
        return bool(self.resolution_failures)

    @property
    def assessments(self) -> tuple[QuantityAssessmentResult, ...]:
        return tuple(
            item.assessment for item in self.assessed if item.assessment is not None
        )

    @property
    def diagnostics(self) -> tuple[QuantityDiagnostic, ...]:
        return tuple(diagnostic for item in self.items for diagnostic in item.diagnostics)

    @property
    def student_feedback(self) -> tuple[QuantityFeedbackItem, ...]:
        return tuple(feedback for item in self.items for feedback in item.student_feedback)

    @property
    def teacher_feedback(self) -> tuple[QuantityFeedbackItem, ...]:
        return tuple(feedback for item in self.items for feedback in item.teacher_feedback)


class NotebookQuantityAssessmentPipeline:
    """Resolve and assess every bound quantity in an in-memory notebook."""

    def assess(
        self,
        notebook: NotebookNode,
        binding_plan: NotebookBindingPlan,
        quantity_expectation_set: QuantityExpectationSet,
        uncertainty_expectation_set: UncertaintyQualityExpectationSet | None = None,
        feedback_catalog: QuantityFeedbackCatalog | None = None,
    ) -> NotebookQuantityAssessmentSet:
        if not isinstance(notebook, NotebookNode):
            raise TypeError("Le notebook doit être un NotebookNode déjà chargé.")
        if not isinstance(binding_plan, NotebookBindingPlan):
            raise TypeError("Le plan doit être un NotebookBindingPlan.")
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
        if quantity_expectation_set.plan is not binding_plan.production_plan:
            raise ValueError("Les bindings et les quantités doivent partager le même plan.")
        if (
            uncertainty_expectation_set is not None
            and uncertainty_expectation_set.quantity_expectation_set
            is not quantity_expectation_set
        ):
            raise ValueError("La politique et les quantités doivent partager le même jeu.")
        for binding in binding_plan:
            production = binding_plan.production_plan.get(binding.production_id)
            assert production is not None
            if (
                production.kind is ScientificProductionKind.QUANTITY
                and quantity_expectation_set.get(binding.production_id) is None
            ):
                raise ValueError(
                    "Une production QUANTITY liée est absente du jeu de quantités : "
                    f"{binding.production_id!r}."
                )

        resolution_set = resolve_notebook_bindings(notebook, binding_plan)
        items: list[NotebookQuantityAssessmentItem] = []
        for resolution in resolution_set:
            production = binding_plan.production_plan.get(resolution.production_id)
            assert production is not None
            if production.kind is not ScientificProductionKind.QUANTITY:
                continue
            if resolution.failed:
                items.append(
                    NotebookQuantityAssessmentItem(
                        resolution,
                        production,
                        NotebookQuantityAssessmentStatus.RESOLUTION_FAILED,
                    )
                )
                continue
            assert isinstance(resolution.text, str)
            assessment = assess_quantity_text(
                resolution.text,
                resolution.production_id,
                quantity_expectation_set,
                uncertainty_expectation_set,
                feedback_catalog,
            )
            items.append(
                NotebookQuantityAssessmentItem(
                    resolution,
                    production,
                    NotebookQuantityAssessmentStatus.ASSESSED,
                    assessment,
                )
            )
        return NotebookQuantityAssessmentSet(resolution_set, tuple(items))


def assess_notebook_quantities(
    notebook: NotebookNode,
    binding_plan: NotebookBindingPlan,
    quantity_expectation_set: QuantityExpectationSet,
    uncertainty_expectation_set: UncertaintyQualityExpectationSet | None = None,
    feedback_catalog: QuantityFeedbackCatalog | None = None,
) -> NotebookQuantityAssessmentSet:
    """Delegate to :class:`NotebookQuantityAssessmentPipeline`."""

    return NotebookQuantityAssessmentPipeline().assess(
        notebook,
        binding_plan,
        quantity_expectation_set,
        uncertainty_expectation_set,
        feedback_catalog,
    )
