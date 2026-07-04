from __future__ import annotations

import nbformat

from tpstudio.code_semantics import (
    analyze_code_semantics_in_notebooks,
)


def _notebook(*code_sources: str):
    cells = []

    for index, source in enumerate(code_sources):
        cells.append(
            nbformat.v4.new_markdown_cell(
                f"## Partie {index + 1}"
            )
        )
        cells.append(
            nbformat.v4.new_code_cell(source)
        )

    return nbformat.v4.new_notebook(cells=cells)


def test_detects_changed_numeric_constant_in_formula() -> None:
    model = _notebook("n = 1 / np.sin(il)")
    copy = _notebook("n = 2 / np.sin(il)")

    findings = analyze_code_semantics_in_notebooks(
        model,
        copy,
    )

    assert len(findings) == 1
    assert findings[0].kind == "changed_constant"
    assert findings[0].target == "n"
    assert findings[0].model_expression == "1 / np.sin(il)"
    assert findings[0].copy_expression == "2 / np.sin(il)"


def test_detects_swapped_quotient_operands() -> None:
    model = _notebook("n = sini1 / sini2")
    copy = _notebook("n = sini2 / sini1")

    findings = analyze_code_semantics_in_notebooks(
        model,
        copy,
    )

    assert len(findings) == 1
    assert findings[0].kind == "swapped_quotient"
    assert "inversés" in findings[0].message


def test_does_not_flag_identical_formula() -> None:
    model = _notebook("n = 1 / np.sin(il)")
    copy = _notebook("n = 1 / np.sin(il)")

    findings = analyze_code_semantics_in_notebooks(
        model,
        copy,
    )

    assert findings == []


def test_does_not_flag_different_measurement_arrays() -> None:
    model = _notebook(
        "i1 = np.array([10, 20, 30])\n"
        "i2 = np.array([7, 13, 19])"
    )
    copy = _notebook(
        "i1 = np.array([11, 21, 31])\n"
        "i2 = np.array([8, 14, 20])"
    )

    findings = analyze_code_semantics_in_notebooks(
        model,
        copy,
    )

    assert findings == []


def test_detects_changed_binary_operator() -> None:
    model = _notebook("n = sini1 / sini2")
    copy = _notebook("n = sini1 * sini2")

    findings = analyze_code_semantics_in_notebooks(
        model,
        copy,
    )

    assert len(findings) == 1
    assert findings[0].kind == "changed_operator"

def test_detects_changed_constant_when_model_cell_is_split_in_copy() -> None:
    model = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "## Première méthode"
            ),
            nbformat.v4.new_code_cell(
                "import numpy as np\n"
                "n = 1 / np.sin(il)"
            ),
        ]
    )

    copy = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "## Première méthode"
            ),
            nbformat.v4.new_code_cell(
                "import numpy as np"
            ),
            nbformat.v4.new_markdown_cell(
                "## Protocole"
            ),
            nbformat.v4.new_code_cell(
                "il = 42"
            ),
            nbformat.v4.new_code_cell(
                "n = 2 / np.sin(il)"
            ),
        ]
    )

    findings = analyze_code_semantics_in_notebooks(
        model,
        copy,
    )

    assert len(findings) == 1
    assert findings[0].kind == "changed_constant"
    assert findings[0].copy_cell_index == 4


def test_detects_swapped_quotient_after_extra_copy_cells() -> None:
    model = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "## Dernière méthode"
            ),
            nbformat.v4.new_code_cell(
                "n = sini1 / sini2"
            ),
        ]
    )

    copy = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "## Dernière méthode"
            ),
            nbformat.v4.new_code_cell(
                "i1 = np.array([10, 20])"
            ),
            nbformat.v4.new_code_cell(
                "i2 = np.array([7, 13])"
            ),
            nbformat.v4.new_code_cell(
                "sini1 = np.sin(i1)"
            ),
            nbformat.v4.new_code_cell(
                "sini2 = np.sin(i2)"
            ),
            nbformat.v4.new_code_cell(
                "n = sini2 / sini1"
            ),
        ]
    )

    findings = analyze_code_semantics_in_notebooks(
        model,
        copy,
    )

    assert len(findings) == 1
    assert findings[0].kind == "swapped_quotient"
    assert findings[0].copy_cell_index == 5


def test_same_target_occurrences_are_paired_by_formula_similarity() -> None:
    model = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "n = 1 / np.sin(il)"
            ),
            nbformat.v4.new_code_cell(
                "n = np.sin(i1) / np.sin(i2)"
            ),
            nbformat.v4.new_code_cell(
                "n = sini1 / sini2"
            ),
        ]
    )

    copy = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "n = 2 / np.sin(il)"
            ),
            nbformat.v4.new_code_cell(
                "x = 123"
            ),
            nbformat.v4.new_code_cell(
                "n = np.sin(i1) / np.sin(i2)"
            ),
            nbformat.v4.new_code_cell(
                "n = sini2 / sini1"
            ),
        ]
    )

    findings = analyze_code_semantics_in_notebooks(
        model,
        copy,
    )

    assert len(findings) == 2
    assert {
        finding.kind
        for finding in findings
    } == {
        "changed_constant",
        "swapped_quotient",
    }

