"""Configurable feedback for A70h justification diagnostics."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from tpstudio.diagnostics.comparison_justifications import (
    ComparisonJustificationDiagnostic, ComparisonJustificationDiagnosticCode,
    ComparisonJustificationDiagnosticSet,
)
from tpstudio.evaluation.comparison_interpretations import ComparisonInterpretationEvaluationStatus
from tpstudio.evaluation.comparison_justifications import ComparisonJustificationEvaluationStatus
from tpstudio.expectations.comparison_justifications import ComparisonJustificationRequirement
from tpstudio.expectations.quantity_comparisons import ComparisonPedagogicalContext

from .models import FeedbackAudience, FeedbackPriority


class ComparisonJustificationFeedbackVariant(str, Enum):
    GENERIC = "generic"
    REQUIRED_ELEMENTS_MISSING = "required_elements_missing"
    ALTERNATIVE_GROUPS_MISSING = "alternative_groups_missing"
    REQUIRED_AND_ALTERNATIVE_MISSING = "required_and_alternative_missing"
    OPTIONAL_ONLY = "optional_only"


def comparison_justification_feedback_variant(diagnostic):
    if type(diagnostic) is not ComparisonJustificationDiagnostic: raise TypeError("Le diagnostic est invalide.")
    if diagnostic.status is not ComparisonJustificationEvaluationStatus.PARTIAL: return ComparisonJustificationFeedbackVariant.GENERIC
    expectation = diagnostic.evaluation.expectation
    has_obligations = any(item.requirement is ComparisonJustificationRequirement.REQUIRED for item in expectation.elements) or any(item.requirement is ComparisonJustificationRequirement.ONE_OF_GROUP for item in expectation.elements)
    if not has_obligations: return ComparisonJustificationFeedbackVariant.OPTIONAL_ONLY
    if diagnostic.missing_required_element_ids and diagnostic.missing_alternative_groups: return ComparisonJustificationFeedbackVariant.REQUIRED_AND_ALTERNATIVE_MISSING
    if diagnostic.missing_required_element_ids: return ComparisonJustificationFeedbackVariant.REQUIRED_ELEMENTS_MISSING
    if diagnostic.missing_alternative_groups: return ComparisonJustificationFeedbackVariant.ALTERNATIVE_GROUPS_MISSING
    return ComparisonJustificationFeedbackVariant.GENERIC


@dataclass(frozen=True, slots=True)
class ComparisonJustificationFeedbackTemplate:
    code: ComparisonJustificationDiagnosticCode
    audience: FeedbackAudience
    priority: FeedbackPriority
    text: str
    variant: ComparisonJustificationFeedbackVariant = ComparisonJustificationFeedbackVariant.GENERIC
    pedagogical_context: ComparisonPedagogicalContext | None = None
    interpretation_status: ComparisonInterpretationEvaluationStatus | None = None

    def __post_init__(self):
        if type(self.code) is not ComparisonJustificationDiagnosticCode: raise TypeError("Le code est invalide.")
        if type(self.audience) is not FeedbackAudience: raise TypeError("Le destinataire est invalide.")
        if type(self.priority) is not FeedbackPriority: raise TypeError("La priorité est invalide.")
        if not isinstance(self.text, str): raise TypeError("Le texte doit être une chaîne.")
        if not self.text.strip(): raise ValueError("Le texte ne peut pas être vide.")
        if type(self.variant) is not ComparisonJustificationFeedbackVariant: raise TypeError("La variante est invalide.")
        if self.pedagogical_context is not None and type(self.pedagogical_context) is not ComparisonPedagogicalContext: raise TypeError("Le contexte est invalide.")
        if self.interpretation_status is not None and type(self.interpretation_status) is not ComparisonInterpretationEvaluationStatus: raise TypeError("Le statut A70e est invalide.")


@dataclass(frozen=True, slots=True)
class ComparisonJustificationFeedbackCatalog:
    templates: tuple[ComparisonJustificationFeedbackTemplate, ...]

    def __post_init__(self):
        if isinstance(self.templates, (str, bytes)): raise TypeError("Les templates doivent former une collection.")
        templates = tuple(self.templates)
        if not templates: raise ValueError("Un catalogue doit contenir un template.")
        if any(type(item) is not ComparisonJustificationFeedbackTemplate for item in templates): raise TypeError("Un template est invalide.")
        keys = tuple((item.code, item.audience, item.variant, item.pedagogical_context, item.interpretation_status) for item in templates)
        if len(keys) != len(set(keys)): raise ValueError("Les clés des templates doivent être uniques.")
        object.__setattr__(self, "templates", templates)

    def __iter__(self) -> Iterator[ComparisonJustificationFeedbackTemplate]: return iter(self.templates)
    def __len__(self): return len(self.templates)
    def get_exact(self, code, audience, variant, pedagogical_context, interpretation_status):
        if type(code) is not ComparisonJustificationDiagnosticCode: raise TypeError("Le code est invalide.")
        if type(audience) is not FeedbackAudience: raise TypeError("Le destinataire est invalide.")
        if type(variant) is not ComparisonJustificationFeedbackVariant: raise TypeError("La variante est invalide.")
        if pedagogical_context is not None and type(pedagogical_context) is not ComparisonPedagogicalContext: raise TypeError("Le contexte est invalide.")
        if interpretation_status is not None and type(interpretation_status) is not ComparisonInterpretationEvaluationStatus: raise TypeError("Le statut A70e est invalide.")
        return next((item for item in self.templates if item.code is code and item.audience is audience and item.variant is variant and item.pedagogical_context is pedagogical_context and item.interpretation_status is interpretation_status), None)

    def resolve(self, code, audience, variant, pedagogical_context, interpretation_status):
        if type(pedagogical_context) is not ComparisonPedagogicalContext: raise TypeError("Le contexte effectif est invalide.")
        if type(interpretation_status) is not ComparisonInterpretationEvaluationStatus: raise TypeError("Le statut A70e effectif est invalide.")
        variants = (variant,) if variant is ComparisonJustificationFeedbackVariant.GENERIC else (variant, ComparisonJustificationFeedbackVariant.GENERIC)
        for variant_key in variants:
            for context_key, status_key in ((pedagogical_context, interpretation_status), (pedagogical_context, None), (None, interpretation_status), (None, None)):
                if (template := self.get_exact(code, audience, variant_key, context_key, status_key)) is not None: return template
        return None


@dataclass(frozen=True, slots=True)
class ComparisonJustificationFeedbackItem:
    diagnostic: ComparisonJustificationDiagnostic
    template: ComparisonJustificationFeedbackTemplate
    variant: ComparisonJustificationFeedbackVariant

    def __post_init__(self):
        if type(self.diagnostic) is not ComparisonJustificationDiagnostic: raise TypeError("Le diagnostic est invalide.")
        if type(self.template) is not ComparisonJustificationFeedbackTemplate: raise TypeError("Le template est invalide.")
        if type(self.variant) is not ComparisonJustificationFeedbackVariant: raise TypeError("La variante est invalide.")
        if self.variant is not comparison_justification_feedback_variant(self.diagnostic): raise ValueError("La variante n'est pas canonique.")
        if self.template.code is not self.diagnostic.code: raise ValueError("Le template vise un autre code.")
        if self.template.variant not in (self.variant, ComparisonJustificationFeedbackVariant.GENERIC): raise ValueError("Le template vise une autre variante.")
        if self.template.pedagogical_context is not None and self.template.pedagogical_context is not self.diagnostic.pedagogical_context: raise ValueError("Le template vise un autre contexte.")
        if self.template.interpretation_status is not None and self.template.interpretation_status is not self.diagnostic.interpretation_status: raise ValueError("Le template vise un autre statut A70e.")

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
    def interpretation_status(self): return self.diagnostic.interpretation_status
    @property
    def student_normalized_error_status(self): return self.diagnostic.student_normalized_error_status
    @property
    def pedagogical_context(self): return self.diagnostic.pedagogical_context
    @property
    def observed_element_ids(self): return self.diagnostic.observed_element_ids
    @property
    def observed_kinds(self): return self.diagnostic.observed_kinds
    @property
    def missing_required_element_ids(self): return self.diagnostic.missing_required_element_ids
    @property
    def satisfied_alternative_groups(self): return self.diagnostic.satisfied_alternative_groups
    @property
    def missing_alternative_groups(self): return self.diagnostic.missing_alternative_groups
    @property
    def not_evaluable_reasons(self): return self.diagnostic.not_evaluable_reasons


def _derive(diagnostic_set, catalog):
    if type(diagnostic_set) is not ComparisonJustificationDiagnosticSet: raise TypeError("Le jeu de diagnostics est invalide.")
    if type(catalog) is not ComparisonJustificationFeedbackCatalog: raise TypeError("Le catalogue est invalide.")
    items = []
    for diagnostic in diagnostic_set:
        variant = comparison_justification_feedback_variant(diagnostic)
        for audience in (FeedbackAudience.STUDENT, FeedbackAudience.TEACHER):
            template = catalog.resolve(diagnostic.code, audience, variant, diagnostic.pedagogical_context, diagnostic.interpretation_status)
            if template is not None: items.append(ComparisonJustificationFeedbackItem(diagnostic, template, variant))
    return tuple(items)


@dataclass(frozen=True, slots=True)
class ComparisonJustificationFeedbackSet:
    diagnostic_set: ComparisonJustificationDiagnosticSet
    feedback: tuple[ComparisonJustificationFeedbackItem, ...]

    def __post_init__(self):
        if type(self.diagnostic_set) is not ComparisonJustificationDiagnosticSet: raise TypeError("Le jeu de diagnostics est invalide.")
        if isinstance(self.feedback, (str, bytes)): raise TypeError("Les feedbacks doivent former une collection.")
        feedback = tuple(self.feedback)
        if any(type(item) is not ComparisonJustificationFeedbackItem for item in feedback): raise TypeError("Un feedback est invalide.")
        object.__setattr__(self, "feedback", feedback)
        diagnostics = tuple(self.diagnostic_set)
        if any(not any(item.diagnostic is diagnostic for diagnostic in diagnostics) for item in feedback): raise ValueError("Un feedback est étranger.")
        keys = tuple((id(item.diagnostic), item.audience) for item in feedback)
        if len(keys) != len(set(keys)): raise ValueError("Un diagnostic ne produit qu'un feedback par audience.")
        positions = {id(item): index for index, item in enumerate(diagnostics)}
        audience_order = {FeedbackAudience.STUDENT: 0, FeedbackAudience.TEACHER: 1}
        order = tuple((positions[id(item.diagnostic)], audience_order[item.audience]) for item in feedback)
        if order != tuple(sorted(order)): raise ValueError("L'ordre des feedbacks est invalide.")

    def __iter__(self): return iter(self.feedback)
    def __len__(self): return len(self.feedback)
    def for_comparison(self, comparison_id): return tuple(item for item in self.feedback if item.comparison_id == comparison_id)
    def for_audience(self, audience):
        if type(audience) is not FeedbackAudience: raise TypeError("Le destinataire est invalide.")
        return tuple(item for item in self.feedback if item.audience is audience)
    def for_code(self, code):
        if type(code) is not ComparisonJustificationDiagnosticCode: raise TypeError("Le code est invalide.")
        return tuple(item for item in self.feedback if item.code is code)
    def for_priority(self, priority):
        if type(priority) is not FeedbackPriority: raise TypeError("La priorité est invalide.")
        return tuple(item for item in self.feedback if item.priority is priority)
    def for_variant(self, variant):
        if type(variant) is not ComparisonJustificationFeedbackVariant: raise TypeError("La variante est invalide.")
        return tuple(item for item in self.feedback if item.variant is variant)
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


class ComparisonJustificationFeedbackRenderer:
    def render(self, diagnostic_set, catalog): return ComparisonJustificationFeedbackSet(diagnostic_set, _derive(diagnostic_set, catalog))


def render_comparison_justification_feedback(diagnostic_set, catalog):
    """Delegate to the stateless A70h renderer."""
    return ComparisonJustificationFeedbackRenderer().render(diagnostic_set, catalog)


def french_comparison_justification_feedback_catalog():
    partial = ComparisonJustificationDiagnosticCode.JUSTIFICATION_PARTIAL
    missing = ComparisonJustificationDiagnosticCode.JUSTIFICATION_MISSING
    unavailable = ComparisonJustificationDiagnosticCode.JUSTIFICATION_NOT_EVALUABLE
    generic = ComparisonJustificationFeedbackVariant.GENERIC
    required = ComparisonJustificationFeedbackVariant.REQUIRED_ELEMENTS_MISSING
    alternatives = ComparisonJustificationFeedbackVariant.ALTERNATIVE_GROUPS_MISSING
    both = ComparisonJustificationFeedbackVariant.REQUIRED_AND_ALTERNATIVE_MISSING
    optional = ComparisonJustificationFeedbackVariant.OPTIONAL_ONLY
    student, teacher = FeedbackAudience.STUDENT, FeedbackAudience.TEACHER
    normal, high, low = FeedbackPriority.NORMAL, FeedbackPriority.HIGH, FeedbackPriority.LOW
    return ComparisonJustificationFeedbackCatalog((
        ComparisonJustificationFeedbackTemplate(partial, student, normal, "Votre justification contient certains éléments attendus, mais elle reste incomplète. Reliez plus explicitement votre conclusion aux éléments utilisés pour comparer les deux résultats."),
        ComparisonJustificationFeedbackTemplate(partial, teacher, normal, "La justification contient des éléments exploitables, mais toutes les exigences structurelles déclarées ne sont pas satisfaites."),
        ComparisonJustificationFeedbackTemplate(partial, student, normal, "Votre justification est partielle : un ou plusieurs éléments explicitement demandés ne sont pas présents.", required),
        ComparisonJustificationFeedbackTemplate(partial, teacher, normal, "La justification est partielle en raison d’éléments obligatoires non observés.", required),
        ComparisonJustificationFeedbackTemplate(partial, student, normal, "Votre justification reste incomplète : elle doit comporter au moins un argument parmi les alternatives attendues.", alternatives),
        ComparisonJustificationFeedbackTemplate(partial, teacher, normal, "Un ou plusieurs groupes d’arguments alternatifs ne sont pas satisfaits.", alternatives),
        ComparisonJustificationFeedbackTemplate(partial, student, high, "Votre justification doit être complétée : certains éléments obligatoires manquent et aucun argument attendu n’a été identifié dans un ou plusieurs groupes d’alternatives.", both),
        ComparisonJustificationFeedbackTemplate(partial, teacher, high, "La justification cumule des éléments obligatoires manquants et des groupes alternatifs non satisfaits.", both),
        ComparisonJustificationFeedbackTemplate(partial, student, normal, "Les éléments repérés enrichissent votre réponse, mais ils ne constituent pas à eux seuls une justification complète.", optional),
        ComparisonJustificationFeedbackTemplate(partial, teacher, low, "Seuls des éléments facultatifs ont été observés ; aucune obligation structurelle n’était déclarée.", optional),
        ComparisonJustificationFeedbackTemplate(missing, student, high, "Votre conclusion n’est pas accompagnée des éléments de justification attendus."),
        ComparisonJustificationFeedbackTemplate(missing, teacher, high, "Aucun élément justificatif déclaré n’a été observé dans la source exploitable."),
        ComparisonJustificationFeedbackTemplate(unavailable, teacher, normal, "La justification n’a pas pu être évaluée automatiquement à partir des sources disponibles."),
        ComparisonJustificationFeedbackTemplate(missing, student, high, "Votre conclusion correspond au classement obtenu, mais elle n’est pas accompagnée des éléments de justification attendus.", generic, None, ComparisonInterpretationEvaluationStatus.MATCHES_OBJECTIVE_CLASSIFICATION),
        ComparisonJustificationFeedbackTemplate(missing, teacher, high, "La conclusion correspond au classement objectif, mais aucun élément justificatif déclaré n’a été observé.", generic, None, ComparisonInterpretationEvaluationStatus.MATCHES_OBJECTIVE_CLASSIFICATION),
        ComparisonJustificationFeedbackTemplate(partial, student, normal, "Votre justification doit encore relier explicitement l’écart observé à la limite de la méthode étudiée ou à l’un des arguments alternatifs attendus.", alternatives, ComparisonPedagogicalContext.METHOD_LIMITATION_EXPECTED),
    ))
