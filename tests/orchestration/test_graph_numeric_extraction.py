from __future__ import annotations

import nbformat

from tpstudio.notebooks import resolve_notebook_bindings
from tpstudio.orchestration import (
    GraphSeriesRole,
    GraphSeriesStatus,
    observe_saved_graph,
)
from tpstudio.projects import snells_laws_teacher_project


def _observe(cells):
    project = snells_laws_teacher_project()
    notebook = nbformat.v4.new_notebook(cells=cells)
    resolution = resolve_notebook_bindings(
        notebook, project.notebook_binding_plan
    ).get("regression-graph-cell")
    return observe_saved_graph(notebook, resolution)


def test_extracts_small_numeric_series_without_execution() -> None:
    observation = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "x = np.array([1., 2., 3., 4.])\n"
            "y = np.array([2., 4., 6., 8.])\n"
            "plt.plot(x, y, 'o')\n"
        )
    ])
    assert observation is not None
    series = observation.series_data[0]
    assert series.technical_status is GraphSeriesStatus.EXTRACTED
    assert series.x_values == (1.0, 2.0, 3.0, 4.0)
    assert series.y_values == (2.0, 4.0, 6.0, 8.0)
    assert series.n_points == 4
    assert series.role is GraphSeriesRole.UNKNOWN


def test_extracts_numpy_transformation_and_snell_like_series() -> None:
    observation = _observe([
        nbformat.v4.new_code_cell(
            "# Préparation\n"
            "i1 = np.array([0., 0.5, 1.0])\n"
            "i2 = np.array([0., 0.3, 0.7])\n"
            "sini1 = np.sin(i1)\n"
            "sini2 = np.sin(i2)\n"
        ),
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "plt.plot(sini2, sini1, 'o', label='Mesures')\n"
        ),
    ])
    assert observation is not None
    series = observation.series_data[0]
    assert series.role is GraphSeriesRole.MEASURED
    assert series.x_values == (0.0, 0.29552020666133955, 0.644217687237691)
    assert series.y_values == (0.0, 0.479425538604203, 0.8414709848078965)


def test_reassignment_after_graph_does_not_change_series() -> None:
    observation = _observe([
        nbformat.v4.new_code_cell("x = [1, 2, 3]\ny = [2, 4, 6]\n"),
        nbformat.v4.new_code_cell(
            "# Vérification graphique\nplt.plot(x, y)\n"
        ),
        nbformat.v4.new_code_cell("x = [10, 20, 30]\ny = [1, 1, 1]\n"),
    ])
    assert observation is not None
    assert observation.series_data[0].x_values == (1.0, 2.0, 3.0)
    assert observation.series_data[0].y_values == (2.0, 4.0, 6.0)


def test_reassignment_between_two_plots_is_sequential() -> None:
    observation = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "x = [1, 2, 3]\n"
            "y = [2, 4, 6]\n"
            "plt.plot(x, y)\n"
            "x = [10, 20, 30]\n"
            "y = [1, 1, 1]\n"
            "plt.plot(x, y)\n"
        )
    ])
    assert observation is not None
    assert observation.series_data[0].x_values == (1.0, 2.0, 3.0)
    assert observation.series_data[0].y_values == (2.0, 4.0, 6.0)
    assert observation.series_data[1].x_values == (10.0, 20.0, 30.0)
    assert observation.series_data[1].y_values == (1.0, 1.0, 1.0)


def test_invalid_lengths_and_non_finite_values_are_technical_failures() -> None:
    invalid = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "plt.plot([1, 2], [1])\n"
        )
    ])
    assert invalid is not None
    assert invalid.series_data[0].technical_status is GraphSeriesStatus.INVALID
    assert "longueurs_x_y_incompatibles" in invalid.series_data[0].diagnostics

    non_finite = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "x = [1, np.nan, 3]\n"
            "y = [1, 2, 3]\n"
            "plt.plot(x, y)\n"
        )
    ])
    assert non_finite is not None
    assert non_finite.series_data[0].technical_status is GraphSeriesStatus.NOT_EVALUABLE

    empty = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "x = np.array([])\n"
            "y = np.array([])\n"
            "plt.plot(x, y)\n"
        )
    ])
    assert empty is not None
    assert empty.series_data[0].technical_status is GraphSeriesStatus.NOT_EVALUABLE


def test_radians_are_not_assumed_for_raw_angles() -> None:
    raw = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "angle = [30.]\nplt.plot(angle, np.sin(angle))\n"
        )
    ])
    converted = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "angle = [30.]\nplt.plot(angle, np.sin(np.radians(angle)))\n"
        )
    ])
    assert raw is not None and converted is not None
    assert raw.series_data[0].y_values != converted.series_data[0].y_values
    assert converted.series_data[0].y_values == (0.49999999999999994,)


def test_errorbar_uses_first_two_arguments_only() -> None:
    observation = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "x = [1, 2, 3]\n"
            "y = [2, 4, 6]\n"
            "ux = [0.1, 0.1, 0.1]\n"
            "uy = [0.2, 0.2, 0.2]\n"
            "plt.errorbar(x, y, xerr=ux, yerr=uy)\n"
        )
    ])
    assert observation is not None
    assert observation.series_data[0].x_values == (1.0, 2.0, 3.0)
    assert observation.series_data[0].y_values == (2.0, 4.0, 6.0)


def test_unknown_calls_are_not_executed_or_resolved() -> None:
    observation = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "x = open('student.txt')\n"
            "y = os.system('touch forbidden')\n"
            "plt.plot(x, y)\n"
        )
    ])
    assert observation is not None
    assert observation.series_data[0].technical_status is GraphSeriesStatus.NOT_EVALUABLE
    assert observation.series_data[0].x_values is None
    assert observation.series_data[0].y_values is None


def test_multiple_series_remain_separate_and_fit_is_not_measured() -> None:
    observation = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "x = [1, 2, 3]\n"
            "y = [2, 4, 6]\n"
            "a = 2\n"
            "plt.plot(x, y, 'o', label='Mesures')\n"
            "plt.plot(x, a*x, label='Régression linéaire')\n"
        )
    ])
    assert observation is not None
    assert len(observation.series_data) == 2
    assert observation.series_data[0].role is GraphSeriesRole.MEASURED
    assert observation.series_data[1].role is GraphSeriesRole.FIT
    assert observation.series_data[0].series_id != observation.series_data[1].series_id


def test_generic_droite_label_remains_unknown() -> None:
    observation = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\nplt.plot([1, 2], [2, 4], label='Droite')\n"
        )
    ])
    assert observation is not None
    assert observation.series_data[0].role is GraphSeriesRole.UNKNOWN


def test_unsupported_assignments_do_not_create_false_bindings() -> None:
    observation = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "x = [1, 2]\n"
            "x += [3]\n"
            "x[0] = 99\n"
            "a, b = [1, 2]\n"
            "plt.plot(x, [1, 2])\n"
        )
    ])
    assert observation is not None
    assert observation.series_data[0].x_values == (1.0, 2.0)


def test_pathological_expressions_are_rejected_without_crashing() -> None:
    observation = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            "x = [10 ** 100000000]\n"
            "y = [1]\n"
            "plt.plot(x, y)\n"
        )
    ])
    assert observation is not None
    assert observation.series_data[0].technical_status is GraphSeriesStatus.NOT_EVALUABLE

    values = ", ".join(str(index) for index in range(10_001))
    oversized = _observe([
        nbformat.v4.new_code_cell(
            "# Vérification graphique\n"
            f"x = [{values}]\n"
            "y = [1]\n"
            "plt.plot(x, y)\n"
        )
    ])
    assert oversized is not None
    assert oversized.series_data[0].technical_status is GraphSeriesStatus.NOT_EVALUABLE
