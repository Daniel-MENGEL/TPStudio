from dataclasses import FrozenInstanceError

import pytest

from tpstudio.reporting import (
    TeacherReportCategory, TeacherReportPriority, TeacherReportSeverity,
    order_teacher_report_priorities,
)


def _priority(identifier, severity, production=None):
    return TeacherReportPriority(identifier, severity, TeacherReportCategory.PRODUCTION, "Titre", "Message", production_id=production)


def test_enums_have_exact_presentation_values() -> None:
    assert [item.value for item in TeacherReportSeverity] == ["info", "attention", "important", "blocking"]
    assert TeacherReportCategory.JUSTIFICATION.value == "justification"


def test_priority_is_immutable_and_has_no_score_or_grade() -> None:
    item = _priority("p", TeacherReportSeverity.INFO)
    with pytest.raises(FrozenInstanceError): item.title = "x"
    assert not hasattr(item, "score") and not hasattr(item, "grade")


def test_priority_order_is_severity_then_pedagogy_then_id() -> None:
    values = (
        _priority("z", TeacherReportSeverity.INFO, "a"),
        _priority("i2", TeacherReportSeverity.IMPORTANT, "b"),
        _priority("i1", TeacherReportSeverity.IMPORTANT, "a"),
        _priority("b", TeacherReportSeverity.BLOCKING, "b"),
        _priority("a", TeacherReportSeverity.ATTENTION, "a"),
    )
    assert tuple(item.priority_id for item in order_teacher_report_priorities(values, ("a", "b"))) == ("b", "i1", "i2", "a", "z")


def test_duplicate_priority_ids_are_rejected() -> None:
    item = _priority("same", TeacherReportSeverity.INFO)
    with pytest.raises(ValueError): order_teacher_report_priorities((item, item), ())
