"""Pure projection of a TeacherCopyReport for the teacher Web UI."""

from __future__ import annotations

from collections import Counter

from tpstudio.reporting import (
    TeacherCopyReport,
    TeacherReportCategory,
    TeacherReportSeverity,
)

from .model import (
    TeacherScientificOverview,
    TeacherScientificOverviewRow,
    TeacherScientificSeverity,
)


_ICONS = {
    TeacherScientificSeverity.OK: "✅",
    TeacherScientificSeverity.REVIEW: "⚠️",
    TeacherScientificSeverity.ERROR: "❌",
    TeacherScientificSeverity.INFO: "ℹ️",
}


def scientific_detail_widget_key(source_id: str, row_key: str) -> str:
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("source_id doit être une chaîne non vide.")
    if not isinstance(row_key, str) or not row_key.strip():
        raise ValueError("row_key doit être une chaîne non vide.")
    return f"scientific-detail-{source_id}-{row_key}"


def scientific_severity_icon(severity: TeacherScientificSeverity) -> str:
    return _ICONS[severity]


def _priority_severity(
    report: TeacherCopyReport,
    categories: set[TeacherReportCategory],
    identifiers: set[str] | None = None,
    diagnostic_ids: set[str] | None = None,
):
    priorities = tuple(
        item for item in report.priorities
        if item.category in categories
        and (
            (diagnostic_ids is not None and bool(diagnostic_ids.intersection(item.diagnostic_ids)))
            or (
                diagnostic_ids is None
                and (not identifiers or item.production_id in identifiers or item.comparison_id in identifiers)
            )
        )
    )
    if any(item.severity is TeacherReportSeverity.BLOCKING for item in priorities):
        return TeacherScientificSeverity.ERROR
    if any(item.severity is TeacherReportSeverity.IMPORTANT for item in priorities):
        return TeacherScientificSeverity.REVIEW
    if any(item.severity is TeacherReportSeverity.ATTENTION for item in priorities):
        return TeacherScientificSeverity.REVIEW
    if priorities:
        return TeacherScientificSeverity.INFO
    return None


def _row(key, label, summary, severity, details=()):
    return TeacherScientificOverviewRow(key, label, summary, severity, tuple(details))


def _productions_row(report: TeacherCopyReport):
    required = tuple(item for item in report.productions if item.required)
    if not required:
        return None
    statuses = Counter(item.status for item in required)
    resolved = statuses.get("resolved", 0)
    missing = statuses.get("missing", 0)
    ambiguous = statuses.get("ambiguous", 0)
    severity = _priority_severity(report, {TeacherReportCategory.PRODUCTION})
    if severity is None:
        severity = TeacherScientificSeverity.ERROR if missing else TeacherScientificSeverity.REVIEW if ambiguous else TeacherScientificSeverity.OK
    if missing or ambiguous:
        parts = []
        if missing:
            parts.append(f"{missing} absente" + ("s" if missing > 1 else ""))
        if ambiguous:
            parts.append(f"{ambiguous} ambiguë" + ("s" if ambiguous > 1 else ""))
        summary = f"{resolved}/{len(required)} résolues, " + ", ".join(parts)
    else:
        summary = "Toutes présentes"
    details = tuple(f"{item.title} : {item.status}" for item in required if item.status != "resolved")
    return _row("productions", "Productions obligatoires", summary, severity, details)


def _quantities_row(report: TeacherCopyReport):
    if not report.quantities:
        return None
    observed = sum(item.value is not None for item in report.quantities)
    absent = sum(item.value is None and item.status not in {"ambiguous"} for item in report.quantities)
    ambiguous = sum(item.status == "ambiguous" for item in report.quantities)
    non_evaluable = sum(not item.evaluable for item in report.quantities)
    parts = [f"{observed} observée" + ("s" if observed != 1 else "")]
    if absent:
        parts.append(f"{absent} absente" + ("s" if absent != 1 else ""))
    if ambiguous:
        parts.append(f"{ambiguous} ambiguë" + ("s" if ambiguous != 1 else ""))
    if non_evaluable and not absent and not ambiguous:
        parts.append(f"{non_evaluable} non évaluable" + ("s" if non_evaluable != 1 else ""))
    severity = _priority_severity(report, {TeacherReportCategory.QUANTITY})
    if severity is None:
        severity = TeacherScientificSeverity.ERROR if absent else TeacherScientificSeverity.REVIEW if ambiguous or non_evaluable else TeacherScientificSeverity.OK
    details = tuple(f"{item.production_id} : {', '.join(item.reasons)}" for item in report.quantities if item.reasons)
    return _row("quantities", "Quantités", ", ".join(parts), severity, details)


def _diagnostic_row(report, key, label, needles, category):
    diagnostics = tuple(
        item for item in report.diagnostics
        if any(needle in item.code.lower() or needle in item.message_key.lower() for needle in needles)
    )
    if not diagnostics:
        return None
    diagnostic_ids = {item.diagnostic_id for item in diagnostics}
    severity = _priority_severity(report, {category}, diagnostic_ids=diagnostic_ids)
    if severity is None:
        severity = TeacherScientificSeverity.REVIEW
    details = tuple(item.message_key for item in diagnostics)
    return _row(key, label, f"{len(diagnostics)} problème" + ("s" if len(diagnostics) > 1 else ""), severity, details)


def _uncertainties_row(report: TeacherCopyReport):
    problem_needles = (
        "uncertainty_missing",
        "uncertainty_not_strictly_positive",
        "uncertainty_significant_digits_invalid",
        "uncertainty_decimal_place_mismatch",
    )
    deferred_needles = ("uncertainty_justification_deferred",)
    problems = tuple(
        item for item in report.diagnostics
        if any(needle in item.code.lower() or needle in item.message_key.lower() for needle in problem_needles)
    )
    deferred = tuple(
        item for item in report.diagnostics
        if any(needle in item.code.lower() or needle in item.message_key.lower() for needle in deferred_needles)
    )
    if not problems and not deferred:
        return None
    diagnostic_ids = {item.diagnostic_id for item in (*problems, *deferred)}
    severity = _priority_severity(report, {TeacherReportCategory.QUANTITY}, diagnostic_ids=diagnostic_ids)
    if problems:
        severity = severity or TeacherScientificSeverity.REVIEW
        summary = f"{len(problems)} problème" + ("s" if len(problems) > 1 else "")
        details = tuple(item.message_key for item in problems) + tuple(item.message_key for item in deferred)
    else:
        severity = severity or TeacherScientificSeverity.INFO
        summary = "contrôle différé"
        details = tuple(item.message_key for item in deferred)
    return _row("uncertainties", "Incertitudes", summary, severity, details)


def _comparisons_row(report: TeacherCopyReport):
    if not report.comparisons:
        return None
    counts = Counter(item.objective_status for item in report.comparisons)
    strong = counts.get("strongly_incoherent", 0)
    moderate = counts.get("moderately_incoherent", 0)
    not_eval = counts.get("not_evaluable", 0)
    coherent = counts.get("coherent", 0)
    severity = _priority_severity(report, {TeacherReportCategory.COMPARISON, TeacherReportCategory.NORMALIZED_ERROR})
    # Non-evaluable is an information/review state, not a scientific error.
    # Existing priorities may still strengthen evaluated incoherences.
    if strong:
        severity = TeacherScientificSeverity.ERROR
    elif moderate:
        severity = TeacherScientificSeverity.REVIEW
    elif not_eval:
        severity = TeacherScientificSeverity.REVIEW
    elif severity is None:
        severity = TeacherScientificSeverity.OK
    if strong:
        summary = f"{strong} incohérence forte"
    else:
        parts = []
        if coherent:
            parts.append(f"{coherent} cohérente" + ("s" if coherent > 1 else ""))
        if moderate:
            parts.append(f"{moderate} à revoir")
        if not_eval:
            parts.append(f"{not_eval} non évaluable")
        summary = ", ".join(parts)
    details = tuple(
        f"{item.comparison_id} : {item.objective_status}"
        + (f" (En={item.normalized_error})" if item.normalized_error is not None else "")
        + (f" — {', '.join(item.objective_reasons)}" if item.objective_reasons else "")
        for item in report.comparisons
    )
    return _row("comparisons", "Comparaisons", summary, severity, details)


def _relations_row(report: TeacherCopyReport):
    if not report.relations:
        return None
    counts = Counter(item.status for item in report.relations)
    present = counts.get("observed", 0)
    missing = counts.get("missing", 0)
    ambiguous = counts.get("ambiguous", 0)
    severity = _priority_severity(report, {TeacherReportCategory.RELATION})
    if severity is None:
        severity = TeacherScientificSeverity.ERROR if missing else TeacherScientificSeverity.REVIEW if ambiguous else TeacherScientificSeverity.OK
    parts = []
    if present:
        parts.append(f"{present} présente" + ("s" if present > 1 else ""))
    if missing:
        parts.append(f"{missing} absente" + ("s" if missing > 1 else ""))
    if ambiguous:
        parts.append(f"{ambiguous} ambiguë" + ("s" if ambiguous > 1 else ""))
    details = tuple(f"{item.relation_id} : {item.status}" for item in report.relations)
    return _row("relations", "Relations", ", ".join(parts), severity, details)


def _conclusion_row(report: TeacherCopyReport):
    conclusion = report.final_conclusion
    if conclusion.status == "absent":
        severity = _priority_severity(report, {TeacherReportCategory.CONCLUSION, TeacherReportCategory.FINAL_CONCLUSION}) or TeacherScientificSeverity.REVIEW
        return _row("conclusion", "Conclusion", "absente", severity, ())
    severity = _priority_severity(report, {TeacherReportCategory.CONCLUSION, TeacherReportCategory.FINAL_CONCLUSION}) or TeacherScientificSeverity.INFO
    return _row("conclusion", "Conclusion", "présente", severity, ((conclusion.excerpt,) if conclusion.excerpt else ()))


def build_teacher_scientific_overview(report: TeacherCopyReport) -> TeacherScientificOverview:
    """Build a compact, presentation-only overview from an immutable report."""
    if type(report) is not TeacherCopyReport:
        raise TypeError("La synthèse exige exactement un TeacherCopyReport.")
    rows = []
    for row in (
        _productions_row(report),
        _quantities_row(report),
        _diagnostic_row(report, "units", "Unités", ("unit_missing", "unit_mismatch"), TeacherReportCategory.QUANTITY),
        _uncertainties_row(report),
        _comparisons_row(report),
        _relations_row(report),
        _conclusion_row(report),
        _row("limitations", "Limitations", f"{len(report.limitations)} limitation" + ("s" if len(report.limitations) > 1 else ""), TeacherScientificSeverity.INFO, report.limitations) if report.limitations else None,
    ):
        if row is not None:
            rows.append(row)
    return TeacherScientificOverview(tuple(rows))
