"""Teacher-facing reporting API."""

from .inspection import format_inspection, make_inspection_report
from .markdown import render_teacher_report_markdown, summarize_teacher_report
from .priorities import TeacherReportCategory, TeacherReportPriority, TeacherReportSeverity, order_teacher_report_priorities
from .teacher_report import (
    TeacherComparisonReport, TeacherCopyReport, TeacherDiagnosticReportItem,
    TeacherFeedbackReportItem, TeacherFinalConclusionReport, TeacherGraphReport,
    TeacherHumanReviewReport, TeacherProductionReport, TeacherQuantityReport,
    TeacherRelationReport, TeacherReportOverview, TeacherTechnicalReport,
    TeacherValueReport, build_teacher_copy_report,
    diagnostic_source_key, feedback_source_key,
)

__all__ = [name for name in globals() if name.startswith("Teacher") or name in {
    "build_teacher_copy_report", "render_teacher_report_markdown",
    "summarize_teacher_report", "order_teacher_report_priorities",
    "format_inspection", "make_inspection_report",
    "diagnostic_source_key", "feedback_source_key",
}]
