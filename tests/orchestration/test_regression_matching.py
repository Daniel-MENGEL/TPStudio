from __future__ import annotations

import nbformat
import pytest

from tpstudio.orchestration.graph_adapter import (
    GraphSeriesData,
    GraphSeriesRole,
    GraphSeriesSource,
    GraphSeriesStatus,
)
from tpstudio.regression import extract_regression_observations
from tpstudio.regression_matching import (
    RegressionSeriesMatchStatus,
    match_regression_to_series,
)


def _series(cell_index: int, ordinal: int, x: str, y: str, xv=(0.0, 1.0, 2.0), yv=(1.0, 3.0, 5.0), role=GraphSeriesRole.MEASURED):
    return GraphSeriesData(
        f"cell-{cell_index}-series-{ordinal}", f"cell-{cell_index}", cell_index,
        role, x, y, tuple(xv), tuple(yv), len(xv), (min(xv), max(xv)),
        (min(yv), max(yv)), GraphSeriesStatus.EXTRACTED,
        GraphSeriesSource.STATIC_CODE,
    )


def _notebook(*sources: str):
    return nbformat.v4.new_notebook(
        cells=[nbformat.v4.new_code_cell(source) for source in sources]
    )


def _observation(source: str, cell_index: int = 0):
    return extract_regression_observations(source, cell_index, f"cell-{cell_index}")[0]


def test_exact_match_uses_expressions_and_temporal_bindings():
    notebook = _notebook(
        "t = [0., 1., 2.]\nz = [1., 3., 5.]\np = np.polyfit(t, z, 2)",
        "plt.plot(t, z, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "t", "z"),)
    )
    assert result.status is RegressionSeriesMatchStatus.EXACT


def test_aliases_match_by_numeric_values():
    notebook = _notebook(
        "t = [0., 1., 2.]\nz = [1., 3., 5.]\ntt = t\nzz = z\np = np.polyfit(tt, zz, 2)",
        "plt.plot(t, z, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "t", "z"),)
    )
    assert result.status is RegressionSeriesMatchStatus.NUMERIC_EQUIVALENT


def test_reversed_axes_are_explicit():
    notebook = _notebook(
        "t = [0., 1., 2.]\nz = [1., 3., 5.]\np = np.polyfit(z, t, 2)",
        "plt.plot(t, z, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "t", "z"),)
    )
    assert result.status is RegressionSeriesMatchStatus.REVERSED


def test_identical_measured_series_are_ambiguous():
    notebook = _notebook(
        "t = [0., 1., 2.]\nz = [1., 3., 5.]\np = np.polyfit(t, z, 2)",
        "plt.plot(t, z, 'o', label='Mesures')\nplt.plot(t, z, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook,
        _observation(notebook.cells[0].source),
        (_series(1, 1, "t", "z"), _series(1, 2, "t", "z")),
    )
    assert result.status is RegressionSeriesMatchStatus.AMBIGUOUS
    assert result.matched_series_id is None


def test_unique_nearest_repeated_series_is_selected() -> None:
    notebook = _notebook(
        "x = [0., 1., 2.]\ny = [1., 3., 5.]\np = np.polyfit(x, y, 1)",
        "plt.plot(x, y, 'o', label='Mesures')",
        "unrelated = 1",
        "plt.plot(x, y, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook,
        _observation(notebook.cells[0].source),
        (
            _series(1, 1, "x", "y"),
            _series(3, 1, "x", "y"),
        ),
    )
    assert result.status is RegressionSeriesMatchStatus.EXACT
    assert result.matched_series_id == "cell-1-series-1"
    assert not result.requires_human_review


def test_equally_near_repeated_series_remain_ambiguous() -> None:
    notebook = _notebook(
        "x = [0., 1., 2.]\ny = [1., 3., 5.]\nplt.plot(x, y, 'o', label='Mesures')",
        "p = np.polyfit(x, y, 1)",
        "plt.plot(x, y, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook,
        _observation(notebook.cells[1].source, 1),
        (
            _series(0, 1, "x", "y"),
            _series(2, 1, "x", "y"),
        ),
    )
    assert result.status is RegressionSeriesMatchStatus.AMBIGUOUS
    assert result.matched_series_id is None


def test_reassignment_between_regression_and_plot_is_not_exact():
    notebook = _notebook(
        "x = [0., 1., 2.]\ny = [1., 3., 5.]\np = np.polyfit(x, y, 1)",
        "x = [10., 20., 30.]\nplt.plot(x, y, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook,
        _observation(notebook.cells[0].source),
        (_series(1, 1, "x", "y", (10., 20., 30.)),),
    )
    assert result.status is RegressionSeriesMatchStatus.UNMATCHED
    assert result.requires_human_review


def test_fit_and_theory_are_not_candidates():
    notebook = _notebook("p = np.polyfit(t, z, 2)")
    result = match_regression_to_series(
        notebook,
        _observation(notebook.cells[0].source),
        (_series(0, 1, "t", "z", role=GraphSeriesRole.FIT),),
    )
    assert result.status is RegressionSeriesMatchStatus.NOT_EVALUABLE


def test_exact_expression_can_match_without_numeric_resolution():
    notebook = _notebook("p = np.polyfit(np.sin(i2), np.sin(i1), 1)", "plt.plot(np.sin(i2), np.sin(i1), 'o', label='Mesures')")
    result = match_regression_to_series(
        notebook,
        _observation(notebook.cells[0].source),
        (_series(1, 1, "np.sin(i2)", "np.sin(i1)", xv=(0., 1., 2.), yv=(0., 1., 2.)),),
    )
    assert result.status is RegressionSeriesMatchStatus.EXACT


def test_same_x_and_y_is_ambiguous_between_direct_and_reversed():
    notebook = _notebook(
        "x = [0., 1., 2.]\np = np.polyfit(x, x, 1)",
        "plt.plot(x, x, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "x", "x", (0., 1., 2.), (0., 1., 2.)),)
    )
    assert result.status is RegressionSeriesMatchStatus.AMBIGUOUS
    assert result.matched_series_id is None


def test_augmented_assignment_taints_matching():
    notebook = _notebook(
        "x = [0., 1., 2.]\ny = [1., 2., 3.]\np = np.polyfit(x, y, 1)\nx += 1",
        "plt.plot(x, y, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "x", "y"),)
    )
    assert result.status is RegressionSeriesMatchStatus.NOT_EVALUABLE
    assert result.diagnostics[0].startswith("variable_modifiee_par_operation_non_resoluble:x")


@pytest.mark.parametrize("operator", ("+=", "-=", "*=", "/="))
def test_all_augmented_assignments_taint_matching(operator):
    notebook = _notebook(
        f"x = [0., 1., 2.]\ny = [1., 2., 3.]\np = np.polyfit(x, y, 1)\nx {operator} 1",
        "plt.plot(x, y, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "x", "y"),)
    )
    assert result.status is RegressionSeriesMatchStatus.NOT_EVALUABLE


def test_index_mutation_taints_matching():
    notebook = _notebook(
        "x = [0., 1., 2.]\ny = [1., 2., 3.]\np = np.polyfit(x, y, 1)\nx[0] = 100",
        "plt.plot(x, y, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "x", "y"),)
    )
    assert result.status is RegressionSeriesMatchStatus.NOT_EVALUABLE


def test_mutation_before_fit_is_not_an_exact_match():
    notebook = _notebook(
        "x = [0., 1., 2.]\ny = [1., 2., 3.]\nx += 1\np = np.polyfit(x, y, 1)",
        "plt.plot(x, y, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "x", "y"),)
    )
    assert result.status is RegressionSeriesMatchStatus.NOT_EVALUABLE


def test_mutation_after_plot_does_not_retroactively_invalidate_match():
    notebook = _notebook(
        "x = [0., 1., 2.]\ny = [1., 2., 3.]\np = np.polyfit(x, y, 1)\nplt.plot(x, y, 'o', label='Mesures')\nx += 1",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(0, 1, "x", "y"),)
    )
    assert result.status is RegressionSeriesMatchStatus.EXACT


def test_multiple_dependencies_report_the_tainted_name():
    notebook = _notebook(
        "a = 2.\nx = [0., 1., 2.]\nb = 1.\ny = [1., 2., 3.]\np = np.polyfit(a*x+b, y, 1)\nx += 1",
        "plt.plot(a*x+b, y, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "a*x+b", "y"),)
    )
    assert result.status is RegressionSeriesMatchStatus.NOT_EVALUABLE
    assert "x" in result.diagnostics[0]


def test_two_non_numeric_identical_measured_series_are_ambiguous():
    notebook = _notebook(
        "p = np.polyfit(np.sin(i2), np.sin(i1), 1)",
        "plt.plot(np.sin(i2), np.sin(i1), 'o', label='Mesures')\nplt.plot(np.sin(i2), np.sin(i1), 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook,
        _observation(notebook.cells[0].source),
        (_series(1, 1, "np.sin(i2)", "np.sin(i1)"), _series(1, 2, "np.sin(i2)", "np.sin(i1)")),
    )
    assert result.status is RegressionSeriesMatchStatus.AMBIGUOUS
    assert result.matched_series_id is None


def test_valid_regression_without_measured_series_is_unmatched():
    notebook = _notebook("x = [0., 1., 2.]\ny = [1., 2., 3.]\np = np.polyfit(x, y, 1)")
    result = match_regression_to_series(notebook, _observation(notebook.cells[0].source), ())
    assert result.status is RegressionSeriesMatchStatus.UNMATCHED


def test_snell_expression_with_tainted_dependency_is_not_exact():
    notebook = _notebook(
        "p = np.polyfit(np.sin(i2), np.sin(i1), 1)\ni2 += 1",
        "plt.plot(np.sin(i2), np.sin(i1), 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook,
        _observation(notebook.cells[0].source),
        (_series(1, 1, "np.sin(i2)", "np.sin(i1)"),),
    )
    assert result.status is RegressionSeriesMatchStatus.NOT_EVALUABLE


def test_unrelated_mutation_does_not_taint_used_bindings():
    notebook = _notebook(
        "x = [0., 1., 2.]\ny = [1., 2., 3.]\np = np.polyfit(x, y, 1)\nunrelated += 1",
        "plt.plot(x, y, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "x", "y"),)
    )
    assert result.status is RegressionSeriesMatchStatus.EXACT


def test_invalidation_can_be_cleared_by_a_new_simple_assignment():
    notebook = _notebook(
        "x = [0., 1., 2.]\ny = [1., 2., 3.]\np = np.polyfit(x, y, 1)\nx += 1\nx = [10., 20., 30.]",
        "plt.plot(x, y, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "x", "y", (10., 20., 30.)),)
    )
    assert result.status is RegressionSeriesMatchStatus.UNMATCHED


def test_unsupported_unpacking_taints_following_names():
    notebook = _notebook(
        "x = [0., 1., 2.]\ny = [1., 2., 3.]\np = np.polyfit(x, y, 1)\nx, y = y, x",
        "plt.plot(x, y, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook, _observation(notebook.cells[0].source), (_series(1, 1, "x", "y"),)
    )
    assert result.status is RegressionSeriesMatchStatus.NOT_EVALUABLE


def test_direct_and_reversed_competing_series_are_ambiguous():
    notebook = _notebook(
        "x = [0., 1., 2.]\ny = [1., 2., 4.]\np = np.polyfit(x, y, 1)",
        "plt.plot(x, y, 'o', label='Mesures')\nplt.plot(y, x, 'o', label='Mesures')",
    )
    result = match_regression_to_series(
        notebook,
        _observation(notebook.cells[0].source),
        (_series(1, 1, "x", "y", (0., 1., 2.), (1., 2., 4.)),
         _series(1, 2, "y", "x", (1., 2., 4.), (0., 1., 2.))),
    )
    assert result.status is RegressionSeriesMatchStatus.AMBIGUOUS
    assert result.matched_series_id is None
