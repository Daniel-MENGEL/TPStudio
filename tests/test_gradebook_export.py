
from __future__ import annotations

import csv
import json
from pathlib import Path

from tpstudio.gradebook_export import (
    NotebookIdentity,
    StudentRecord,
    build_gradebook_rows,
    export_gradebook_csv,
    extract_identity_from_text,
    infer_student_name_from_notebook,
    load_students_csv,
    match_student_record,
    read_notebook_identity,
    split_identity_names,
    split_identity_students,
)


def _write_notebook(path: Path, cells: list[dict]) -> None:
    path.write_text(json.dumps({"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}, ensure_ascii=False), encoding="utf-8")


def _write_students_csv(path: Path) -> None:
    path.write_text(
        "Nom,Prénom,Email,Groupe\n"
        "DURAND,Alice,alice.durand@example.test,PCSI2-A\n"
        "MARTIN,Bob,bob.martin@example.test,PCSI2-A\n"
        "DUPONT,Claire,claire.dupont@example.test,PCSI2-B\n",
        encoding="utf-8",
    )


def test_load_students_csv(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    _write_students_csv(students_file)
    students = load_students_csv(students_file)
    assert students == [
        StudentRecord("DURAND", "Alice", "alice.durand@example.test", "PCSI2-A"),
        StudentRecord("MARTIN", "Bob", "bob.martin@example.test", "PCSI2-A"),
        StudentRecord("DUPONT", "Claire", "claire.dupont@example.test", "PCSI2-B"),
    ]


def test_match_student_record_accepts_swapped_first_last_name() -> None:
    official = [StudentRecord("DURAND", "Alice", "alice.durand@example.test", "PCSI2-A")]
    assert match_student_record("DURAND", "Alice", official) == official[0]
    assert match_student_record("Alice", "Durand", official) == official[0]


def test_extract_identity_from_markdown_text() -> None:
    identity = extract_identity_from_text(
        "## Identification du compte rendu\n\n"
        "**Noms :** Durand Alice\n"
        "**Groupe :** PCSI2\n"
        "**Date de la séance :** 2026-07-02\n"
    )
    assert identity == NotebookIdentity(names="Durand Alice", group="PCSI2", session_date="2026-07-02")


def test_extract_identity_from_bullet_list() -> None:
    identity = extract_identity_from_text(
        "## Identification du compte rendu\n\n"
        "**Noms :**\n"
        "- Durand Alice\n"
        "- Martin Bob\n"
        "- Dupont Claire\n"
        "**Groupe :** PCSI2\n"
        "**Date de la séance :** 2026-07-02\n"
    )
    assert identity.names == "Durand Alice ; Martin Bob ; Dupont Claire"
    assert identity.group == "PCSI2"
    assert identity.session_date == "2026-07-02"


def test_read_notebook_identity_from_tpsudio_metadata(tmp_path: Path) -> None:
    notebook = tmp_path / "Durand-Alice.ipynb"
    _write_notebook(notebook, [{"cell_type": "markdown", "metadata": {"tpstudio": {"cell_role": "report_identity"}}, "source": ["## Identification du compte rendu\n", "\n", "**Noms :** Durand Alice\n", "**Groupe :** PCSI2\n", "**Date de la séance :** 2026-07-02\n"]}])
    assert read_notebook_identity(notebook) == NotebookIdentity(names="Durand Alice", group="PCSI2", session_date="2026-07-02")


def test_split_identity_students_handles_monomes_binomes_trinomes() -> None:
    assert split_identity_students("Durand Alice") == [("DURAND", "Alice")]
    assert split_identity_students("Durand Alice ; Martin Bob") == [("DURAND", "Alice"), ("MARTIN", "Bob")]
    assert split_identity_students("Durand Alice ; Martin Bob ; Dupont Claire") == [("DURAND", "Alice"), ("MARTIN", "Bob"), ("DUPONT", "Claire")]
    assert split_identity_students("Durand Alice et Martin Bob") == [("DURAND", "Alice"), ("MARTIN", "Bob")]


def test_split_identity_names_keeps_backward_compatible_single_value() -> None:
    assert split_identity_names("Durand Alice") == ("DURAND", "Alice")
    assert split_identity_names("Durand Alice ; Martin Bob") == ("Durand Alice ; Martin Bob", "")
    assert split_identity_names("") == ("", "")


def test_infer_student_name_from_notebook() -> None:
    assert infer_student_name_from_notebook("Durand-Alice.ipynb") == ("DURAND", "Alice")
    assert infer_student_name_from_notebook("DURAND_Alice.ipynb") == ("DURAND", "Alice")
    assert infer_student_name_from_notebook("Martin Bob.ipynb") == ("MARTIN", "Bob")
    assert infer_student_name_from_notebook("copie-Dupont-Marie.ipynb") == ("DUPONT", "Marie")


def test_infer_student_name_leaves_tp_title_empty_when_no_student_name() -> None:
    assert infer_student_name_from_notebook("Lois-de-Snell-Descartes.ipynb", tp_name="Lois de Snell Descartes") == ("", "")
    assert infer_student_name_from_notebook("Lois-de-Snell-Descartes-codex.ipynb", tp_name="Lois de Snell Descartes") == ("", "")


def test_build_gradebook_rows_uses_notebook_identity_first(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Lois-de-Snell-Descartes-codex.ipynb", [{"cell_type": "markdown", "metadata": {}, "source": ["## Identification du compte rendu\n", "\n", "**Noms :** Durand Alice\n", "**Groupe :** PCSI2\n", "**Date de la séance :** 2026-07-02\n"]}])
    rows = build_gradebook_rows(tmp_path, session="Séance n°2", tp_name="Lois de Snell Descartes", date_value="2026-07-01")
    assert len(rows) == 1
    assert rows[0].last_name == "DURAND"
    assert rows[0].first_name == "Alice"
    assert rows[0].email == ""
    assert rows[0].group == "PCSI2"
    assert rows[0].date == "2026-07-02"


def test_build_gradebook_rows_adds_email_from_students_file_without_filling_tp_group(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    _write_students_csv(students_file)
    _write_notebook(tmp_path / "copie-binome.ipynb", [{"cell_type": "markdown", "metadata": {}, "source": ["## Identification du compte rendu\n", "\n", "**Noms :** Durand Alice ; Martin Bob\n", "**Groupe :**\n", "**Date de la séance :** 2026-07-02\n"]}])
    rows = build_gradebook_rows(tmp_path, session="Séance n°2", tp_name="Lois de Snell Descartes", date_value="2026-07-01", students_file=students_file)
    assert [(row.last_name, row.first_name, row.email, row.group) for row in rows] == [
        ("DURAND", "Alice", "alice.durand@example.test", ""),
        ("MARTIN", "Bob", "bob.martin@example.test", ""),
    ]


def test_build_gradebook_rows_uses_tp_group_from_notebook(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    _write_students_csv(students_file)
    _write_notebook(tmp_path / "Durand-Alice.ipynb", [{"cell_type": "markdown", "metadata": {}, "source": ["## Identification du compte rendu\n", "\n", "**Noms :** Durand Alice\n", "**Groupe :** Groupe TP 4\n", "**Date de la séance :** 2026-07-02\n"]}])
    rows = build_gradebook_rows(tmp_path, session="Séance n°2", tp_name="Lois de Snell Descartes", students_file=students_file)
    assert rows[0].email == "alice.durand@example.test"
    assert rows[0].group == "Groupe TP 4"


def test_build_gradebook_rows_creates_one_row_per_student(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "copie-binome.ipynb", [{"cell_type": "markdown", "metadata": {}, "source": ["## Identification du compte rendu\n", "\n", "**Noms :** Durand Alice ; Martin Bob ; Dupont Claire\n", "**Groupe :** PCSI2\n", "**Date de la séance :** 2026-07-02\n"]}])
    rows = build_gradebook_rows(tmp_path, session="Séance n°2", tp_name="Lois de Snell Descartes", date_value="2026-07-01")
    assert [(row.last_name, row.first_name) for row in rows] == [("DURAND", "Alice"), ("MARTIN", "Bob"), ("DUPONT", "Claire")]
    assert {row.notebook_name for row in rows} == {"copie-binome.ipynb"}
    assert {row.group for row in rows} == {"PCSI2"}


def test_build_gradebook_rows_keeps_unknown_name_empty(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Lois-de-Snell-Descartes.ipynb", [])
    _write_notebook(tmp_path / "Lois-de-Snell-Descartes-codex.ipynb", [])
    rows = build_gradebook_rows(tmp_path, session="Séance n°2", tp_name="Lois de Snell Descartes", date_value="2026-07-02")
    assert [row.notebook_name for row in rows] == ["Lois-de-Snell-Descartes-codex.ipynb", "Lois-de-Snell-Descartes.ipynb"]
    assert rows[0].last_name == ""
    assert rows[0].first_name == ""
    assert rows[1].last_name == ""
    assert rows[1].first_name == ""


def test_build_gradebook_rows_ignores_generated_feedback_notebooks(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "Durand-Alice.ipynb", [])
    _write_notebook(tmp_path / "Martin-Bob.ipynb", [])
    _write_notebook(tmp_path / "Martin-Bob-retour-tpstudio.ipynb", [])
    rows = build_gradebook_rows(tmp_path, session="Séance n°2", tp_name="Lois de Snell Descartes", date_value="2026-07-02")
    assert [row.notebook_name for row in rows] == ["Durand-Alice.ipynb", "Martin-Bob.ipynb"]


def test_export_gradebook_csv(tmp_path: Path) -> None:
    students_file = tmp_path / "students.csv"
    _write_students_csv(students_file)
    _write_notebook(tmp_path / "Durand-Alice.ipynb", [{"cell_type": "markdown", "metadata": {}, "source": ["## Identification du compte rendu\n", "\n", "**Noms :** Durand Alice\n", "**Groupe :** PCSI2\n", "**Date de la séance :** 2026-07-02\n"]}])
    output = tmp_path / "suivi.csv"
    created = export_gradebook_csv(tmp_path, output, session="Séance n°2", tp_name="Lois de Snell Descartes", date_value="2026-07-01", students_file=students_file)
    assert created == output
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert rows[0]["Nom"] == "DURAND"
    assert rows[0]["Prénom"] == "Alice"
    assert rows[0]["Email"] == "alice.durand@example.test"
    assert rows[0]["Groupe"] == "PCSI2"
    assert rows[0]["Séance"] == "Séance n°2"
    assert rows[0]["Nom du TP"] == "Lois de Snell Descartes"
    assert rows[0]["Nom du notebook"] == "Durand-Alice.ipynb"
    assert rows[0]["Date"] == "2026-07-02"
    assert rows[0]["Note"] == ""
