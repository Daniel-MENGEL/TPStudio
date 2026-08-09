from pathlib import Path

import nbformat

from tpstudio.protocol import (
    ProtocolStatus,
    evaluate_protocol_cells,
    manipulations_from_latex,
    prepare_notebook_with_protocol_cells,
    protocol_cell_metadata,
    snells_laws_manipulations,
)


def _notebook(*cells):
    return nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell(cell) for cell in cells])


def test_snells_latex_sections_become_three_protocol_manipulations(tmp_path: Path) -> None:
    tex = tmp_path / "statement.tex"
    tex.write_text(
        r"""\section*{Présentation du dispositif}
\subsection*{Première méthode de mesure de l'indice}
\subsection*{Seconde méthode de mesure de l'indice}
\subsection*{Vérification de la loi de la réfraction et dernière méthode de mesure de l'indice}
""",
        encoding="utf-8",
    )
    values = manipulations_from_latex(tex)
    assert [item.title for item in values] == [
        "Première méthode de mesure de l'indice",
        "Seconde méthode de mesure de l'indice",
        "Vérification de la loi de la réfraction et dernière méthode de mesure de l'indice",
    ]


def test_preparation_is_ordered_and_idempotent() -> None:
    manipulations = snells_laws_manipulations()
    notebook = _notebook(
        "Introduction",
        "Première méthode de mesure de l'indice\nConsigne",
        "Résultats première méthode",
        "Seconde méthode de mesure de l'indice\nConsigne",
        "Résultats seconde méthode",
        "Vérification de la loi de la réfraction et dernière méthode de mesure de l'indice\nConsigne",
    )
    prepared = prepare_notebook_with_protocol_cells(notebook, manipulations)
    prepared_again = prepare_notebook_with_protocol_cells(prepared, manipulations)
    protocol_cells = [
        cell for cell in prepared_again.cells
        if cell.metadata.get("tpstudio", {}).get("role") == "protocol_response"
    ]
    assert len(protocol_cells) == 3
    assert len([
        cell for cell in prepared_again.cells
        if cell.source == "Résultats première méthode"
    ]) == 1
    assert prepared_again.cells == prepared.cells


def test_existing_protocol_response_is_preserved() -> None:
    manipulation = snells_laws_manipulations()[0]
    notebook = _notebook("Première méthode de mesure de l'indice")
    cell = nbformat.v4.new_markdown_cell(
        "### Protocole expérimental\n\nNous plaçons le disque, alignons le rayon et relevons plusieurs angles."
    )
    cell.metadata = protocol_cell_metadata(manipulation)
    notebook.cells.append(cell)
    prepared = prepare_notebook_with_protocol_cells(notebook, (manipulation,))
    assert len(prepared.cells) == 2
    assert "Nous plaçons" in prepared.cells[1].source


def test_duplicate_protocol_cells_are_not_silently_repaired() -> None:
    manipulation = snells_laws_manipulations()[0]
    notebook = _notebook()
    for _ in range(2):
        cell = nbformat.v4.new_markdown_cell("### Protocole expérimental")
        cell.metadata = protocol_cell_metadata(manipulation)
        notebook.cells.append(cell)
    prepared = prepare_notebook_with_protocol_cells(notebook, (manipulation,))
    assert len(prepared.cells) == 2
    assert evaluate_protocol_cells(prepared, (manipulation,))[0].status is ProtocolStatus.NOT_EVALUABLE


def test_protocol_statuses_are_local_to_explicit_cells() -> None:
    manipulations = snells_laws_manipulations()[:2]
    notebook = _notebook("On place le disque et on relève plusieurs angles dans un tableau.")
    cell = nbformat.v4.new_markdown_cell("### Protocole expérimental\n\nVoir énoncé")
    cell.metadata = protocol_cell_metadata(manipulations[0])
    notebook.cells.append(cell)
    prepared = prepare_notebook_with_protocol_cells(notebook, manipulations)
    statuses = evaluate_protocol_cells(prepared, manipulations)
    assert statuses[0].status is ProtocolStatus.MISSING
    assert statuses[1].status is ProtocolStatus.MISSING


def test_substantial_list_protocol_is_present() -> None:
    manipulation = snells_laws_manipulations()[0]
    notebook = _notebook()
    cell = nbformat.v4.new_markdown_cell(
        "### Protocole expérimental\n\n- placer le disque gradué\n- aligner le rayon\n- relever les angles"
    )
    cell.metadata = protocol_cell_metadata(manipulation)
    notebook.cells.append(cell)
    assert evaluate_protocol_cells(notebook, (manipulation,))[0].status is ProtocolStatus.PRESENT


def test_empty_response_is_missing_and_uses_response_index() -> None:
    manipulation = snells_laws_manipulations()[0]
    notebook = _notebook()
    cell = nbformat.v4.new_markdown_cell("### Protocole\n\nÀ compléter :")
    cell.metadata = protocol_cell_metadata(manipulation)
    notebook.cells.append(cell)
    result = evaluate_protocol_cells(notebook, (manipulation,))[0]
    assert result.status is ProtocolStatus.MISSING
    assert result.cell_index == 0
    assert result.anchor_cell_index is None


def test_missing_response_uses_unambiguous_section_anchor() -> None:
    manipulation = snells_laws_manipulations()[0]
    notebook = _notebook("1. Mesure par angle limite\nConsigne professeur")
    result = evaluate_protocol_cells(notebook, (manipulation,))[0]
    assert result.status is ProtocolStatus.MISSING
    assert result.cell_index is None
    assert result.anchor_cell_index == 0


def test_missing_response_without_section_has_no_anchor() -> None:
    manipulation = snells_laws_manipulations()[0]
    result = evaluate_protocol_cells(_notebook("Introduction générale"), (manipulation,))[0]
    assert result.status is ProtocolStatus.MISSING
    assert result.cell_index is None
    assert result.anchor_cell_index is None


def test_long_professor_prompt_never_counts_as_student_response() -> None:
    manipulation = snells_laws_manipulations()[0]
    prompt = (
        "Première méthode de mesure de l'indice. Décrire le dispositif, placer le "
        "demi-cylindre, choisir plusieurs angles, lire les angles observés, estimer "
        "les incertitudes, comparer les mesures, organiser les résultats et expliquer "
        "la méthode avec précision pour permettre une reproduction complète de "
        "l'expérience par un autre groupe de TP."
    )
    notebook = _notebook(prompt)
    prepared = prepare_notebook_with_protocol_cells(notebook, (manipulation,))
    assert prepared.cells[0].source == prompt
    assert evaluate_protocol_cells(prepared, (manipulation,))[0].status is ProtocolStatus.MISSING
    response = next(
        cell for cell in prepared.cells
        if cell.metadata.get("tpstudio", {}).get("role") == "protocol_response"
    )
    response.source = (
        "### Protocole\n\nNous plaçons le demi-cylindre, choisissons plusieurs angles "
        "et relevons les angles de réfraction dans un tableau. Nous répétons la mesure "
        "pour chaque position."
    )
    assert evaluate_protocol_cells(prepared, (manipulation,))[0].status is ProtocolStatus.PRESENT
