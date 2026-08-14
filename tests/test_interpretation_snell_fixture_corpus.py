"""A73c1.1 audit benchmark for the independent Snell-Descartes corpus."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import nbformat

from tpstudio.interpretation import InterpretationContext, evaluate_interpretation_cells


FIXTURE_PATH = Path(__file__).parent / "fixtures/interpretation/snell_descartes/a73c1_1_snell_descartes_cases.json"


def _evaluate_case(case: dict) -> str:
    expectation_id = case["id"]
    scientific = case["scientific_context"]
    context = InterpretationContext(
        expectation_id=expectation_id,
        local_prompt=case["local_prompt"],
        local_scientific_context=tuple(str(value) for value in scientific.values()),
    )
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(
            case["student_answer"],
            metadata={"tpstudio": {"role": "interpretation_response", "expectation_id": expectation_id}},
        )
    ])
    evaluation = evaluate_interpretation_cells(notebook, contexts={expectation_id: context})[0]
    assert evaluation.status.name == case["expected_status"]
    assert evaluation.classification is not None
    return evaluation.classification.name


def test_snell_descartes_fixture_corpus_reports_actual_classifications():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = payload["cases"]
    assert len(cases) == 15
    assert Counter(case["expected_classification"] for case in cases) == Counter({
        "CLEARLY_SUFFICIENT": 5,
        "CLEARLY_INSUFFICIENT": 5,
        "AMBIGUOUS": 5,
    })

    rows = []
    matrix = Counter()
    for case in cases:
        actual = _evaluate_case(case)
        expected = case["expected_classification"]
        match = actual == expected
        rows.append((case["id"], expected, actual, match))
        matrix[(expected, actual)] += 1

    print("\nA73c1.1 — corpus Snell-Descartes")
    for case_id, expected, actual, match in rows:
        print(f"{case_id} | expected={expected} | actual={actual} | match={'oui' if match else 'non'}")

    labels = ("CLEARLY_SUFFICIENT", "CLEARLY_INSUFFICIENT", "AMBIGUOUS")
    print("\nMatrice de confusion (lignes attendu, colonnes obtenu)")
    print("expected\\actual | " + " | ".join(labels))
    for expected in labels:
        print(expected + " | " + " | ".join(str(matrix[(expected, actual)]) for actual in labels))

    total_matches = sum(match for _, _, _, match in rows)
    print(f"\nCorrects: {total_matches}/{len(rows)} ({total_matches / len(rows):.1%})")
    for expected in labels:
        count = sum(matrix[(expected, actual)] for actual in labels)
        correct = matrix[(expected, expected)]
        print(f"{expected}: {correct}/{count} ({correct / count:.1%})")

    # Audit only: report disagreements without reimplementing or altering the engine.
    assert len(rows) == 15
