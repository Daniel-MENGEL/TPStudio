from __future__ import annotations

import nbformat

from tpstudio.numerical_consistency import (
    _main_result_value,
    _response_result_values,
    analyze_numerical_consistency_in_notebooks,
)


def _stream(text: str):
    return nbformat.v4.new_output(
        output_type="stream",
        name="stdout",
        text=text,
    )


def test_extracts_main_estimator_but_ignores_uncertainty() -> None:
    cell = nbformat.v4.new_code_cell(
        "print('test')",
        outputs=[
            _stream(
                "Meilleur estimateur : n= 2.989\n"
                "Incertitude type : u(n)= 0.029\n"
            )
        ],
    )

    assert _main_result_value(cell) == 2.989


def test_extracts_result_values_from_written_response() -> None:
    source = (
        "**Réponse :** Avec l'angle mesuré, on obtient un indice "
        "proche de 1,49. L'indice attendu est voisin de 1,5."
    )

    values = _response_result_values(source)

    assert values == [1.49, 1.5]


def test_ignores_normalized_difference_threshold() -> None:
    source = (
        "**Réponse :** Comme l'écart normalisé est inférieur à 2, "
        "les résultats sont compatibles."
    )

    assert _response_result_values(source) == []


def test_detects_code_vs_written_result_mismatch() -> None:
    model = nbformat.v4.new_notebook(cells=[])

    copy = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Première méthode"
            ),
            nbformat.v4.new_code_cell(
                "n = 2 / np.sin(il)",
                outputs=[
                    _stream(
                        "Meilleur estimateur : n= 2.99\n"
                    )
                ],
            ),
            nbformat.v4.new_markdown_cell(
                "**Réponse :** On obtient un indice proche de 1,49."
            ),
        ]
    )

    findings = analyze_numerical_consistency_in_notebooks(
        model,
        copy,
    )

    assert len(findings) == 1
    assert findings[0].code_value == 2.99
    assert findings[0].expected_value == 1.49
    assert findings[0].reference_kind == "written"


def test_close_code_and_written_values_are_not_flagged() -> None:
    model = nbformat.v4.new_notebook(cells=[])

    copy = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Première méthode"
            ),
            nbformat.v4.new_code_cell(
                "n = 1 / np.sin(il)",
                outputs=[
                    _stream(
                        "Meilleur estimateur : n= 1.49\n"
                    )
                ],
            ),
            nbformat.v4.new_markdown_cell(
                "**Réponse :** On obtient un indice proche de 1,50."
            ),
        ]
    )

    findings = analyze_numerical_consistency_in_notebooks(
        model,
        copy,
    )

    assert findings == []


def test_detects_last_method_mismatch_using_later_conclusion() -> None:
    model = nbformat.v4.new_notebook(cells=[])

    copy = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Dernière méthode"
            ),
            nbformat.v4.new_code_cell(
                "n = sini2 / sini1",
                outputs=[
                    _stream(
                        "Meilleur estimateur : 0.668\n"
                    )
                ],
            ),
            nbformat.v4.new_markdown_cell(
                "**Réponse :** Comme l'écart normalisé est inférieur à 2, "
                "les résultats sont compatibles."
            ),
            nbformat.v4.new_markdown_cell(
                "### Conclusion\n\n"
                "**Réponse :** Les méthodes donnent un indice autour de 1,5."
            ),
        ]
    )

    findings = analyze_numerical_consistency_in_notebooks(
        model,
        copy,
    )

    assert len(findings) == 1
    assert findings[0].expected_value == 1.5
