"""Configurable feedback for A70f interpretation diagnostics."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from tpstudio.diagnostics.comparison_interpretations import (
    ComparisonInterpretationDiagnostic,
    ComparisonInterpretationDiagnosticCode,
    ComparisonInterpretationDiagnosticSet,
)
from tpstudio.expectations.comparison_interpretations import ComparisonInterpretationKind
from tpstudio.expectations.quantity_comparisons import ComparisonPedagogicalContext

from .models import FeedbackAudience, FeedbackPriority


@dataclass(frozen=True, slots=True)
class ComparisonInterpretationFeedbackTemplate:
    code: ComparisonInterpretationDiagnosticCode
    audience: FeedbackAudience
    priority: FeedbackPriority
    text: str
    pedagogical_context: ComparisonPedagogicalContext | None = None
    observed_kind: ComparisonInterpretationKind | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not ComparisonInterpretationDiagnosticCode:
            raise TypeError("Le code est invalide.")
        if type(self.audience) is not FeedbackAudience:
            raise TypeError("Le destinataire est invalide.")
        if type(self.priority) is not FeedbackPriority:
            raise TypeError("La priorité est invalide.")
        if not isinstance(self.text, str):
            raise TypeError("Le texte doit être une chaîne.")
        if not self.text.strip():
            raise ValueError("Le texte ne peut pas être vide.")
        if self.pedagogical_context is not None and type(self.pedagogical_context) is not ComparisonPedagogicalContext:
            raise TypeError("Le contexte est invalide.")
        if self.observed_kind is not None and type(self.observed_kind) is not ComparisonInterpretationKind:
            raise TypeError("Le type observé est invalide.")


@dataclass(frozen=True, slots=True)
class ComparisonInterpretationFeedbackCatalog:
    templates: tuple[ComparisonInterpretationFeedbackTemplate, ...]

    def __post_init__(self) -> None:
        if isinstance(self.templates, (str, bytes)):
            raise TypeError("Les templates doivent former une collection ordonnée.")
        templates = tuple(self.templates)
        if not templates:
            raise ValueError("Un catalogue doit contenir au moins un template.")
        if any(type(item) is not ComparisonInterpretationFeedbackTemplate for item in templates):
            raise TypeError("Chaque entrée doit être exactement un template A70f.")
        keys = tuple((item.code, item.audience, item.pedagogical_context, item.observed_kind) for item in templates)
        if len(keys) != len(set(keys)):
            raise ValueError("Chaque clé de template doit être unique.")
        object.__setattr__(self, "templates", templates)

    def __iter__(self) -> Iterator[ComparisonInterpretationFeedbackTemplate]:
        return iter(self.templates)

    def __len__(self) -> int:
        return len(self.templates)

    def get_exact(self, code, audience, pedagogical_context, observed_kind) -> ComparisonInterpretationFeedbackTemplate | None:
        if type(code) is not ComparisonInterpretationDiagnosticCode:
            raise TypeError("Le code est invalide.")
        if type(audience) is not FeedbackAudience:
            raise TypeError("Le destinataire est invalide.")
        if pedagogical_context is not None and type(pedagogical_context) is not ComparisonPedagogicalContext:
            raise TypeError("Le contexte est invalide.")
        if observed_kind is not None and type(observed_kind) is not ComparisonInterpretationKind:
            raise TypeError("Le type observé est invalide.")
        return next((item for item in self.templates if (
            item.code is code and item.audience is audience
            and item.pedagogical_context is pedagogical_context
            and item.observed_kind is observed_kind
        )), None)

    def resolve(self, code, audience, pedagogical_context, observed_kind) -> ComparisonInterpretationFeedbackTemplate | None:
        if type(pedagogical_context) is not ComparisonPedagogicalContext:
            raise TypeError("Le contexte effectif est invalide.")
        if observed_kind is not None and type(observed_kind) is not ComparisonInterpretationKind:
            raise TypeError("Le type observé est invalide.")
        for context_key, kind_key in (
            (pedagogical_context, observed_kind),
            (pedagogical_context, None),
            (None, observed_kind),
            (None, None),
        ):
            if (template := self.get_exact(code, audience, context_key, kind_key)) is not None:
                return template
        return None


@dataclass(frozen=True, slots=True)
class ComparisonInterpretationFeedbackItem:
    diagnostic: ComparisonInterpretationDiagnostic
    template: ComparisonInterpretationFeedbackTemplate

    def __post_init__(self) -> None:
        if type(self.diagnostic) is not ComparisonInterpretationDiagnostic:
            raise TypeError("Le diagnostic est invalide.")
        if type(self.template) is not ComparisonInterpretationFeedbackTemplate:
            raise TypeError("Le template est invalide.")
        if self.template.code is not self.diagnostic.code:
            raise ValueError("Le template vise un autre code.")
        if self.template.pedagogical_context is not None and self.template.pedagogical_context is not self.diagnostic.pedagogical_context:
            raise ValueError("Le template vise un autre contexte.")
        if self.template.observed_kind is not None and self.template.observed_kind is not self.diagnostic.observed_kind:
            raise ValueError("Le template vise un autre type observé.")

    @property
    def comparison_id(self): return self.diagnostic.comparison_id
    @property
    def production_id(self): return self.diagnostic.production_id
    @property
    def code(self): return self.diagnostic.code
    @property
    def audience(self): return self.template.audience
    @property
    def priority(self): return self.template.priority
    @property
    def text(self): return self.template.text
    @property
    def status(self): return self.diagnostic.status
    @property
    def objective_status(self): return self.diagnostic.objective_status
    @property
    def observed_kind(self): return self.diagnostic.observed_kind
    @property
    def pedagogical_context(self): return self.diagnostic.pedagogical_context
    @property
    def student_normalized_error_status(self): return self.diagnostic.student_normalized_error_status
    @property
    def not_evaluable_reasons(self): return self.diagnostic.not_evaluable_reasons


def _derive_feedback(diagnostic_set, catalog) -> tuple[ComparisonInterpretationFeedbackItem, ...]:
    if type(diagnostic_set) is not ComparisonInterpretationDiagnosticSet:
        raise TypeError("Les diagnostics doivent former exactement un jeu A70f.")
    if type(catalog) is not ComparisonInterpretationFeedbackCatalog:
        raise TypeError("Le catalogue doit être exactement un catalogue A70f.")
    items = []
    for diagnostic in diagnostic_set:
        for audience in (FeedbackAudience.STUDENT, FeedbackAudience.TEACHER):
            template = catalog.resolve(diagnostic.code, audience, diagnostic.pedagogical_context, diagnostic.observed_kind)
            if template is not None:
                items.append(ComparisonInterpretationFeedbackItem(diagnostic, template))
    return tuple(items)


@dataclass(frozen=True, slots=True)
class ComparisonInterpretationFeedbackSet:
    diagnostic_set: ComparisonInterpretationDiagnosticSet
    feedback: tuple[ComparisonInterpretationFeedbackItem, ...]

    def __post_init__(self) -> None:
        if type(self.diagnostic_set) is not ComparisonInterpretationDiagnosticSet:
            raise TypeError("Les diagnostics doivent former exactement un jeu A70f.")
        if isinstance(self.feedback, (str, bytes)):
            raise TypeError("Les feedbacks doivent former une collection ordonnée.")
        feedback = tuple(self.feedback)
        if any(type(item) is not ComparisonInterpretationFeedbackItem for item in feedback):
            raise TypeError("Chaque élément doit être exactement un feedback A70f.")
        object.__setattr__(self, "feedback", feedback)
        diagnostics = tuple(self.diagnostic_set)
        if any(not any(item.diagnostic is diagnostic for diagnostic in diagnostics) for item in feedback):
            raise ValueError("Chaque feedback doit réutiliser un diagnostic du set.")
        keys = tuple((id(item.diagnostic), item.audience) for item in feedback)
        if len(keys) != len(set(keys)):
            raise ValueError("Un diagnostic ne peut produire qu'un feedback par audience.")
        positions = {id(item): index for index, item in enumerate(diagnostics)}
        audience_order = {FeedbackAudience.STUDENT: 0, FeedbackAudience.TEACHER: 1}
        order = tuple((positions[id(item.diagnostic)], audience_order[item.audience]) for item in feedback)
        if order != tuple(sorted(order)):
            raise ValueError("L'ordre doit suivre les diagnostics puis les audiences.")

    def __iter__(self): return iter(self.feedback)
    def __len__(self): return len(self.feedback)
    def for_comparison(self, comparison_id): return tuple(item for item in self.feedback if item.comparison_id == comparison_id)
    def for_audience(self, audience):
        if type(audience) is not FeedbackAudience: raise TypeError("Le destinataire est invalide.")
        return tuple(item for item in self.feedback if item.audience is audience)
    def for_code(self, code):
        if type(code) is not ComparisonInterpretationDiagnosticCode: raise TypeError("Le code est invalide.")
        return tuple(item for item in self.feedback if item.code is code)
    def for_priority(self, priority):
        if type(priority) is not FeedbackPriority: raise TypeError("La priorité est invalide.")
        return tuple(item for item in self.feedback if item.priority is priority)
    @property
    def student_feedback(self): return self.for_audience(FeedbackAudience.STUDENT)
    @property
    def teacher_feedback(self): return self.for_audience(FeedbackAudience.TEACHER)
    @property
    def high_priority(self): return self.for_priority(FeedbackPriority.HIGH)
    @property
    def has_feedback(self): return bool(self.feedback)
    @property
    def has_student_feedback(self): return bool(self.student_feedback)
    @property
    def has_teacher_feedback(self): return bool(self.teacher_feedback)
    @property
    def has_high_priority_feedback(self): return bool(self.high_priority)


class ComparisonInterpretationFeedbackRenderer:
    def render(self, diagnostic_set, catalog) -> ComparisonInterpretationFeedbackSet:
        return ComparisonInterpretationFeedbackSet(diagnostic_set, _derive_feedback(diagnostic_set, catalog))


def render_comparison_interpretation_feedback(diagnostic_set, catalog) -> ComparisonInterpretationFeedbackSet:
    """Delegate to the stateless A70f feedback renderer."""
    return ComparisonInterpretationFeedbackRenderer().render(diagnostic_set, catalog)


def french_comparison_interpretation_feedback_catalog() -> ComparisonInterpretationFeedbackCatalog:
    partial = ComparisonInterpretationDiagnosticCode.INTERPRETATION_PARTIALLY_MATCHES
    contradicts = ComparisonInterpretationDiagnosticCode.INTERPRETATION_CONTRADICTS
    unavailable = ComparisonInterpretationDiagnosticCode.INTERPRETATION_NOT_EVALUABLE
    limitation = ComparisonPedagogicalContext.METHOD_LIMITATION_EXPECTED
    return ComparisonInterpretationFeedbackCatalog((
        ComparisonInterpretationFeedbackTemplate(partial, FeedbackAudience.STUDENT, FeedbackPriority.NORMAL, "Votre conclusion va dans le sens du résultat obtenu, mais elle ne distingue pas suffisamment le niveau d’incohérence mis en évidence par l’écart normalisé."),
        ComparisonInterpretationFeedbackTemplate(partial, FeedbackAudience.TEACHER, FeedbackPriority.LOW, "La conclusion est globalement orientée dans le bon sens, mais reste moins précise que le classement objectif."),
        ComparisonInterpretationFeedbackTemplate(contradicts, FeedbackAudience.STUDENT, FeedbackPriority.HIGH, "Votre conclusion ne correspond pas au classement donné par l’écart normalisé. Reprenez les seuils utilisés et reliez explicitement votre conclusion à la valeur calculée."),
        ComparisonInterpretationFeedbackTemplate(contradicts, FeedbackAudience.TEACHER, FeedbackPriority.HIGH, "La conclusion observée contredit le classement objectif associé à l’écart normalisé."),
        ComparisonInterpretationFeedbackTemplate(partial, FeedbackAudience.STUDENT, FeedbackPriority.NORMAL, "Vous avez identifié l’incohérence, mais la conclusion attendue doit aussi relier cet écart aux limites de la méthode étudiée.", limitation, ComparisonInterpretationKind.INCOHERENT),
        ComparisonInterpretationFeedbackTemplate(partial, FeedbackAudience.STUDENT, FeedbackPriority.NORMAL, "Vous avez identifié la forte incohérence. Complétez la conclusion en expliquant en quoi elle met en évidence la limite de la méthode étudiée.", limitation, ComparisonInterpretationKind.STRONGLY_INCOHERENT),
        ComparisonInterpretationFeedbackTemplate(unavailable, FeedbackAudience.TEACHER, FeedbackPriority.NORMAL, "L’interprétation de la comparaison n’a pas pu être évaluée automatiquement à partir du texte disponible."),
    ))
