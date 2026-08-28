from decimal import Decimal
from types import SimpleNamespace

import pytest

from tpstudio.grading import (
    FormativeGradingProfile,
    RubricCriterion,
    RubricDecision,
    RubricLevel,
    build_formative_grade_proposal,
)
from tpstudio.projects import FIRST_LAB_FORMATIVE_GRADING_PROFILE
from tpstudio.projects import suggest_first_lab_rubric
from tpstudio.semantic_analysis import SemanticRole


def _decisions(level: RubricLevel):
    return tuple(
        RubricDecision(item.criterion_id, level)
        for item in FIRST_LAB_FORMATIVE_GRADING_PROFILE.criteria
    )


def test_first_lab_profile_starts_at_fifteen_for_satisfactory_work() -> None:
    result = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        _decisions(RubricLevel.SATISFACTORY),
    )
    assert result.base_score == Decimal("15")
    assert result.bonus == Decimal("0.0")
    assert result.deduction == Decimal("0.0")
    assert result.proposed_score == Decimal("15.0")


def test_first_lab_profile_rewards_very_good_work_up_to_twenty() -> None:
    result = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        _decisions(RubricLevel.VERY_GOOD),
    )
    assert result.bonus == Decimal("5.0")
    assert result.proposed_score == Decimal("20.0")


def test_first_lab_profile_uses_moderate_deductions() -> None:
    partial = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        _decisions(RubricLevel.PARTIAL),
    )
    absent = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        _decisions(RubricLevel.ABSENT),
    )
    assert partial.deduction == Decimal("3.5")
    assert partial.proposed_score == Decimal("11.5")
    assert absent.deduction == Decimal("7.0")
    assert absent.proposed_score == Decimal("8.0")


def test_profile_requires_complete_ordered_teacher_decisions() -> None:
    with pytest.raises(ValueError, match="ordonnée"):
        build_formative_grade_proposal(
            FIRST_LAB_FORMATIVE_GRADING_PROFILE,
            _decisions(RubricLevel.SATISFACTORY)[:-1],
        )


def test_profile_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="somme"):
        FormativeGradingProfile(
            "bad", "project", "Bad", Decimal("15"), Decimal("5"), Decimal("7"),
            (RubricCriterion("one", "One", "Description", Decimal("0.5")),),
        )


def _semantic(role, response):
    return SimpleNamespace(
        contract=SimpleNamespace(semantic_role=role, criteria=()),
        student_response=response,
        result=None,
    )


def test_first_lab_suggestions_distinguish_complete_and_empty_copies() -> None:
    empty = SimpleNamespace(
        project_id="first-lab-measurements",
        semantic_response_analyses=(),
        quantity_evaluations=(),
        graph_evaluations=(),
        has_placeholders=True,
        has_unexecuted_code=True,
    )
    empty_suggestions = suggest_first_lab_rubric(empty)
    assert tuple(item.decision.level for item in empty_suggestions) == (
        RubricLevel.ABSENT,
        RubricLevel.ABSENT,
        RubricLevel.ABSENT,
        RubricLevel.ABSENT,
        RubricLevel.ABSENT,
    )
    empty_grade = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        tuple(item.decision for item in empty_suggestions),
    )
    assert empty_grade.proposed_score == Decimal("8.0")

    semantic = (
        _semantic(SemanticRole.OBJECTIVE, "objectif dynamique"),
        _semantic(SemanticRole.OBJECTIVE, "objectif statique"),
        _semantic(SemanticRole.PROTOCOL, "protocole dynamique"),
        _semantic(SemanticRole.PROTOCOL, "protocole statique"),
        _semantic(SemanticRole.INTERPRETATION, "résultats interprétés"),
        _semantic(SemanticRole.CONCLUSION, "conclusion"),
    )
    quantity = SimpleNamespace(
        assessment=SimpleNamespace(
            selected_observation=object(), is_structurally_satisfied=True
        )
    )
    graph = SimpleNamespace(
        observation=SimpleNamespace(figure_output_present=True),
        orientation_status=SimpleNamespace(value="matches"),
        label_status=SimpleNamespace(value="matches"),
        regression_status=SimpleNamespace(value="missing"),
        expectation=SimpleNamespace(regression_required=False),
    )
    complete = SimpleNamespace(
        project_id="first-lab-measurements",
        semantic_response_analyses=semantic,
        quantity_evaluations=(quantity, quantity, quantity, quantity),
        graph_evaluations=(graph,),
        has_placeholders=False,
        has_unexecuted_code=False,
    )
    complete_suggestions = suggest_first_lab_rubric(complete)
    assert tuple(item.decision.level for item in complete_suggestions) == (
        RubricLevel.SATISFACTORY,
        RubricLevel.SATISFACTORY,
        RubricLevel.VERY_GOOD,
        RubricLevel.SATISFACTORY,
        RubricLevel.VERY_GOOD,
    )
    complete_grade = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        tuple(item.decision for item in complete_suggestions),
    )
    assert complete_grade.proposed_score > empty_grade.proposed_score
