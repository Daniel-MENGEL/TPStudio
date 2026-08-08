from pathlib import Path
import pytest
from tpstudio.batch import BatchCopyResult, BatchCopySource, BatchCopyStatus, BatchOptions, BatchRunResult, BatchPlan, PlannedBatchOutput

def test_models_and_invariants():
    source = BatchCopySource("copy-001", Path("copy.ipynb"))
    assert source.source_id == "copy-001" and BatchOptions().continue_on_error
    success = BatchCopyResult("copy-001", BatchCopyStatus.SUCCESS, Path("a.ipynb"), Path("a.html"))
    run = BatchRunResult("project", (success,), Path("out"), 1, 1, 0, 0, 0, 0)
    assert run.success and run.get("copy-001") is success
    with pytest.raises(ValueError): BatchCopyResult("copy", BatchCopyStatus.FAILED)
    with pytest.raises(AttributeError): source.source_id = "x"

def test_failed_and_skipped_require_reason_and_no_artifacts():
    with pytest.raises(ValueError): BatchCopyResult("x", BatchCopyStatus.SKIPPED)
    assert BatchCopyResult("x", BatchCopyStatus.SKIPPED, error_message="collision").html_path is None


def test_skipped_only_batch_is_not_a_complete_success():
    skipped = BatchCopyResult("x", BatchCopyStatus.SKIPPED, error_message="collision")
    run = BatchRunResult("project", (skipped,), Path("out"), 0, 0, 0, 1, 0, 0)
    assert not run.success and not run.has_failures


def test_batch_plan_rejects_structural_mismatches():
    source_a = BatchCopySource("copy-001", Path("a.ipynb"))
    source_b = BatchCopySource("copy-002", Path("b.ipynb"))
    output_a = PlannedBatchOutput("copy-001", Path("a.ipynb"), Path("a.html"))
    output_b = PlannedBatchOutput("copy-002", Path("b.ipynb"), Path("b.html"))
    with pytest.raises(ValueError):
        BatchPlan((source_a, source_b), Path("out"), BatchOptions(), (output_a,))
    with pytest.raises(ValueError):
        BatchPlan((source_a,), Path("out"), BatchOptions(), (output_b,))
    with pytest.raises(ValueError):
        BatchPlan((source_a, source_a), Path("out"), BatchOptions(), (output_a, output_b))
    with pytest.raises(ValueError):
        BatchPlan((source_a, source_b), Path("out"), BatchOptions(), (output_a, output_a))


def test_batch_run_rejects_pending_final_result_and_empty_is_not_success():
    pending = BatchCopyResult("copy-001", BatchCopyStatus.PENDING)
    with pytest.raises(ValueError):
        BatchRunResult("project", (pending,), Path("out"), 0, 0, 0, 0, 0, 0)
    empty = BatchRunResult("project", (), Path("out"), 0, 0, 0, 0, 0, 0)
    assert not empty.success


@pytest.mark.parametrize("stem", ["", "   ", "../copy", "folder/copy", r"folder\copy", "copy.ipynb", "copy.html"])
def test_output_stem_rejects_paths_and_file_suffixes(stem):
    with pytest.raises(ValueError):
        BatchCopySource("copy-001", Path("tp.ipynb"), output_stem=stem)


def test_output_stem_accepts_unicode_logical_stem():
    source = BatchCopySource("copy-001", Path("tp.ipynb"), output_stem="Lois-de-Snell-Descartes-Léa-DUPONT")
    assert source.output_stem == "Lois-de-Snell-Descartes-Léa-DUPONT"
