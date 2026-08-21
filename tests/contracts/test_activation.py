from pathlib import Path

from tpstudio.contracts import (
    ActivationStatus,
    CandidateConfidence,
    CandidateExtractionMode,
    CandidateItem,
    CandidateKind,
    CandidateProductionMatch,
    CandidateScientificContract,
    MatchConfidence,
    ValidationState,
    activate_validated_candidate_quantity,
)
from tpstudio.projects.torsion_pendulum import torsion_pendulum_teacher_project


def _contract(symbol: str | None = "q") -> CandidateScientificContract:
    return CandidateScientificContract(
        "synthetic",
        "statement.tex",
        (
            CandidateItem(
                "quantity-q-line-1",
                CandidateKind.QUANTITY,
                "statement.tex",
                (1, 1),
                f"Déterminer ${symbol or 'q'}$.",
                f"Déterminer {symbol or 'q'}.",
                CandidateExtractionMode.EXPLICIT,
                CandidateConfidence.HIGH,
                symbol,
                (),
                {},
            ),
        ),
    )


def _match(state: ValidationState, production_id: str = "quantity-q"):
    return CandidateProductionMatch(
        "quantity-q-line-1",
        production_id,
        MatchConfidence.HIGH,
        0.9,
        ("kind compatible",),
        state,
    )


def _synthetic_plan():
    from tpstudio.expectations import (
        EvaluationBasis,
        ScientificProductionKind,
        ScientificProductionPlan,
        ScientificProductionSpec,
    )

    return ScientificProductionPlan(
        "synthetic",
        "Synthetic",
        (
            ScientificProductionSpec(
                "quantity-q", "Quantity q", ScientificProductionKind.QUANTITY,
                (EvaluationBasis.STRUCTURAL,),
            ),
        ),
    )


def test_proposed_high_match_never_activates():
    result = activate_validated_candidate_quantity(
        _match(ValidationState.PROPOSED), _contract(), _synthetic_plan()
    )
    assert result.status is ActivationStatus.NOT_ACCEPTED
    assert result.expectation is None


def test_rejected_match_never_activates():
    result = activate_validated_candidate_quantity(
        _match(ValidationState.REJECTED), _contract(), _synthetic_plan()
    )
    assert result.status is ActivationStatus.NOT_ACCEPTED
    assert result.expectation is None


def test_accepted_generic_quantity_creates_minimal_expectation_with_provenance():
    result = activate_validated_candidate_quantity(
        _match(ValidationState.ACCEPTED), _contract(), _synthetic_plan()
    )
    assert result.status is ActivationStatus.ACTIVATED
    assert result.expectation is not None
    assert result.expectation.production_id == "quantity-q"
    assert result.expectation.canonical_symbol == "q"
    assert result.expectation.canonical_unit is None
    assert result.source_document == "statement.tex"
    assert result.source_location == (1, 1)
    assert result.source_text == "Déterminer $q$."
    assert result.validation_state is ValidationState.ACCEPTED


def test_accepted_candidate_without_scientific_symbol_is_explicitly_insufficient():
    result = activate_validated_candidate_quantity(
        _match(ValidationState.ACCEPTED), _contract(None), _synthetic_plan()
    )
    assert result.status is ActivationStatus.INSUFFICIENT_INFORMATION
    assert result.expectation is None


def test_pendulum_m_jb_and_en_can_be_activated_without_fixed_values():
    from tpstudio.contracts import extract_candidate_scientific_contract

    contract = extract_candidate_scientific_contract(
        Path("/Users/daniel/Downloads/sources tex/Pendule de torsion.tex")
    )
    project = torsion_pendulum_teacher_project()
    targets = {
        "m": "dynamic_mass",
        "J_b": "bar_inertia",
        "E_n": "normalized_error",
    }
    for symbol, production_id in targets.items():
        candidate = next(item for item in contract.items if item.scientific_symbol == symbol)
        result = activate_validated_candidate_quantity(
            CandidateProductionMatch(
                candidate.candidate_id,
                production_id,
                MatchConfidence.HIGH,
                0.9,
                ("explicit teacher acceptance",),
                ValidationState.ACCEPTED,
            ),
            contract,
            project.scientific_production_plan,
        )
        assert result.status is ActivationStatus.ACTIVATED
        assert result.expectation is not None
        assert result.expectation.canonical_symbol == symbol
        assert result.source_document == contract.source_document
    assert len(project.quantity_expectation_set) == 0
