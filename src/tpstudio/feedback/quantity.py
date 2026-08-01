"""Configurable feedback rendering for structured quantity diagnostics."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from tpstudio.diagnostics import (
    QuantityDiagnostic,
    QuantityDiagnosticCode,
    QuantityDiagnosticSet,
)
from tpstudio.evaluation import EvaluationStatus
from tpstudio.reasoning.quantity_extraction import QuantityObservation

from .models import FeedbackAudience, FeedbackPriority


@dataclass(frozen=True, slots=True)
class QuantityFeedbackTemplate:
    """Exact configured wording for one quantity diagnostic code."""

    diagnostic_code: QuantityDiagnosticCode
    text: str
    audience: FeedbackAudience = FeedbackAudience.STUDENT
    priority: FeedbackPriority = FeedbackPriority.NORMAL
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.diagnostic_code, QuantityDiagnosticCode):
            raise TypeError("Le code doit être un QuantityDiagnosticCode.")
        if not self.text.strip():
            raise ValueError("Le texte de feedback ne peut pas être vide.")
        if not isinstance(self.audience, FeedbackAudience):
            raise TypeError("Le destinataire doit être un FeedbackAudience.")
        if not isinstance(self.priority, FeedbackPriority):
            raise TypeError("La priorité doit être une FeedbackPriority.")
        if (
            self.diagnostic_code
            is QuantityDiagnosticCode.UNCERTAINTY_JUSTIFICATION_DEFERRED
            and self.audience is not FeedbackAudience.TEACHER
        ):
            raise ValueError(
                "Un contrôle de justification différé est réservé au professeur."
            )


@dataclass(frozen=True, slots=True)
class QuantityFeedbackCatalog:
    """Immutable explicit catalog with at most one wording per code."""

    id: str
    title: str
    templates: tuple[QuantityFeedbackTemplate, ...]
    language: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("L'identifiant du catalogue ne peut pas être vide.")
        if not self.title.strip():
            raise ValueError("Le titre du catalogue ne peut pas être vide.")
        templates = tuple(self.templates)
        if not templates:
            raise ValueError("Un catalogue doit contenir au moins un template.")
        if any(not isinstance(item, QuantityFeedbackTemplate) for item in templates):
            raise TypeError("Chaque entrée doit être un QuantityFeedbackTemplate.")
        object.__setattr__(self, "templates", templates)
        codes = [item.diagnostic_code for item in templates]
        if len(codes) != len(set(codes)):
            raise ValueError("Un seul template est autorisé par code.")

    def __iter__(self) -> Iterator[QuantityFeedbackTemplate]:
        return iter(self.templates)

    def __len__(self) -> int:
        return len(self.templates)

    def get(
        self, code: QuantityDiagnosticCode
    ) -> QuantityFeedbackTemplate | None:
        for template in self.templates:
            if template.diagnostic_code is code:
                return template
        return None


@dataclass(frozen=True, slots=True)
class QuantityFeedbackItem:
    """Presentable wording retaining its complete source diagnostic."""

    diagnostic: QuantityDiagnostic
    template: QuantityFeedbackTemplate
    production_label: str

    def __post_init__(self) -> None:
        if not isinstance(self.diagnostic, QuantityDiagnostic):
            raise TypeError("Le diagnostic doit être un QuantityDiagnostic.")
        if not isinstance(self.template, QuantityFeedbackTemplate):
            raise TypeError("Le template doit être un QuantityFeedbackTemplate.")
        if self.template.diagnostic_code is not self.diagnostic.code:
            raise ValueError("Le template ne correspond pas au diagnostic.")
        if not self.production_label.strip():
            raise ValueError("Le libellé de production ne peut pas être vide.")

    @property
    def code(self) -> QuantityDiagnosticCode:
        return self.diagnostic.code

    @property
    def production_id(self) -> str:
        return self.diagnostic.production_id

    @property
    def message_key(self) -> str:
        return self.diagnostic.message_key

    @property
    def text(self) -> str:
        return self.template.text

    @property
    def audience(self) -> FeedbackAudience:
        return self.template.audience

    @property
    def priority(self) -> FeedbackPriority:
        return self.template.priority

    @property
    def observation(self) -> QuantityObservation | None:
        return self.diagnostic.observation

    @property
    def status(self) -> EvaluationStatus:
        return self.diagnostic.status


def _production_label(diagnostic_set: QuantityDiagnosticSet) -> str:
    plan = diagnostic_set.structural_evaluation.expectation_set.plan
    production = plan.get(diagnostic_set.production_id)
    if production is None:
        raise ValueError("La production diagnostiquée est absente du plan.")
    if not production.label.strip():
        raise ValueError("Le libellé de la production ne peut pas être vide.")
    return production.label


def _derive_items(
    diagnostic_set: QuantityDiagnosticSet,
    catalog: QuantityFeedbackCatalog,
) -> tuple[QuantityFeedbackItem, ...]:
    if not isinstance(diagnostic_set, QuantityDiagnosticSet):
        raise TypeError("Les diagnostics doivent former un QuantityDiagnosticSet.")
    if not isinstance(catalog, QuantityFeedbackCatalog):
        raise TypeError("Le catalogue doit être un QuantityFeedbackCatalog.")
    production_label = _production_label(diagnostic_set)
    return tuple(
        QuantityFeedbackItem(diagnostic, template, production_label)
        for diagnostic in diagnostic_set
        if (template := catalog.get(diagnostic.code)) is not None
    )


@dataclass(frozen=True, slots=True)
class QuantityFeedbackSet:
    """Immutable feedback items and the sources used to render them."""

    diagnostic_set: QuantityDiagnosticSet
    catalog: QuantityFeedbackCatalog
    items: tuple[QuantityFeedbackItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.diagnostic_set, QuantityDiagnosticSet):
            raise TypeError("Les diagnostics doivent former un QuantityDiagnosticSet.")
        if not isinstance(self.catalog, QuantityFeedbackCatalog):
            raise TypeError("Le catalogue doit être un QuantityFeedbackCatalog.")
        items = tuple(self.items)
        object.__setattr__(self, "items", items)
        if any(not isinstance(item, QuantityFeedbackItem) for item in items):
            raise TypeError("Chaque élément doit être un QuantityFeedbackItem.")
        if len({item.code for item in items}) != len(items):
            raise ValueError("Un code de feedback ne peut apparaître qu'une fois.")
        diagnostics = tuple(self.diagnostic_set)
        if any(
            item.production_id != self.production_id
            or not any(item.diagnostic is diagnostic for diagnostic in diagnostics)
            for item in items
        ):
            raise ValueError("Chaque item doit provenir du jeu de diagnostics.")
        if any(self.catalog.get(item.code) is not item.template for item in items):
            raise ValueError("Chaque item doit utiliser le template du catalogue.")
        expected = _derive_items(self.diagnostic_set, self.catalog)
        if items != expected:
            raise ValueError("Les feedbacks ne correspondent pas aux sources fournies.")

    @property
    def production_id(self) -> str:
        return self.diagnostic_set.production_id

    def __iter__(self) -> Iterator[QuantityFeedbackItem]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def get(self, code: QuantityDiagnosticCode) -> QuantityFeedbackItem | None:
        for item in self.items:
            if item.code is code:
                return item
        return None

    @property
    def student_items(self) -> tuple[QuantityFeedbackItem, ...]:
        return tuple(
            item for item in self.items
            if item.audience is FeedbackAudience.STUDENT
        )

    @property
    def teacher_items(self) -> tuple[QuantityFeedbackItem, ...]:
        return tuple(
            item for item in self.items
            if item.audience is FeedbackAudience.TEACHER
        )

    @property
    def high_priority_items(self) -> tuple[QuantityFeedbackItem, ...]:
        return tuple(
            item for item in self.items
            if item.priority is FeedbackPriority.HIGH
        )

    @property
    def is_empty(self) -> bool:
        return not self.items

    @property
    def has_student_feedback(self) -> bool:
        return bool(self.student_items)

    @property
    def has_teacher_feedback(self) -> bool:
        return bool(self.teacher_items)


class QuantityFeedbackRenderer:
    """Render configured feedback without fallback or reordering."""

    def render(
        self,
        diagnostic_set: QuantityDiagnosticSet,
        catalog: QuantityFeedbackCatalog,
    ) -> QuantityFeedbackSet:
        items = _derive_items(diagnostic_set, catalog)
        return QuantityFeedbackSet(diagnostic_set, catalog, items)


def render_quantity_feedback(
    diagnostic_set: QuantityDiagnosticSet,
    catalog: QuantityFeedbackCatalog,
) -> QuantityFeedbackSet:
    """Convenience wrapper around :class:`QuantityFeedbackRenderer`."""

    return QuantityFeedbackRenderer().render(diagnostic_set, catalog)


def french_quantity_feedback_catalog() -> QuantityFeedbackCatalog:
    """Return a fresh example French catalog for quantity diagnostics."""

    return QuantityFeedbackCatalog(
        id="quantity-feedback-fr",
        title="Feedback français pour les grandeurs numériques",
        language="fr",
        templates=(
            QuantityFeedbackTemplate(
                QuantityDiagnosticCode.QUANTITY_MISSING,
                "La grandeur attendue n’a pas été fournie.",
                priority=FeedbackPriority.HIGH,
            ),
            QuantityFeedbackTemplate(
                QuantityDiagnosticCode.UNIT_MISSING,
                "Précisez l’unité de la valeur indiquée.",
            ),
            QuantityFeedbackTemplate(
                QuantityDiagnosticCode.UNCERTAINTY_MISSING,
                "Précisez l’incertitude associée à cette valeur.",
                priority=FeedbackPriority.HIGH,
            ),
            QuantityFeedbackTemplate(
                QuantityDiagnosticCode.UNCERTAINTY_JUSTIFICATION_DEFERRED,
                "La justification de l’incertitude doit encore être vérifiée.",
                audience=FeedbackAudience.TEACHER,
            ),
            QuantityFeedbackTemplate(
                QuantityDiagnosticCode.UNCERTAINTY_NOT_STRICTLY_POSITIVE,
                "L’incertitude doit être strictement positive.",
                priority=FeedbackPriority.HIGH,
            ),
            QuantityFeedbackTemplate(
                QuantityDiagnosticCode.UNCERTAINTY_SIGNIFICANT_DIGITS_INVALID,
                "Le nombre de chiffres significatifs de l’incertitude n’est pas "
                "conforme à la consigne.",
                priority=FeedbackPriority.LOW,
            ),
            QuantityFeedbackTemplate(
                QuantityDiagnosticCode.UNCERTAINTY_DECIMAL_PLACE_MISMATCH,
                "Présentez la valeur et son incertitude au même rang décimal.",
                priority=FeedbackPriority.LOW,
            ),
        ),
    )
