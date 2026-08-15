from tpstudio.regression import (
    RegressionMethod,
    RegressionTargetKind,
    RegressionTechnicalStatus,
    extract_regression_observations,
)


def test_polyfit_single_target_degree_one() -> None:
    item = extract_regression_observations("p = np.polyfit(x, y, 1)", 4, "cell-4")[0]
    assert item.method is RegressionMethod.NUMPY_POLYFIT
    assert item.degree == 1
    assert item.target_kind is RegressionTargetKind.SINGLE
    assert item.target_names == ("p",)
    assert item.technical_status is RegressionTechnicalStatus.EXTRACTED


def test_polyfit_tuple_targets_match_degree() -> None:
    linear = extract_regression_observations("a, b = np.polyfit(x, y, 1)", 1)[0]
    quadratic = extract_regression_observations("a, b, c = np.polyfit(x, y, 2)", 1)[0]
    assert linear.target_names == ("a", "b")
    assert quadratic.target_names == ("a", "b", "c")
    assert linear.technical_status is RegressionTechnicalStatus.EXTRACTED
    assert quadratic.technical_status is RegressionTechnicalStatus.EXTRACTED


def test_multiple_regressions_keep_source_order() -> None:
    items = extract_regression_observations(
        "p1 = np.polyfit(x1, y1, 1)\np2 = np.polyfit(x2, y2, 2)", 2
    )
    assert [item.regression_id for item in items] == ["cell-2-regression-0", "cell-2-regression-1"]
    assert [item.x_expression for item in items] == ["x1", "x2"]
    assert [item.degree for item in items] == [1, 2]


def test_degree_variable_and_unsupported_degree_are_structural_findings() -> None:
    variable = extract_regression_observations("p = np.polyfit(x, y, degree)", 1)[0]
    cubic = extract_regression_observations("p = np.polyfit(x, y, 3)", 1)[0]
    assert variable.technical_status is RegressionTechnicalStatus.NOT_EVALUABLE
    assert cubic.technical_status is RegressionTechnicalStatus.UNSUPPORTED_MODEL


def test_unassigned_calls_are_observed_with_no_target() -> None:
    items = extract_regression_observations(
        "np.polyfit(x, y, 1)\nlinregress(x, y)", 1
    )
    assert [item.target_kind for item in items] == [RegressionTargetKind.NONE, RegressionTargetKind.NONE]
    assert all(item.target_names == () for item in items)
    assert all(item.technical_status is RegressionTechnicalStatus.EXTRACTED for item in items)


def test_nested_regressions_are_intentionally_ignored() -> None:
    source = "if condition:\n    p = np.polyfit(x, y, 1)\ndef fit():\n    return np.polyfit(x, y, 2)"
    assert extract_regression_observations(source, 1) == ()


def test_boolean_degrees_are_not_integer_degrees() -> None:
    true_degree = extract_regression_observations("np.polyfit(x, y, True)", 1)[0]
    false_degree = extract_regression_observations("np.polyfit(x, y, False)", 1)[0]
    assert true_degree.technical_status is RegressionTechnicalStatus.NOT_EVALUABLE
    assert false_degree.technical_status is RegressionTechnicalStatus.NOT_EVALUABLE


def test_incompatible_tuple_target_count_is_not_executed() -> None:
    item = extract_regression_observations("a, b = np.polyfit(x, y, 2)", 1)[0]
    assert item.technical_status is RegressionTechnicalStatus.INVALID_TARGETS
    assert "cibles" in " ".join(item.diagnostics)


def test_linregress_is_affine_and_keeps_target_names() -> None:
    item = extract_regression_observations(
        "slope, intercept, r, pvalue, stderr = linregress(x, y)", 3
    )[0]
    assert item.method is RegressionMethod.SCIPY_LINREGRESS
    assert item.degree == 1
    assert item.target_names == ("slope", "intercept", "r", "pvalue", "stderr")
    assert item.technical_status is RegressionTechnicalStatus.EXTRACTED


def test_unknown_object_named_polyfit_is_not_recognized() -> None:
    assert extract_regression_observations("student.polyfit(x, y, 1)", 1) == ()
