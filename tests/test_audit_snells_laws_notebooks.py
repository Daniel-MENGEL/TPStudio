from __future__ import annotations

import json
from pathlib import Path

import nbformat

from scripts.audit_snells_laws_notebooks import audit_notebook, compare_notebooks, main


def _write_notebook(path: Path, cells: list) -> None:
    notebook = nbformat.v4.new_notebook(cells=cells)
    nbformat.write(notebook, path)


def test_audit_loads_valid_notebook_without_extension(tmp_path: Path) -> None:
    path = tmp_path / "notebook_without_extension"
    _write_notebook(
        path,
        [
            nbformat.v4.new_markdown_cell("# Titre\n**Réponse :** à compléter"),
            nbformat.v4.new_code_cell("value = ?"),
        ],
    )

    audit = audit_notebook(path)

    assert audit["valid_notebook"] is True
    assert audit["cell_count"] == 2
    assert audit["cell_types"] == {"markdown": 1, "code": 1, "raw": 0}
    assert audit["headings"] == [{"cell_index": 0, "title": "Titre"}]
    assert audit["marker_counts"]["Réponse"] == 1
    assert audit["question_mark_cells"] == [1]
    assert audit["external_references"] == []


def test_audit_reports_execution_errors_and_unexecuted_code(tmp_path: Path) -> None:
    path = tmp_path / "errors.ipynb"
    failed = nbformat.v4.new_code_cell("raise ValueError('x')", execution_count=1)
    failed.outputs = [
        nbformat.v4.new_output(
            "error", ename="ValueError", evalue="x", traceback=["trace"]
        )
    ]
    pending = nbformat.v4.new_code_cell("print('pending')")
    _write_notebook(path, [failed, pending])

    audit = audit_notebook(path)

    assert audit["output_count"] == 1
    assert audit["error_output_count"] == 1
    assert audit["unexecuted_code_cells"] == [1]


def test_markdown_question_is_not_a_code_completion_marker(tmp_path: Path) -> None:
    path = tmp_path / "markdown_question.ipynb"
    _write_notebook(
        path,
        [nbformat.v4.new_markdown_cell("Quelle relation doit-on vérifier ?")],
    )

    assert audit_notebook(path)["question_mark_cells"] == []


def test_only_code_placeholder_is_reported_among_markdown_and_code(
    tmp_path: Path,
) -> None:
    path = tmp_path / "mixed_questions.ipynb"
    _write_notebook(
        path,
        [
            nbformat.v4.new_markdown_cell("Quelle relation doit-on vérifier ?"),
            nbformat.v4.new_code_cell("n = ?"),
        ],
    )

    assert audit_notebook(path)["question_mark_cells"] == [1]


def test_raw_question_is_ignored_and_code_indices_keep_notebook_order(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ordered_code_markers.ipynb"
    _write_notebook(
        path,
        [
            nbformat.v4.new_code_cell("first = ?"),
            nbformat.v4.new_raw_cell("Raw content ?"),
            nbformat.v4.new_markdown_cell("Question ?"),
            nbformat.v4.new_code_cell("stable = 1"),
            nbformat.v4.new_code_cell("last = ?"),
        ],
    )

    assert audit_notebook(path)["question_mark_cells"] == [0, 4]


def test_compare_reports_added_removed_and_modified_cells(tmp_path: Path) -> None:
    reference = tmp_path / "reference.ipynb"
    candidate = tmp_path / "candidate.ipynb"
    _write_notebook(
        reference,
        [
            nbformat.v4.new_markdown_cell("# Stable"),
            nbformat.v4.new_code_cell("removed = 1"),
            nbformat.v4.new_markdown_cell("old response"),
        ],
    )
    _write_notebook(
        candidate,
        [
            nbformat.v4.new_markdown_cell("# Stable"),
            nbformat.v4.new_markdown_cell("new response"),
            nbformat.v4.new_code_cell("added = 2"),
        ],
    )

    comparison = compare_notebooks(reference, candidate)

    assert comparison["unchanged_cell_count"] == 1
    assert comparison["modified_cells"] == [
        {"reference_index": 1, "candidate_index": 1},
        {"reference_index": 2, "candidate_index": 2},
    ]


def test_comparison_detects_pure_cell_addition_and_deletion(tmp_path: Path) -> None:
    reference = tmp_path / "reference.ipynb"
    added = tmp_path / "added.ipynb"
    removed = tmp_path / "removed.ipynb"
    stable = nbformat.v4.new_markdown_cell("stable")
    extra = nbformat.v4.new_code_cell("extra = True")
    _write_notebook(reference, [stable])
    _write_notebook(added, [stable, extra])
    _write_notebook(removed, [])

    assert compare_notebooks(reference, added)["added_candidate_cells"] == [1]
    assert compare_notebooks(reference, removed)["removed_reference_cells"] == [0]


def test_audit_is_deterministic_and_does_not_modify_source(tmp_path: Path) -> None:
    path = tmp_path / "source.ipynb"
    _write_notebook(path, [nbformat.v4.new_markdown_cell("## Conclusion\nTODO")])
    before = path.read_bytes()

    first = audit_notebook(path)
    second = audit_notebook(path)

    assert first == second
    assert path.read_bytes() == before


def test_main_emits_deterministic_json_report(tmp_path: Path, capsys) -> None:
    path = tmp_path / "report.ipynb"
    _write_notebook(path, [nbformat.v4.new_markdown_cell("# Objectif")])

    assert main([str(path)]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["notebooks"][0]["headings"][0]["title"] == "Objectif"
