"""Configurable feedback for structured quantity comparison diagnostics."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

from tpstudio.diagnostics.quantity_comparisons import (
    QuantityComparisonDiagnostic,
    QuantityComparisonDiagnosticCode,
    QuantityComparisonDiagnosticSet,
)
from tpstudio.evaluation.quantity_comparisons import (
    QuantityComparisonNotEvaluableReason,
)
from tpstudio.expectations.quantity_comparisons import (
    ComparisonPedagogicalContext,
)

from .models import FeedbackAudience, FeedbackPriority


@dataclass(frozen=True, slots=True)
class QuantityComparisonFeedbackTemplate:
    """Configured wording for one code, audience and optional context."""

    code: QuantityComparisonDiagnosticCode
    audience: FeedbackAudience
    priority: FeedbackPriority
    text: str
    pedagogical_context: ComparisonPedagogicalContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, QuantityComparisonDiagnosticCode):
            raise TypeError("Le code doit être un QuantityComparisonDiagnosticCode.")
        if not isinstance(self.audience, FeedbackAudience):
            raise TypeError("Le destinataire doit être un FeedbackAudience.")
        if not isinstance(self.priority, FeedbackPriority):
            raise TypeError("La priorité doit être une FeedbackPriority.")
        if not isinstance(self.text, str):
            raise TypeError("Le texte doit être une chaîne.")
        if not self.text.strip():
            raise ValueError("Le texte de feedback ne peut pas être vide.")
        if self.pedagogical_context is not None and not isinstance(
            self.pedagogical_context, ComparisonPedagogicalContext
        ):
            raise TypeError("Le contexte doit être un ComparisonPedagogicalContext ou None.")


@dataclass(frozen=True, slots=True)
class QuantityComparisonFeedbackCatalog:
    """Explicit templates with exact-context then generic resolution."""

    templates: tuple[QuantityComparisonFeedbackTemplate, ...]

    def __post_init__(self) -> None:
        templates = tuple(self.templates)
        if not templates:
            raise ValueError("Un catalogue doit contenir au moins un template.")
        if any(not isinstance(item, QuantityComparisonFeedbackTemplate) for item in templates):
            raise TypeError("Chaque entrée doit être un QuantityComparisonFeedbackTemplate.")
        keys = tuple(
            (item.code, item.audience, item.pedagogical_context) for item in templates
        )
        if len(keys) != len(set(keys)):
            raise ValueError("Chaque combinaison code, audience et contexte doit être unique.")
        object.__setattr__(self, "templates", templates)

    def __iter__(self) -> Iterator[QuantityComparisonFeedbackTemplate]:
        return iter(self.templates)

    def __len__(self) -> int:
        return len(self.templates)

    def get_exact(
        self,
        code: QuantityComparisonDiagnosticCode,
        audience: FeedbackAudience,
        pedagogical_context: ComparisonPedagogicalContext | None,
    ) -> QuantityComparisonFeedbackTemplate | None:
        if not isinstance(code, QuantityComparisonDiagnosticCode):
            raise TypeError("Le code doit être un QuantityComparisonDiagnosticCode.")
        if not isinstance(audience, FeedbackAudience):
            raise TypeError("Le destinataire doit être un FeedbackAudience.")
        if pedagogical_context is not None and not isinstance(
            pedagogical_context, ComparisonPedagogicalContext
        ):
            raise TypeError("Le contexte doit être un ComparisonPedagogicalContext ou None.")
        return next(
            (
                item
                for item in self.templates
                if item.code is code
                and item.audience is audience
                and item.pedagogical_context is pedagogical_context
            ),
            None,
        )

    def resolve(
        self,
        code: QuantityComparisonDiagnosticCode,
        audience: FeedbackAudience,
        pedagogical_context: ComparisonPedagogicalContext,
    ) -> QuantityComparisonFeedbackTemplate | None:
        if not isinstance(pedagogical_context, ComparisonPedagogicalContext):
            raise TypeError("Le contexte doit être un ComparisonPedagogicalContext.")
        return self.get_exact(code, audience, pedagogical_context) or self.get_exact(
            code, audience, None
        )


@dataclass(frozen=True, slots=True)
class QuantityComparisonFeedbackItem:
    """Configured feedback retaining its complete diagnostic source."""

    diagnostic: QuantityComparisonDiagnostic
    template: QuantityComparisonFeedbackTemplate

    def __post_init__(self) -> None:
        if not isinstance(self.diagnostic, QuantityComparisonDiagnostic):
            raise TypeError("Le diagnostic doit être un QuantityComparisonDiagnostic.")
        if not isinstance(self.template, QuantityComparisonFeedbackTemplate):
            raise TypeError("Le template doit être un QuantityComparisonFeedbackTemplate.")
        if self.template.code is not self.diagnostic.code:
            raise ValueError("Le template ne correspond pas au diagnostic.")
        if (
            self.template.pedagogical_context is not None
            and self.template.pedagogical_context
            is not self.diagnostic.pedagogical_context
        ):
            raise ValueError("Le contexte du template ne correspond pas au diagnostic.")

    @property
    def production_id(self) -> str:
        return self.diagnostic.production_id

    @property
    def code(self) -> QuantityComparisonDiagnosticCode:
        return self.diagnostic.code

    @property
    def audience(self) -> FeedbackAudience:
        return self.template.audience

    @property
    def priority(self) -> FeedbackPriority:
        return self.template.priority

    @property
    def text(self) -> str:
        return self.template.text

    @property
    def pedagogical_context(self) -> ComparisonPedagogicalContext:
        return self.diagnostic.pedagogical_context

    @property
    def normalized_error(self) -> Decimal | None:
        return self.diagnostic.normalized_error

    @property
    def not_evaluable_reasons(
        self,
    ) -> tuple[QuantityComparisonNotEvaluableReason, ...]:
        return self.diagnostic.not_evaluable_reasons


def _derive_feedback(
    diagnostic_set: QuantityComparisonDiagnosticSet,
    catalog: QuantityComparisonFeedbackCatalog,
) -> tuple[QuantityComparisonFeedbackItem, ...]:
    if not isinstance(diagnostic_set, QuantityComparisonDiagnosticSet):
        raise TypeError("Les diagnostics doivent former un QuantityComparisonDiagnosticSet.")
    if not isinstance(catalog, QuantityComparisonFeedbackCatalog):
        raise TypeError("Le catalogue doit être un QuantityComparisonFeedbackCatalog.")
    items: list[QuantityComparisonFeedbackItem] = []
    for diagnostic in diagnostic_set:
        for audience in (FeedbackAudience.STUDENT, FeedbackAudience.TEACHER):
            template = catalog.resolve(
                diagnostic.code, audience, diagnostic.pedagogical_context
            )
            if template is not None:
                items.append(QuantityComparisonFeedbackItem(diagnostic, template))
    return tuple(items)


@dataclass(frozen=True, slots=True)
class QuantityComparisonFeedbackSet:
    """Ordered configured feedback retaining its diagnostic set."""

    diagnostic_set: QuantityComparisonDiagnosticSet
    feedback: tuple[QuantityComparisonFeedbackItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.diagnostic_set, QuantityComparisonDiagnosticSet):
            raise TypeError("Les diagnostics doivent former un QuantityComparisonDiagnosticSet.")
        feedback = tuple(self.feedback)
        if any(not isinstance(item, QuantityComparisonFeedbackItem) for item in feedback):
            raise TypeError("Chaque élément doit être un QuantityComparisonFeedbackItem.")
        object.__setattr__(self, "feedback", feedback)
        diagnostics = tuple(self.diagnostic_set)
        if any(
            not any(item.diagnostic is diagnostic for diagnostic in diagnostics)
            for item in feedback
        ):
            raise ValueError("Chaque feedback doit réutiliser un diagnostic du set.")
        keys = tuple((id(item.diagnostic), item.audience) for item in feedback)
        if len(keys) != len(set(keys)):
            raise ValueError("Un diagnostic ne peut produire qu'un feedback par audience.")
        positions = {id(item): index for index, item in enumerate(diagnostics)}
        audience_order = {FeedbackAudience.STUDENT: 0, FeedbackAudience.TEACHER: 1}
        order = tuple(
            (positions[id(item.diagnostic)], audience_order[item.audience])
            for item in feedback
        )
        if order != tuple(sorted(order)):
            raise ValueError("L'ordre doit suivre les diagnostics puis les audiences.")

    def __iter__(self) -> Iterator[QuantityComparisonFeedbackItem]:
        return iter(self.feedback)

    def __len__(self) -> int:
        return len(self.feedback)

    def for_production(self, production_id: str) -> tuple[QuantityComparisonFeedbackItem, ...]:
        return tuple(item for item in self.feedback if item.production_id == production_id)

    def for_audience(self, audience: FeedbackAudience) -> tuple[QuantityComparisonFeedbackItem, ...]:
        if not isinstance(audience, FeedbackAudience):
            raise TypeError("Le destinataire doit être un FeedbackAudience.")
        return tuple(item for item in self.feedback if item.audience is audience)

    def for_code(self, code: QuantityComparisonDiagnosticCode) -> tuple[QuantityComparisonFeedbackItem, ...]:
        if not isinstance(code, QuantityComparisonDiagnosticCode):
            raise TypeError("Le code doit être un QuantityComparisonDiagnosticCode.")
        return tuple(item for item in self.feedback if item.code is code)

    @property
    def student_feedback(self) -> tuple[QuantityComparisonFeedbackItem, ...]:
        return self.for_audience(FeedbackAudience.STUDENT)

    @property
    def teacher_feedback(self) -> tuple[QuantityComparisonFeedbackItem, ...]:
        return self.for_audience(FeedbackAudience.TEACHER)

    @property
    def has_student_feedback(self) -> bool:
        return bool(self.student_feedback)

    @property
    def has_teacher_feedback(self) -> bool:
        return bool(self.teacher_feedback)

    @property
    def has_feedback(self) -> bool:
        return bool(self.feedback)


class QuantityComparisonFeedbackRenderer:
    """Render exact contextual or generic configured feedback."""

    def render(
        self,
        diagnostic_set: QuantityComparisonDiagnosticSet,
        catalog: QuantityComparisonFeedbackCatalog,
    ) -> QuantityComparisonFeedbackSet:
        return QuantityComparisonFeedbackSet(
            diagnostic_set, _derive_feedback(diagnostic_set, catalog)
        )


def render_quantity_comparison_feedback(
    diagnostic_set: QuantityComparisonDiagnosticSet,
    catalog: QuantityComparisonFeedbackCatalog,
) -> QuantityComparisonFeedbackSet:
    """Delegate to the stateless comparison feedback renderer."""

    return QuantityComparisonFeedbackRenderer().render(diagnostic_set, catalog)


def french_quantity_comparison_feedback_catalog() -> QuantityComparisonFeedbackCatalog:
    """Return a fresh explicit French comparison feedback catalog."""

    moderate = QuantityComparisonDiagnosticCode.COMPARISON_MODERATELY_INCOHERENT
    strong = QuantityComparisonDiagnosticCode.COMPARISON_STRONGLY_INCOHERENT
    unavailable = QuantityComparisonDiagnosticCode.COMPARISON_NOT_EVALUABLE
    limitation = ComparisonPedagogicalContext.METHOD_LIMITATION_EXPECTED
    return QuantityComparisonFeedbackCatalog(
        (
            QuantityComparisonFeedbackTemplate(
                moderate,
                FeedbackAudience.STUDENT,
                FeedbackPriority.NORMAL,
                "Les deux résultats ne sont pas cohérents au regard des incertitudes annoncées. Calculez ou vérifiez l’écart normalisé, puis interprétez cet écart.",
            ),
            QuantityComparisonFeedbackTemplate(
                strong,
                FeedbackAudience.STUDENT,
                FeedbackPriority.HIGH,
                "Les deux résultats présentent une forte incohérence. Vérifiez les valeurs et les incertitudes, puis discutez la fiabilité des méthodes et les biais expérimentaux possibles.",
            ),
            QuantityComparisonFeedbackTemplate(
                strong,
                FeedbackAudience.STUDENT,
                FeedbackPriority.HIGH,
                "Les deux résultats présentent une forte incohérence, qui peut être liée à la limitation de méthode étudiée dans ce TP. Appuyez clairement votre conclusion sur le calcul de l’écart normalisé.",
                limitation,
            ),
            QuantityComparisonFeedbackTemplate(
                strong,
                FeedbackAudience.TEACHER,
                FeedbackPriority.NORMAL,
                "Une forte incohérence était pédagogiquement plausible dans ce TP. Examiner surtout si l’étudiant l’a identifiée, calculée et correctement interprétée.",
                limitation,
            ),
            QuantityComparisonFeedbackTemplate(
                unavailable,
                FeedbackAudience.TEACHER,
                FeedbackPriority.NORMAL,
                "La comparaison n’a pas pu être évaluée automatiquement à partir des résultats quantitatifs disponibles.",
            ),
        )
    )
