import pytest

from tpstudio.web.roster import (
    RosterStudent, confirm_exact_roster_identity, enrich_identity_for_mail,
    load_roster, parse_roster_csv, save_roster,
    suggest_roster_students,
)
from tpstudio.web.identity import (
    CopyIdentity, CopyIdentitySource, CopyIdentityStatus, StudentIdentity,
    build_canonical_copy_stem,
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


def test_exact_notebook_names_are_confirmed_automatically_against_roster():
    roster = (
        RosterStudent("DURAND", "Alice", "alice@example.test"),
        RosterStudent("ROUX", "Paul", "paul@example.test"),
    )
    identity = CopyIdentity(
        (StudentIdentity("Alice DURAND"), StudentIdentity("Paul ROUX")),
        CopyIdentitySource.NOTEBOOK,
        CopyIdentityStatus.TO_REVIEW,
        "Alice DURAND et Paul ROUX",
        ("Le nom du fichier semble indiquer une identité différente.",),
    )

    confirmed = confirm_exact_roster_identity(identity, roster)

    assert confirmed.status is CopyIdentityStatus.CONFIRMED
    assert confirmed.source is CopyIdentitySource.NOTEBOOK
    assert [student.email for student in confirmed.students] == [
        "alice@example.test", "paul@example.test",
    ]
    assert confirmed.warnings == ()


def test_confirmed_notebook_identity_is_enriched_from_reversed_roster_name():
    roster = (
        RosterStudent("MEGLY", "Clara", "clara@example.test"),
        RosterStudent("THOUVENOT", "Thomas", "thomas@example.test"),
    )
    identity = CopyIdentity(
        (StudentIdentity("Mégly Clara"), StudentIdentity("Thouvenot Thomas")),
        CopyIdentitySource.NOTEBOOK,
        CopyIdentityStatus.CONFIRMED,
        "Mégly Clara et Thouvenot Thomas",
    )

    confirmed = confirm_exact_roster_identity(identity, roster)

    assert [student.family_name for student in confirmed.students] == [
        "MEGLY", "THOUVENOT",
    ]
    assert [student.given_names for student in confirmed.students] == [
        "Clara", "Thomas",
    ]
    assert build_canonical_copy_stem("TP", confirmed) == (
        "TP-MEGLY-Clara-THOUVENOT-Thomas"
    )


def test_unique_uppercase_family_names_recover_given_names_from_roster():
    roster = (
        RosterStudent("MAIRE", "Manon", "manon@example.test"),
        RosterStudent("LAMBIN", "Lise", "lise@example.test"),
    )
    identity = CopyIdentity(
        (StudentIdentity("MAIRE"), StudentIdentity("LAMBIN")),
        CopyIdentitySource.NOTEBOOK,
        CopyIdentityStatus.CONFIRMED,
        "MAIRE et LAMBIN",
    )

    confirmed = confirm_exact_roster_identity(identity, roster)

    assert build_canonical_copy_stem("Premières-mesures-au-labo", confirmed) == (
        "Premières-mesures-au-labo-MAIRE-Manon-LAMBIN-Lise"
    )


def test_unique_titlecase_family_name_recovers_given_name_from_roster():
    roster = (
        RosterStudent("GROSPERRIN", "Emilie", "emilie@example.test"),
    )
    identity = CopyIdentity(
        (StudentIdentity("Grosperrin"),),
        CopyIdentitySource.NOTEBOOK,
        CopyIdentityStatus.CONFIRMED,
        "Grosperrin",
    )

    confirmed = confirm_exact_roster_identity(identity, roster)

    assert build_canonical_copy_stem("Premières-mesures-au-labo", confirmed) == (
        "Premières-mesures-au-labo-GROSPERRIN-Emilie"
    )


def test_ambiguous_family_name_does_not_guess_a_given_name():
    roster = (
        RosterStudent("DUPONT", "Alice", "alice@example.test"),
        RosterStudent("DUPONT", "Léa", "lea@example.test"),
    )
    identity = CopyIdentity(
        (StudentIdentity("DUPONT"),),
        CopyIdentitySource.NOTEBOOK,
        CopyIdentityStatus.CONFIRMED,
    )

    assert confirm_exact_roster_identity(identity, roster) is identity


def test_roster_confirmation_abstains_for_ambiguous_or_filename_only_identity():
    duplicate_names = (
        RosterStudent("DURAND", "Alice", "alice.1@example.test"),
        RosterStudent("DURAND", "Alice", "alice.2@example.test"),
    )
    notebook_identity = CopyIdentity(
        (StudentIdentity("Alice DURAND"),), CopyIdentitySource.NOTEBOOK,
        CopyIdentityStatus.TO_REVIEW,
    )
    filename_identity = CopyIdentity(
        (), CopyIdentitySource.FILENAME, CopyIdentityStatus.TO_REVIEW,
    )

    assert confirm_exact_roster_identity(notebook_identity, duplicate_names) is notebook_identity
    assert confirm_exact_roster_identity(filename_identity, duplicate_names) is filename_identity


def test_mail_identity_uses_roster_for_two_names_combined_in_one_field():
    roster = (
        RosterStudent("BERTRAND", "Vincent", "vincent@example.test"),
        RosterStudent("FIETTA", "Chloe", "chloe@example.test"),
    )
    identity = CopyIdentity(
        (StudentIdentity("Vincent BERTRAND Chloé FIETTA"),),
        CopyIdentitySource.NOTEBOOK,
        CopyIdentityStatus.CONFIRMED,
        "Vincent BERTRAND Chloé FIETTA",
    )

    enriched = enrich_identity_for_mail(
        identity,
        "Untitled-Vincent-Bertrand-et-Chloe-Fietta.ipynb",
        roster,
    )

    assert [student.email for student in enriched.students] == [
        "vincent@example.test", "chloe@example.test",
    ]


def test_mail_identity_recovers_family_name_and_email_from_roster():
    roster = (RosterStudent("BEURVILLE", "Ewann", "ewann@example.test"),)
    identity = CopyIdentity(
        (StudentIdentity("BEURVILLE ELZEAR"),),
        CopyIdentitySource.NOTEBOOK,
        CopyIdentityStatus.CONFIRMED,
        "BEURVILLE ELZEAR",
    )

    enriched = enrich_identity_for_mail(
        identity, "Untitled BEURVILLE ELZEAR.ipynb", roster,
    )

    assert enriched.students[0].display_name == "Ewann BEURVILLE"
    assert enriched.students[0].email == "ewann@example.test"


def test_mail_identity_can_use_filename_when_notebook_identity_is_missing():
    roster = (
        RosterStudent("DOROSZEWSKI", "Alice", "alice@example.test"),
        RosterStudent("DOUAIR", "Kenzo", "kenzo@example.test"),
    )
    identity = CopyIdentity(
        (), CopyIdentitySource.FILENAME, CopyIdentityStatus.TO_REVIEW,
    )

    enriched = enrich_identity_for_mail(
        identity,
        "doroszewski douair 14.09.2026 Kenzo Alice.ipynb",
        roster,
    )

    assert enriched.status is CopyIdentityStatus.CONFIRMED
    assert [student.email for student in enriched.students] == [
        "alice@example.test", "kenzo@example.test",
    ]


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


def test_mail_identity_accepts_objects_kept_by_an_old_streamlit_session():
    class OldEnum:
        def __init__(self, value):
            self.value = value

    class OldStudent:
        display_name = "Alice DOROSZEWSKI"
        family_name = "DOROSZEWSKI"
        given_names = "Alice"
        email = "alice@example.test"

    class OldIdentity:
        students = (OldStudent(),)
        source = OldEnum("manual")
        status = OldEnum("confirmed")
        raw_value = "Alice DOROSZEWSKI"
        warnings = ()

    enriched = enrich_identity_for_mail(
        OldIdentity(), "copie.ipynb", (),
    )

    assert enriched.status is CopyIdentityStatus.CONFIRMED
    assert enriched.source is CopyIdentitySource.MANUAL
    assert enriched.students[0].email == "alice@example.test"
