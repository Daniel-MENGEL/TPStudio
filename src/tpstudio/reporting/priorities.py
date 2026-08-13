"""Deterministic presentation priorities for teacher reports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TeacherReportSeverity(str, Enum):
    INFO = "info"
    ATTENTION = "attention"
    IMPORTANT = "important"
    BLOCKING = "blocking"


class TeacherReportCategory(str, Enum):
    TECHNICAL = "technical"
    PRODUCTION = "production"
    QUANTITY = "quantity"
    UNCERTAINTY = "uncertainty"
    RELATION = "relation"
    GRAPH = "graph"
    COMPARISON = "comparison"
    NORMALIZED_ERROR = "normalized_error"
    INTERPRETATION = "interpretation"
    JUSTIFICATION = "justification"
    FINAL_CONCLUSION = "final_conclusion"
    LIMITATION = "limitation"
    PROTOCOL = "protocol"
    CONCLUSION = "conclusion"


@dataclass(frozen=True, slots=True)
class TeacherReportPriority:
    priority_id: str
    severity: TeacherReportSeverity
    category: TeacherReportCategory
    title: str
    message: str
    production_id: str | None = None
    comparison_id: str | None = None
    cell_indices: tuple[int, ...] = ()
    diagnostic_ids: tuple[str, ...] = ()
    feedback_ids: tuple[str, ...] = ()
    requires_human_review: bool = True

    def __post_init__(self) -> None:
        for name in ("priority_id", "title", "message"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} ne peut pas être vide.")
        if type(self.severity) is not TeacherReportSeverity:
            raise TypeError("La sévérité de présentation est invalide.")
        if type(self.category) is not TeacherReportCategory:
            raise TypeError("La catégorie de rapport est invalide.")
        if type(self.requires_human_review) is not bool:
            raise TypeError("requires_human_review doit être booléen.")
        for name in ("cell_indices", "diagnostic_ids", "feedback_ids"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


_SEVERITY_ORDER = {
    TeacherReportSeverity.BLOCKING: 0,
    TeacherReportSeverity.IMPORTANT: 1,
    TeacherReportSeverity.ATTENTION: 2,
    TeacherReportSeverity.INFO: 3,
}


def order_teacher_report_priorities(
    priorities: tuple[TeacherReportPriority, ...],
    production_order: tuple[str, ...],
) -> tuple[TeacherReportPriority, ...]:
    """Order presentation priorities without changing scientific statuses."""

    values = tuple(priorities)
    if any(type(item) is not TeacherReportPriority for item in values):
        raise TypeError("Chaque priorité doit être une TeacherReportPriority.")
    if len({item.priority_id for item in values}) != len(values):
        raise ValueError("Les identifiants de priorité doivent être uniques.")
    pedagogical = {identifier: index for index, identifier in enumerate(production_order)}
    return tuple(sorted(values, key=lambda item: (
        _SEVERITY_ORDER[item.severity],
        pedagogical.get(item.production_id or item.comparison_id or "", len(pedagogical)),
        item.priority_id,
    )))
