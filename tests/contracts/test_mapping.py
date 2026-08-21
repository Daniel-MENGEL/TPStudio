from types import SimpleNamespace
from pathlib import Path

from tpstudio.contracts import (
    CandidateConfidence,
    CandidateExtractionMode,
    CandidateItem,
    CandidateKind,
    CandidateScientificContract,
    MatchConfidence,
    extract_candidate_scientific_contract,
    propose_candidate_production_matches,
)
from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    EvaluationBasis,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
)
from tpstudio.projects.torsion_pendulum import torsion_pendulum_teacher_project


def _candidate(candidate_id, kind, text, symbol=None, line=1, metadata=None):
    return CandidateItem(
        candidate_id,
        kind,
        "statement.tex",
        (line, line),
        text,
        text,
        CandidateExtractionMode.EXPLICIT,
        CandidateConfidence.HIGH,
        symbol,
        (),
        metadata or {},
    )


def _configuration(specs, markers):
    plan = ScientificProductionPlan("synthetic", "Synthetic plan", tuple(specs))
    bindings = tuple(
        CellProductionBinding(
            f"binding-{production_id}",
            production_id,
            NotebookCellSelector(NotebookCellSelectorKind.SOURCE_MARKER, marker),
            CellTextScope.full_source(),
        )
        for production_id, marker in markers.items()
    )
    return SimpleNamespace(
        scientific_production_plan=plan,
        notebook_binding_plan=NotebookBindingPlan(
            "synthetic-bindings", "Synthetic bindings", plan, bindings
        ),
    )


def _spec(identifier, label, kind):
    return ScientificProductionSpec(identifier, label, kind, (EvaluationBasis.STRUCTURAL,))


def test_generic_mapping_uses_kind_symbol_and_binding_without_domain_table():
    configuration = _configuration(
        (
            _spec("velocity", "Vitesse", ScientificProductionKind.QUANTITY),
            _spec("gravity", "Accélération", ScientificProductionKind.QUANTITY),
            _spec("trajectory_graph", "Trajectoire", ScientificProductionKind.PLOT),
        ),
        {"velocity": "v = ?", "gravity": "g = ?", "trajectory_graph": "plt.plot(?, ?,"},
    )
    contract = CandidateScientificContract(
        "synthetic", "statement.tex",
        (
            _candidate("quantity-v-line-1", CandidateKind.QUANTITY, "Mesurer $v$", "v"),
            _candidate("quantity-g-line-2", CandidateKind.QUANTITY, "Déterminer $g$", "g", 2),
            _candidate("graph-line-3", CandidateKind.GRAPH, "Tracer la trajectoire", line=3),
        ),
    )
    matches = propose_candidate_production_matches(contract, configuration)
    assert {match.production_id for match in matches} == {"velocity", "gravity", "trajectory_graph"}
    assert all(match.confidence in (MatchConfidence.HIGH, MatchConfidence.MEDIUM) for match in matches)


def test_opaque_production_ids_still_map_from_symbol_and_binding():
    configuration = _configuration(
        (
            _spec("production-1", "Production A", ScientificProductionKind.QUANTITY),
            _spec("production-2", "Production B", ScientificProductionKind.QUANTITY),
        ),
        {"production-1": "v = ?", "production-2": "J_b = ?"},
    )
    contract = CandidateScientificContract(
        "synthetic", "statement.tex",
        (
            _candidate("quantity-v-line-1", CandidateKind.QUANTITY, "Mesurer $v$", "v"),
            _candidate("quantity-jb-line-2", CandidateKind.QUANTITY, "Déterminer $J_b$", "J_b", 2),
        ),
    )
    matches = propose_candidate_production_matches(contract, configuration)
    assert {match.production_id for match in matches} == {"production-1", "production-2"}
    assert all(match.confidence in (MatchConfidence.HIGH, MatchConfidence.MEDIUM) for match in matches)
    assert all(any("symbole compatible" in reason for reason in match.reasons) for match in matches)


def test_ambiguous_same_symbol_is_explicit():
    configuration = _configuration(
        (
            _spec("first_x", "Première valeur", ScientificProductionKind.QUANTITY),
            _spec("second_x", "Seconde valeur", ScientificProductionKind.QUANTITY),
        ),
        {"first_x": "x = ?", "second_x": "x = ?"},
    )
    contract = CandidateScientificContract(
        "synthetic", "statement.tex",
        (_candidate("quantity-x-line-1", CandidateKind.QUANTITY, "Mesurer $x$", "x"),),
    )
    matches = propose_candidate_production_matches(contract, configuration)
    assert {match.production_id for match in matches} == {"first_x", "second_x"}
    assert all(match.confidence is not MatchConfidence.HIGH for match in matches)
    assert all("ambiguïté" in match.reasons[-1] for match in matches)


def test_provided_relation_is_never_high_automatically():
    configuration = _configuration(
        (_spec("model_relation", "Relation énergie", ScientificProductionKind.RELATION),),
        {"model_relation": "E ="},
    )
    contract = CandidateScientificContract(
        "synthetic", "statement.tex",
        (_candidate(
            "relation-line-1", CandidateKind.RELATION, "$E=mc^2$", "E", 1,
            metadata={"relation_role": "provided_scientific_context"},
        ),),
    )
    matches = propose_candidate_production_matches(contract, configuration)
    assert all(match.confidence is not MatchConfidence.HIGH for match in matches)


def test_pendulum_mapping_exposes_useful_matches_and_real_ambiguities():
    contract = extract_candidate_scientific_contract(Path("/Users/daniel/Downloads/sources tex/Pendule de torsion.tex"))
    matches = propose_candidate_production_matches(contract, torsion_pendulum_teacher_project())

    def for_candidate(candidate_id):
        return tuple(match for match in matches if match.candidate_id == candidate_id)

    assert any(match.production_id == "dynamic_mass" and match.confidence is MatchConfidence.HIGH
               for match in for_candidate("quantity-m-line-92"))
    assert any(match.production_id == "dynamic_thickness" and match.confidence is MatchConfidence.HIGH
               for match in for_candidate("quantity-l-line-92"))
    assert any(match.production_id == "dynamic_graph" for match in for_candidate("graph-regression-line-94"))
    c_dynamic = for_candidate("quantity-c-line-95")
    assert {match.production_id for match in c_dynamic} >= {"dynamic_torsion_constant", "static_torsion_constant"}
    assert all(match.confidence is not MatchConfidence.HIGH for match in c_dynamic)
    assert any(match.production_id == "normalized_error"
               and match.confidence in (MatchConfidence.MEDIUM, MatchConfidence.HIGH)
               for match in for_candidate("quantity-e-n-line-181"))
    assert not any(match.candidate_id.startswith("relation-") and match.confidence is MatchConfidence.HIGH
                   for match in matches)
