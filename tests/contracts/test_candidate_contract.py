from pathlib import Path

import pytest

from tpstudio.contracts import (
    CandidateConfidence,
    CandidateExtractionMode,
    CandidateItem,
    CandidateKind,
    CandidateScientificContract,
    extract_candidate_scientific_contract,
)


def _item(**overrides):
    values = dict(
        candidate_id="quantity-m-line-2",
        kind=CandidateKind.QUANTITY,
        source_document="statement.tex",
        source_location=(2, 2),
        source_text=r"\item Mesurer $m$.",
        normalized_text="Mesurer m.",
        extraction_mode=CandidateExtractionMode.EXPLICIT,
        confidence=CandidateConfidence.HIGH,
    )
    values.update(overrides)
    return CandidateItem(**values)


def test_candidate_item_preserves_raw_provenance_and_metadata():
    item = _item(metadata={"unit_required": True}, target_symbols=("m",), scientific_symbol="m")
    assert item.source_text == r"\item Mesurer $m$."
    assert item.source_location == (2, 2)
    assert item.metadata["unit_required"] is True
    assert item.scientific_symbol == "m"


def test_candidate_item_rejects_invalid_kind_and_provenance():
    with pytest.raises(TypeError):
        _item(kind="quantity")
    with pytest.raises(ValueError):
        _item(source_location=(0, 1))


def test_candidate_contract_allows_empty_but_requires_unique_ids():
    assert CandidateScientificContract("statement", "statement.tex").items == ()
    with pytest.raises(ValueError):
        CandidateScientificContract("statement", "statement.tex", (_item(), _item()))


def test_extracts_generic_quantities_and_rules_from_short_tex(tmp_path: Path):
    path = tmp_path / "statement.tex"
    path.write_text(
        r"""\title{TP}
\questions
\begin{list}{\textbullet}{}
\item Mesurer la vitesse $v$ et la hauteur $h$.
\item En déduire l'accélération $g$.
\item Pour 8 valeurs de $x>0$, effectuer une régression linéaire.
\item Comparer les résultats en calculant l'écart normalisé.
\end{list}
\indications La relation $y=ax+b$ est fournie.
\end{document}
""",
        encoding="utf-8",
    )
    contract = extract_candidate_scientific_contract(path)
    quantities = contract.by_kind(CandidateKind.QUANTITY)
    assert {item.scientific_symbol for item in quantities} >= {"v", "h", "g", "E_n"}
    assert any(item.kind is CandidateKind.GRAPH for item in contract.items)
    assert any(item.kind is CandidateKind.RELATION for item in contract.items)
    assert any(item.metadata.get("sample_count_exact") == 8 for item in contract.items)
    assert all(item.source_document == "statement.tex" for item in contract.items)
    assert all(item.source_text.startswith(("\\item", "\\indications")) for item in contract.items)


def test_normalized_error_is_an_autonomous_candidate(tmp_path: Path):
    path = tmp_path / "statement.tex"
    path.write_text(r"""\questions
\begin{list}{\textbullet}{}
\item Comparer les deux valeurs en calculant l'écart normalisé.
\end{list}
""", encoding="utf-8")
    contract = extract_candidate_scientific_contract(path)
    comparisons = contract.by_kind(CandidateKind.COMPARISON)
    errors = tuple(item for item in contract.items if item.scientific_symbol == "E_n")
    assert len(comparisons) == 1
    assert len(errors) == 1
    assert errors[0].metadata["derived_quantity_role"] == "normalized_error"
    assert errors[0].extraction_mode is CandidateExtractionMode.EXPLICIT
    assert errors[0].confidence is CandidateConfidence.HIGH
    assert errors[0].source_location == comparisons[0].source_location
    assert errors[0].target_symbols == ()


def test_same_line_candidates_receive_deterministic_collision_suffixes(tmp_path: Path):
    path = tmp_path / "same-line.tex"
    path.write_text(
        r"""\questions
\item Déterminer $x$. \item Déterminer $x$.
""",
        encoding="utf-8",
    )
    quantities = extract_candidate_scientific_contract(path).by_kind(CandidateKind.QUANTITY)
    assert [item.candidate_id for item in quantities] == [
        "quantity-x-line-2",
        "quantity-x-line-2-2",
    ]


def test_relation_after_questions_is_kept_but_procedure_is_not(tmp_path: Path):
    path = tmp_path / "late-relation.tex"
    path.write_text(
        r"""\questions
\item Mesurer $v$.
Texte scientifique ultérieur : $E=mc^2$.
\questions
\item Régler $theta_0$ puis relever $theta_eq$.
""",
        encoding="utf-8",
    )
    relations = extract_candidate_scientific_contract(path).by_kind(CandidateKind.RELATION)
    assert len(relations) == 1
    assert "E=mc^2" in relations[0].source_text


def test_relations_are_structural_and_symbol_neutral(tmp_path: Path):
    path = tmp_path / "relations.tex"
    path.write_text(
        r"""\section*{Modèles}
\indications
$E=mc^2$
\[U=RI\]
\(pV=nRT\)
$$y=ax+b$$
$v^2=v_0^2+2ax$
$Q=XZ^3/Y$
\questions
\item Régler $x=0$ puis relever la mesure.
\item Placer l'index à $q=7$.
\item Tourner jusqu'à $z=5$.
""",
        encoding="utf-8",
    )
    relations = extract_candidate_scientific_contract(path).by_kind(CandidateKind.RELATION)
    assert len(relations) == 6
    assert {item.metadata["relation_fragment"] for item in relations} >= {
        "E=mc^2", "U=RI", "pV=nRT", "y=ax+b", "v^2=v_0^2+2ax", "Q=XZ^3/Y",
    }
    assert not any("x=0" in item.source_text for item in relations)
    assert not any("q=7" in item.source_text for item in relations)
    assert not any("z=5" in item.source_text for item in relations)


def test_pendulum_candidates_are_neutral_and_traceable():
    path = Path("/Users/daniel/Downloads/sources tex/Pendule de torsion.tex")
    contract = extract_candidate_scientific_contract(path)
    source_lines = path.read_text(encoding="utf-8").splitlines()
    line_of = lambda fragment: source_lines.index(fragment) + 1
    quantities = contract.by_kind(CandidateKind.QUANTITY)
    symbols = {item.scientific_symbol for item in quantities}
    assert {"m", "L", "C", "J_b", "E_n"} <= symbols
    assert any(item.scientific_symbol == "C" and item.source_location == (line_of(next(line for line in source_lines if "En déduire" in line)),) * 2 for item in quantities)
    assert any(item.scientific_symbol == "C" and "mesure de $C$" in item.source_text for item in quantities)
    assert any(item.kind is CandidateKind.PROTOCOL and "protocole de mesure précise" in item.source_text for item in contract.items)
    assert any(item.kind is CandidateKind.PROTOCOL and "protocole de mesure de $C$" in item.source_text for item in contract.items)
    assert any(item.metadata.get("sample_count_exact") == 8 for item in contract.items)
    assert any(item.metadata.get("sample_count_min") == 6 for item in contract.items)
    assert any(item.kind is CandidateKind.GRAPH and item.metadata.get("model") == "AFFINE" for item in contract.items)
    static_line = line_of(next(line for line in source_lines if "On produira les forces" in line))
    assert any(item.kind is CandidateKind.RELATION and "C(\\theta_" in item.source_text for item in contract.items)
    static_relations = tuple(item for item in contract.by_kind(CandidateKind.RELATION)
                             if item.source_location == (static_line, static_line))
    assert len(static_relations) == 2
    assert {item.metadata["relation_fragment"] for item in static_relations} >= {"F=mg"}
    assert any("C=" in item.metadata["relation_fragment"] for item in static_relations)
    assert not any("Remonter le plateau" in item.source_text and item.kind is CandidateKind.RELATION for item in contract.items)
    assert all("dynamic_" not in item.candidate_id and "static_" not in item.candidate_id for item in contract.items)
