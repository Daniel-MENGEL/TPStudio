import nbformat
import numpy as np
import pytest
from dataclasses import replace

from tpstudio.notebooks import resolve_notebook_bindings
from tpstudio.orchestration import (
    GraphCheckStatus,
    extract_all_graph_series_data,
    evaluate_saved_graph,
    observe_saved_graph,
)
from tpstudio.projects import snells_laws_teacher_project


def _evaluate(code: str, *, image: bool = False):
    project = snells_laws_teacher_project()
    cell = nbformat.v4.new_code_cell("# Vérification graphique\n" + code)
    if image:
        cell.outputs = [nbformat.v4.new_output("display_data", data={"image/png": "AA=="})]
    notebook = nbformat.v4.new_notebook(cells=[cell])
    resolution = resolve_notebook_bindings(notebook, project.notebook_binding_plan).get("regression-graph-cell")
    observation = observe_saved_graph(notebook, resolution)
    expectation = replace(
        project.graph_expectation_set.get("regression_graph"),
        x_expression="np.sin(i2)", y_expression="np.sin(i1)",
    )
    return evaluate_saved_graph(expectation, observation)


def _code(x="np.sin(i2)", y="np.sin(i1)", *, labels=True, regression=True, slope="a"):
    lines = [f"plt.plot({x}, {y})"]
    if labels:
        lines.extend(("plt.xlabel('sin(i2)')", "plt.ylabel('sin(i1)')"))
    if regression:
        lines.append(f"{slope} = np.polyfit({x}, {y}, 1)")
    return "\n".join(lines)


def test_conforming_graph_and_saved_figure() -> None:
    result = _evaluate(_code(), image=True)
    assert result.orientation_status is GraphCheckStatus.MATCHES
    assert result.label_status is GraphCheckStatus.MATCHES
    assert result.regression_status is GraphCheckStatus.MATCHES
    assert result.slope_relation_status is GraphCheckStatus.MATCHES
    assert result.observation.figure_output_present


def test_inverted_axes_and_regression_are_detected() -> None:
    result = _evaluate(_code("np.sin(i1)", "np.sin(i2)"))
    assert result.orientation_status is GraphCheckStatus.INVERTED
    assert result.regression_status is GraphCheckStatus.INVERTED
    assert result.has_issues


def test_inverted_labels_are_detected_independently() -> None:
    code = "\n".join((
        "plt.plot(np.sin(i2), np.sin(i1))",
        "plt.xlabel('sin(i1)')", "plt.ylabel('sin(i2)')",
        "a = np.polyfit(np.sin(i2), np.sin(i1), 1)",
    ))
    assert _evaluate(code).label_status is GraphCheckStatus.INVERTED


def test_missing_regression_and_figure_are_structured() -> None:
    result = _evaluate(_code(regression=False))
    assert result.regression_status is GraphCheckStatus.MISSING
    assert not result.observation.figure_output_present


@pytest.mark.parametrize("slope", ("n", "inverse_n"))
def test_literal_slope_target_is_retained_without_scientific_inference(slope: str) -> None:
    result = _evaluate(_code(slope=slope))
    assert result.observation.slope_target == slope


def test_unrecognized_syntax_is_prudently_not_evaluable() -> None:
    result = _evaluate("plt.plot(x)\nthis is not valid python")
    assert not result.evaluable
    assert result.orientation_status is GraphCheckStatus.NOT_EVALUABLE
    assert "syntaxe_non_reconnue" in result.reasons


def test_single_expression_degree_helper_is_safely_interpreted() -> None:
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_code_cell(
            "def deg(x):\n"
            "    return np.asarray(x, dtype=float) * np.pi / 180\n"
        ),
        nbformat.v4.new_code_cell(
            "i1 = np.array([0, 30, 60], dtype=float)\n"
            "i2 = np.array([0, 15, 30], dtype=float)\n"
            "sini1 = np.sin(deg(i1))\n"
            "sini2 = np.sin(deg(i2))\n"
            "plt.plot(sini2, sini1, label='Mesures')\n"
        ),
    ])

    series = extract_all_graph_series_data(notebook)[0]
    assert series.technical_status.value == "extracted"
    assert series.n_points == 3
    assert series.x_values == pytest.approx((0.0, 0.2588190451, 0.5))
    assert series.y_values == pytest.approx((0.0, 0.5, 0.8660254038))


def test_multi_statement_helper_remains_not_evaluable() -> None:
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_code_cell(
            "def transform(x):\n"
            "    y = x * 2\n"
            "    return y\n"
        ),
        nbformat.v4.new_code_cell(
            "x = np.array([0, 1, 2], dtype=float)\n"
            "plt.plot(x, transform(x), label='Mesures')\n"
        ),
    ])

    series = extract_all_graph_series_data(notebook)[0]
    assert series.technical_status.value == "not_evaluable"
    assert series.y_values is None


def test_array_min_max_methods_feed_safe_linspace() -> None:
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(
        "x = np.array([0, 1, 2], dtype=float)\n"
        "xx = np.linspace(x.min(), x.max(), 5)\n"
        "plt.plot(xx, 2 * xx + 1, label='Ajustement')\n"
    )])

    series = extract_all_graph_series_data(notebook)[0]
    assert series.technical_status.value == "extracted"
    assert series.x_values == pytest.approx((0.0, 0.5, 1.0, 1.5, 2.0))
    assert series.y_values == pytest.approx((1.0, 2.0, 3.0, 4.0, 5.0))


def test_no_pixel_or_ocr_dependency_is_present() -> None:
    source = __import__("inspect").getsource(observe_saved_graph)
    assert "ocr" not in source.lower()
    assert "image/png" not in source


def test_preloaded_series_resolve_csv_derived_names_without_executing_notebook_code() -> None:
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_code_cell("data = np.loadtxt('scope.csv')\nt = data[:, 0]\nuC = data[:, 2]"),
        nbformat.v4.new_code_cell("plt.plot(t, uC)"),
    ])
    series = extract_all_graph_series_data(
        notebook,
        {"t": np.array([0.0, 1.0, 2.0]), "uC": (0.0, 3.0, 5.0)},
    )
    assert len(series) == 1
    assert series[0].x_expression == "t"
    assert series[0].y_expression == "uC"
    assert series[0].x_values == (0.0, 1.0, 2.0)
    assert series[0].y_values == (0.0, 3.0, 5.0)
    assert series[0].technical_status.value == "extracted"


def test_preloaded_series_length_mismatch_is_structured() -> None:
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("plt.plot(t, uC)")])
    series = extract_all_graph_series_data(
        notebook, {"t": (0.0, 1.0), "uC": (0.0,)}
    )
    assert len(series) == 1
    assert series[0].technical_status.value == "invalid"
    assert "longueurs_x_y_incompatibles" in series[0].diagnostics


def test_preloaded_series_rejects_non_numeric_values() -> None:
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("plt.plot(t, uC)")])
    with pytest.raises((TypeError, ValueError)):
        extract_all_graph_series_data(notebook, {"t": (0.0, "bad"), "uC": (0.0, 1.0)})


def test_multiplot_selects_expected_curve_by_expressions_not_plot_order() -> None:
    project = snells_laws_teacher_project()
    expectation = replace(
        project.graph_expectation_set.get("regression_graph"),
        x_expression="np.sin(i2)", y_expression="np.sin(i1)",
    )
    code = "# Vérification graphique\nplt.plot(np.sin(i1), np.sin(i2))\nplt.plot(np.sin(i2), np.sin(i1))\na = np.polyfit(np.sin(i2), np.sin(i1), 1)"
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(code)])
    resolution = resolve_notebook_bindings(notebook, project.notebook_binding_plan).get("regression-graph-cell")
    observation = observe_saved_graph(
        notebook, resolution,
        {"i1": (0.0, 1.0, 2.0), "i2": (0.0, 3.0, 5.0)},
    )
    result = evaluate_saved_graph(expectation, observation)
    assert result.orientation_status is GraphCheckStatus.MATCHES
    assert result.observation.series_data[0].y_expression == "np.sin(i1)"


def test_multiplot_duplicate_expected_curve_is_ambiguous() -> None:
    project = snells_laws_teacher_project()
    expectation = replace(
        project.graph_expectation_set.get("regression_graph"),
        x_expression="np.sin(i2)", y_expression="np.sin(i1)",
    )
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(
        "# Vérification graphique\nplt.plot(np.sin(i2), np.sin(i1))\nplt.plot(np.sin(i2), np.sin(i1))\n"
        "a = np.polyfit(np.sin(i2), np.sin(i1), 1)"
    )])
    resolution = resolve_notebook_bindings(notebook, project.notebook_binding_plan).get("regression-graph-cell")
    observation = observe_saved_graph(notebook, resolution, {"i1": (0.0, 1.0), "i2": (0.0, 1.0)})
    result = evaluate_saved_graph(expectation, observation)
    assert result.orientation_status is GraphCheckStatus.NOT_EVALUABLE
    assert "courbe_attendue_ambiguë" in result.reasons


@pytest.mark.parametrize("actual_y", ("uc", "UC", "np.uC"))
def test_graph_identity_is_case_sensitive_and_does_not_strip_np(actual_y: str) -> None:
    project = snells_laws_teacher_project()
    expectation = replace(
        project.graph_expectation_set.get("regression_graph"),
        x_expression="t", y_expression="uC",
        accepted_x_labels=("t",), accepted_y_labels=("uC",),
    )
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(
        f"# Vérification graphique\nplt.plot(t, {actual_y})\n"
        "a = np.polyfit(t, " + actual_y + ", 1)"
    )])
    resolution = resolve_notebook_bindings(notebook, project.notebook_binding_plan).get("regression-graph-cell")
    observation = observe_saved_graph(notebook, resolution, {"t": (0.0, 1.0), actual_y: (0.0, 1.0)})
    result = evaluate_saved_graph(expectation, observation)
    assert result.orientation_status is GraphCheckStatus.NOT_EVALUABLE


def test_multiplot_case_collision_selects_only_exact_expression() -> None:
    project = snells_laws_teacher_project()
    expectation = replace(
        project.graph_expectation_set.get("regression_graph"),
        x_expression="t", y_expression="uC",
        accepted_x_labels=("t",), accepted_y_labels=("uC",),
    )
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(
        "# Vérification graphique\nplt.plot(t, uc)\nplt.plot(t, uC)"
    )])
    resolution = resolve_notebook_bindings(notebook, project.notebook_binding_plan).get("regression-graph-cell")
    observation = observe_saved_graph(
        notebook, resolution, {"t": (0.0, 1.0), "uc": (0.0, 1.0), "uC": (0.0, 2.0)}
    )
    result = evaluate_saved_graph(expectation, observation)
    assert result.orientation_status is GraphCheckStatus.MATCHES
    assert result.observation.series_data[0].y_expression == "uC"


def test_single_wrong_curve_does_not_fallback_to_first_series() -> None:
    project = snells_laws_teacher_project()
    expectation = replace(
        project.graph_expectation_set.get("regression_graph"),
        x_expression="t", y_expression="uC",
        accepted_x_labels=("t",), accepted_y_labels=("uC",),
    )
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(
        "# Vérification graphique\nplt.plot(t, uG)"
    )])
    resolution = resolve_notebook_bindings(notebook, project.notebook_binding_plan).get("regression-graph-cell")
    observation = observe_saved_graph(notebook, resolution, {"t": (0.0, 1.0), "uG": (0.0, 1.0)})
    result = evaluate_saved_graph(expectation, observation)
    assert "courbe_attendue_absente" in result.reasons
