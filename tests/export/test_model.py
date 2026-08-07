from pathlib import Path

import pytest

from tpstudio.export import CopyExportOptions, CopyExportResult, ExportArtifact, ExportArtifactKind


def _artifact(kind=ExportArtifactKind.NOTEBOOK):
    return ExportArtifact(kind, Path("derived"), True, False, "text/plain", "source")


def test_options_defaults_and_exact_booleans():
    assert CopyExportOptions().execute_notebook is False
    with pytest.raises(TypeError): CopyExportOptions(overwrite=1)
    with pytest.raises(NotImplementedError): CopyExportOptions(execute_notebook=True)


def test_artifact_and_result_are_immutable_and_have_no_score():
    artifact = _artifact()
    result = CopyExportResult("project", "source", artifact, _artifact(ExportArtifactKind.HTML), 2, 1, 1, True, True, True)
    assert result.success and result.output_paths == (Path("derived"), Path("derived"))
    with pytest.raises(AttributeError): result.project_id = "other"
    assert not hasattr(result, "score") and not hasattr(result, "grade")
