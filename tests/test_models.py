from pathlib import Path

from tpstudio.models import Metadata, PedagogicalBlock, Section, TP


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
    assert tp.summary() == "TP(title='Lois de Snell Descartes', objectives=1, equipment=1, sections=1, questions=0)"
    assert tp.block("objectifs") is not None

    data = tp.to_dict()
    assert data["metadata"]["title"] == "Lois de Snell Descartes"
    assert data["sections"][0]["title"] == "Première méthode"
