import csv
import io

from tpstudio.web.grade_export import WebGradeEntry, build_web_gradebook_csv
from tpstudio.web.roster import RosterStudent
from tpstudio.web.roster import enrich_identity_for_mail
from tpstudio.web.identity import CopyIdentity, CopyIdentitySource, CopyIdentityStatus, StudentIdentity


def _rows(payload: bytes):
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), delimiter=";"))


def test_grade_export_has_one_student_row_and_one_column_per_tp():
    roster = (
        RosterStudent("DUPONT", "Alice", "alice@example.fr"),
        RosterStudent("MARTIN", "Bob", "bob@example.fr"),
    )
    entries = (
        WebGradeEntry("DUPONT", "Alice", "alice@example.fr", "TP A", "14.5/20", True),
        WebGradeEntry("DUPONT", "Alice", "alice@example.fr", "TP B", "12.0/20", True),
    )

    rows = _rows(build_web_gradebook_csv(entries, roster))

    assert rows[0]["Note — TP A"] == "14,5"
    assert rows[0]["Note — TP B"] == "12,0"
    assert rows[1]["État — TP A"] == "Non remise"
    assert rows[1]["État — TP B"] == "Non remise"


def test_unreviewed_grade_is_not_exported_as_final():
    entries = (
        WebGradeEntry("DUPONT", "Alice", "", "TP A", "9.0/20", False),
    )

    row = _rows(build_web_gradebook_csv(entries))[0]

    assert row["Note — TP A"] == ""
    assert row["État — TP A"] == "À vérifier"


def test_missing_identity_email_is_resolved_from_roster():
    roster = (
        RosterStudent("DUPONT", "Alice", "alice@example.fr"),
    )
    entries = (
        WebGradeEntry("DUPONT", "Alice", None, "TP A", "15/20", True),
    )

    row = _rows(build_web_gradebook_csv(entries, roster))[0]

    assert row["Email"] == "alice@example.fr"
    assert row["Note — TP A"] == "15"


def test_binome_display_names_are_matched_to_both_roster_rows():
    roster = (
        RosterStudent("DUPONT", "Alice", "alice@example.fr"),
        RosterStudent("MARTIN", "Bob", "bob@example.fr"),
    )
    entries = (
        WebGradeEntry("", "", None, "TP A", "15/20", True, "Alice DUPONT"),
        WebGradeEntry("", "", None, "TP A", "15/20", True, "Bob MARTIN"),
    )

    rows = _rows(build_web_gradebook_csv(entries, roster))

    assert {row["Email"] for row in rows} == {"alice@example.fr", "bob@example.fr"}
    assert all(row["Note — TP A"] == "15" for row in rows)


def test_unmatched_display_name_does_not_create_an_anonymous_grade_row():
    entries = (WebGradeEntry("", "", None, "TP A", "12/20", True, "Élève inconnu"),)

    row = _rows(build_web_gradebook_csv(entries))[0]

    assert row["Nom"] == "Élève inconnu"
    assert row["Note — TP A"] == "12"


def test_combined_binome_name_gives_the_grade_to_both_students():
    roster = (
        RosterStudent("ROSELLO", "Marina", "marina@example.fr"),
        RosterStudent("LOMBARD", "Axel", "axel@example.fr"),
    )
    entry = WebGradeEntry("", "", None, "TP A", "15.1/20", True, "ROSELLO MARINA LOMBARD AXEL")

    rows = _rows(build_web_gradebook_csv((entry,), roster))

    assert len(rows) == 2
    assert all(row["Note — TP A"] == "15,1" for row in rows)


def test_unique_surname_typo_with_exact_given_name_matches_roster():
    roster = (RosterStudent("PICARD", "Alban", "alban@example.fr"),)
    entry = WebGradeEntry("", "", None, "TP A", "10/20", True, "PiICARD Alban")

    rows = _rows(build_web_gradebook_csv((entry,), roster))

    assert len(rows) == 1
    assert rows[0]["Email"] == "alban@example.fr"
    assert rows[0]["Note — TP A"] == "10"


def test_incomplete_combined_name_is_not_guessed():
    roster = (
        RosterStudent("BEURVILLE", "Ewann", "ewann@example.fr"),
        RosterStudent("RICHARD", "Gabriel", "gabriel@example.fr"),
    )
    entry = WebGradeEntry("", "", None, "TP A", "10/20", True, "Beurville Richard")

    rows = _rows(build_web_gradebook_csv((entry,), roster))

    assert len(rows) == 3
    assert next(row for row in rows if row["Nom"] == "Beurville Richard")["Note — TP A"] == "10"
    assert all(row["État — TP A"] == "Non remise" for row in rows if row["Email"])


def test_grade_export_uses_the_same_three_recipients_as_mail():
    roster = (
        RosterStudent("BEURVILLE", "Ewann", "ewann@example.fr"),
        RosterStudent("PHILBERT", "Clarence", "clarence@example.fr"),
        RosterStudent("RICHARD", "Gabriel", "gabriel@example.fr"),
    )
    identity = CopyIdentity(
        (StudentIdentity("Philbert Beurville Richard"),),
        CopyIdentitySource.NOTEBOOK,
        CopyIdentityStatus.CONFIRMED,
        "Philbert Beurville Richard",
    )
    resolved = enrich_identity_for_mail(
        identity, "Untitled-Beurville-Richard-Philbert.ipynb", roster
    )
    entries = tuple(
        WebGradeEntry(
            student.family_name or "", student.given_names or "", student.email,
            "Lois de Snell-Descartes", "10.7/20", True, student.display_name,
        )
        for student in resolved.students
    )

    rows = _rows(build_web_gradebook_csv(entries, roster))

    assert len(rows) == 3
    assert all(row["Note — Lois de Snell-Descartes"] == "10,7" for row in rows)
