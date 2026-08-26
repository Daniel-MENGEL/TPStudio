from dataclasses import replace
from pathlib import Path
import importlib.util

from tpstudio.projects import ExpectedGraphModel
from tpstudio.reporting import TeacherGraphReport, build_teacher_copy_report, render_teacher_report_markdown


def _result(tmp_path):
    path = Path("tests/orchestration/test_copy_analysis.py")
    spec = importlib.util.spec_from_file_location("generic_report_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._analyze(tmp_path)


def test_snell_graph_expectation_is_transported_and_rendered(tmp_path) -> None:
    report = build_teacher_copy_report(_result(tmp_path))
    graph = report.graph[0]
    assert graph.expected_x_expression == "sin(i2)"
    assert graph.expected_y_expression == "sin(i1)"
    assert graph.expected_model is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN
    text = render_teacher_report_markdown(report)
    assert "Attendu Snell-Descartes" not in text
    assert "x = `sin(i2)`" in text and "y = `sin(i1)`" in text
    assert "droite passant par l'origine" in text


def test_lens_like_affine_expectation_has_no_snell_renderer_text(tmp_path) -> None:
    source = build_teacher_copy_report(_result(tmp_path))
    lens_graph = replace(
        source.graph[0],
        expected_description="Graphe de 1/OA' en fonction de 1/OA.",
        expected_x_expression="1/OA",
        expected_y_expression="1/OA'",
        expected_model=ExpectedGraphModel.AFFINE,
    )
    report = replace(
        source,
        project_id="thin-lens-image",
        title="Formation d'une image par une lentille mince",
        graph=(lens_graph,),
    )
    text = render_teacher_report_markdown(report)
    assert "1/OA" in text and "1/OA'" in text and "modèle affine" in text
    assert "Attendu Snell-Descartes" not in text
    assert "pente `a = n`" not in text


def test_quadratic_expectation_is_rendered_without_project_logic(tmp_path) -> None:
    source = build_teacher_copy_report(_result(tmp_path))
    graph = replace(
        source.graph[0],
        expected_description="Modélisation par un polynôme de degré 2.",
        expected_x_expression="t",
        expected_y_expression="z",
        expected_model=ExpectedGraphModel.QUADRATIC,
    )
    text = render_teacher_report_markdown(replace(source, graph=(graph,)))
    assert "x = `t`" in text and "y = `z`" in text
    assert "modèle quadratique" in text


def test_graph_without_expectation_is_rendered_minimally(tmp_path) -> None:
    source = build_teacher_copy_report(_result(tmp_path))
    graph = replace(
        source.graph[0],
        expected_description=None,
        expected_x_expression=None,
        expected_y_expression=None,
        expected_model=None,
    )
    text = render_teacher_report_markdown(replace(source, graph=(graph,)))
    assert "### `regression_graph`" in text
    assert "Attendu Snell-Descartes" not in text


def test_each_graph_carries_its_own_expectation(tmp_path) -> None:
    source = build_teacher_copy_report(_result(tmp_path))
    first = source.graph[0]
    second = replace(
        first,
        production_id="second_graph",
        expected_x_expression="t",
        expected_y_expression="z",
        expected_model=ExpectedGraphModel.QUADRATIC,
    )
    text = render_teacher_report_markdown(replace(source, graph=(first, second)))
    assert "x = `sin(i2)`" in text
    assert "x = `t`" in text and "modèle quadratique" in text


def test_generic_graph_transport_does_not_drop_other_report_sections(tmp_path) -> None:
    report = build_teacher_copy_report(_result(tmp_path))
    assert len(report.productions) == 25
    assert len(report.quantities) == 7
    assert len(report.relations) == 5
    assert len(report.comparisons) == 2


def test_teacher_graph_report_keeps_historical_positional_constructor() -> None:
    report = TeacherGraphReport(
        "historical-graph", 12, True, "x_obs", "y_obs", "X", "Y", True,
        "x_reg", "y_reg", "slope", "orientation", "labels", "regression",
        "slope-relation", True, ("limitation",),
    )
    assert report.production_id == "historical-graph"
    assert report.cell_index == 12
    assert report.regression_x_expression == "x_reg"
    assert report.evaluable is True
    assert report.limitations == ("limitation",)
    assert report.expected_description is None
    assert report.expected_x_expression is None
    assert report.expected_y_expression is None
    assert report.expected_model is None
