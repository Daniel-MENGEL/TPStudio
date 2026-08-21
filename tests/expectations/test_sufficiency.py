from tpstudio.expectations import (
    ExpectedQuantity,
    ExpectationSufficiency,
    PresenceRequirement,
    assess_expectation_sufficiency,
)


def test_symbol_only_quantity_is_structural_only():
    expectation = ExpectedQuantity(
        "q", "q",
        unit_requirement=PresenceRequirement.OPTIONAL,
        uncertainty_requirement=PresenceRequirement.IGNORE,
    )
    assessment = assess_expectation_sufficiency(expectation)
    assert assessment.sufficiency is ExpectationSufficiency.STRUCTURAL_ONLY
    assert not assessment.is_analyzable
    assert "only requires presence" in assessment.reasons[0]


def test_quantity_with_explicit_evaluable_policy_is_analyzable():
    expectation = ExpectedQuantity(
        "q", "q",
        canonical_unit="m",
        unit_requirement=PresenceRequirement.REQUIRED,
    )
    assessment = assess_expectation_sufficiency(expectation)
    assert assessment.sufficiency is ExpectationSufficiency.ANALYZABLE
    assert assessment.is_analyzable
