import pytest

from tpstudio.web.roster import (
    RosterStudent, load_roster, parse_roster_csv, save_roster,
    suggest_roster_students,
)


def test_parse_roster_without_header_supports_utf8_and_names_composes():
    students = parse_roster_csv(
        "BOUZRAD LAANDOUR;Khadija;KHDIJA@EXAMPLE.COM\n"
        "MATEUS--LORENZI;Rafaël;rafael@example.com\n\n"
    )
    assert students[0].email == "khdija@example.com"
    assert students[0].label == "Khadija BOUZRAD LAANDOUR"
    assert students[1].given_names == "Rafaël"


def test_parse_header_empty_lines_and_exact_duplicate_are_supported():
    students = parse_roster_csv("NOM;Prénom;mail\nDUPONT;Léa;lea@example.com\n\nDUPONT;Léa;LEA@example.com\n")
    assert len(students) == 1 and students[0].email == "lea@example.com"


def test_parse_rejects_invalid_and_contradictory_duplicate():
    with pytest.raises(ValueError, match="Ligne 1"):
        parse_roster_csv("DUPONT;Léa\n")
    with pytest.raises(ValueError, match="dupliqué"):
        parse_roster_csv("DUPONT;Léa;lea@example.com\nMARTIN;Léo;LEA@example.com\n")


def test_roster_persists_and_reloads_by_email(tmp_path):
    students = (RosterStudent("ABADELIA", "Abdallah", "abdallah@example.com"),)
    path = save_roster(students, tmp_path / "students.json")
    assert load_roster(path) == students


def test_filename_suggestions_are_only_suggestions():
    students = (
        RosterStudent("MASSON", "Antonin", "antonin@example.com"),
        RosterStudent("SCHAEFFER", "Nathan", "nathan@example.com"),
        RosterStudent("MELE", "Hugo", "hugo@example.com"),
        RosterStudent("HIRSCHFELDER", "Carl", "carl@example.com"),
    )
    suggested = suggest_roster_students("Lois-de-Snell-Descartes(Antonin-et)-Nathan.ipynb", students)
    assert {student.email for student in suggested} == {"antonin@example.com", "nathan@example.com"}
    suggested = suggest_roster_students("TP-HugoMELE&CarlHIRSCHFELDER.ipynb", students)
    assert {student.email for student in suggested} == {"hugo@example.com", "carl@example.com"}
