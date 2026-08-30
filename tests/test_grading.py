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
from tpstudio.projects.first_lab_grading import _results_suggestion
from tpstudio.semantic_analysis import SemanticCriterionStatus, SemanticRole


def _decisions(level: RubricLevel):
    return tuple(
        RubricDecision(item.criterion_id, level)
        for item in FIRST_LAB_FORMATIVE_GRADING_PROFILE.criteria
    )


def test_first_lab_profile_starts_at_sixteen_for_good_work() -> None:
    result = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        _decisions(RubricLevel.GOOD),
    )
    assert result.base_score == Decimal("16")
    assert result.bonus == Decimal("0.0")
    assert result.deduction == Decimal("0.0")
    assert result.proposed_score == Decimal("16.0")


def test_first_lab_profile_rewards_very_good_work_up_to_twenty() -> None:
    result = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        _decisions(RubricLevel.VERY_GOOD),
    )
    assert result.bonus == Decimal("4.0")
    assert result.proposed_score == Decimal("20.0")


def test_first_lab_profile_uses_moderate_deductions() -> None:
    partial = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        _decisions(RubricLevel.PARTIAL),
    )
    to_review = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        _decisions(RubricLevel.TO_REVIEW),
    )
    absent = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        _decisions(RubricLevel.ABSENT),
    )
    assert partial.deduction == Decimal("4.0")
    assert partial.proposed_score == Decimal("12.0")
    assert to_review.deduction == Decimal("8.0")
    assert to_review.proposed_score == Decimal("8.0")
    assert absent.deduction == Decimal("12.0")
    assert absent.proposed_score == Decimal("4.0")


def test_profile_requires_complete_ordered_teacher_decisions() -> None:
    with pytest.raises(ValueError, match="ordonnée"):
        build_formative_grade_proposal(
            FIRST_LAB_FORMATIVE_GRADING_PROFILE,
            _decisions(RubricLevel.GOOD)[:-1],
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
    assert empty_grade.proposed_score == Decimal("4.0")

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
        RubricLevel.GOOD,
        RubricLevel.GOOD,
        RubricLevel.VERY_GOOD,
        RubricLevel.GOOD,
        RubricLevel.VERY_GOOD,
    )
    complete_grade = build_formative_grade_proposal(
        FIRST_LAB_FORMATIVE_GRADING_PROFILE,
        tuple(item.decision for item in complete_suggestions),
    )
    assert complete_grade.proposed_score > empty_grade.proposed_score


def test_first_lab_results_are_not_very_good_with_too_few_linear_points() -> None:
    quantity = SimpleNamespace(
        assessment=SimpleNamespace(
            selected_observation=object(), is_structurally_satisfied=True
        )
    )
    graph = SimpleNamespace(
        observation=SimpleNamespace(figure_output_present=True),
        orientation_status=SimpleNamespace(value="matches"),
        label_status=SimpleNamespace(value="matches"),
        regression_status=SimpleNamespace(value="matches"),
        expectation=SimpleNamespace(regression_required=True),
    )
    analysis = SimpleNamespace(
        project_id="first-lab-measurements",
        semantic_response_analyses=(),
        quantity_evaluations=(quantity,),
        graph_evaluations=(graph,),
        regression_model_analyses=(SimpleNamespace(
            degree=1,
            diagnostics=("trop_peu_de_points_pour_regression_lineaire",),
        ),),
        has_placeholders=False,
        has_unexecuted_code=False,
    )

    suggestion = next(
        item for item in suggest_first_lab_rubric(analysis)
        if item.decision.criterion_id == "results_presentation"
    )

    assert suggestion.decision.level is RubricLevel.PARTIAL
    assert "moins de cinq" in suggestion.rationale


def test_missing_units_in_written_results_require_review() -> None:
    quantity = SimpleNamespace(
        assessment=SimpleNamespace(
            selected_observation=object(), is_structurally_satisfied=True
        )
    )
    semantic = tuple(
        SimpleNamespace(
            result=SimpleNamespace(
                diagnostics=(),
                criterion_results=(SimpleNamespace(
                    criterion_id=criterion_id,
                    status=SemanticCriterionStatus.NOT_FOUND,
                ),),
            )
        )
        for criterion_id in (
            "period_with_uncertainty",
            "dynamic_stiffness_with_uncertainty",
            "static_stiffness_with_uncertainty",
        )
    )
    analysis = SimpleNamespace(
        semantic_response_analyses=semantic,
        quantity_evaluations=(quantity, quantity, quantity),
        graph_evaluations=(),
        regression_model_analyses=(),
    )

    suggestion = _results_suggestion(analysis)

    assert suggestion.decision.level is RubricLevel.TO_REVIEW
    assert "unités ou incertitudes" in suggestion.rationale
