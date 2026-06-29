from pathlib import Path

from tpstudio.models import Metadata, Notebook, NotebookCell, PedagogicalBlock, Section, TP


def test_tp_model_exposes_common_fields():
    tp = TP(
        metadata=Metadata(title="Lois de Snell Descartes", source_tex=Path("tp.tex")),
        blocks=[
            PedagogicalBlock(
                kind="objectifs",
                title="Objectifs",
                items=["Vérifier les lois de Snell-Descartes"],
            ),
            PedagogicalBlock(
                kind="materiel",
                title="Matériel",
                items=["Laser"],
            ),
        ],
        sections=[Section(title="Première méthode", level=1)],
    )

    assert tp.title == "Lois de Snell Descartes"
    assert tp.objectives == ["Vérifier les lois de Snell-Descartes"]
    assert tp.equipment == ["Laser"]
    assert tp.annexes == []
    assert tp.questions == []
    assert tp.summary() == "TP(title='Lois de Snell Descartes', objectives=1, equipment=1, sections=1, questions=0, teacher_calls=0)"
    assert tp.block("objectifs") is not None

    data = tp.to_dict()
    assert data["metadata"]["title"] == "Lois de Snell Descartes"
    assert data["sections"][0]["title"] == "Première méthode"



def test_tp_model_can_hold_notebook():
    notebook = Notebook(
        cells=[
            NotebookCell(index=1, cell_type="markdown", source="Réponse : test"),
            NotebookCell(index=2, cell_type="code", source="x = 1"),
        ]
    )
    tp = TP(notebook=notebook)

    assert tp.notebook is notebook
    assert tp.notebook.cell_count == 2
    assert tp.notebook.response_cell_count == 1
    assert tp.to_dict()["notebook"]["cell_count"] == 2
