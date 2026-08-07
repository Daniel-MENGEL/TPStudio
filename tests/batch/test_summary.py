from pathlib import Path
from tpstudio.batch import BatchCopyResult, BatchCopyStatus, BatchRunResult, render_batch_report_markdown, summarize_batch_run

def test_summaries_are_deterministic_and_anonymized():
    result = BatchRunResult("project", (BatchCopyResult("copy-001", BatchCopyStatus.SUCCESS, Path("/tmp/a.ipynb"), Path("/tmp/a.html"), 2), BatchCopyResult("copy-002", BatchCopyStatus.FAILED, error_type="ValueError", error_message="invalid notebook")), Path("/tmp/out"), 2, 1, 1, 0, 2, 0)
    summary = summarize_batch_run(result); markdown = render_batch_report_markdown(result)
    assert summary == summarize_batch_run(result) and "copy-001" in markdown
    assert "/tmp" not in markdown and "score" not in markdown.lower() and "grade" not in markdown.lower()

def test_private_error_text_never_reaches_public_summaries():
    result = BatchRunResult("project", (BatchCopyResult("copy-002", BatchCopyStatus.FAILED, error_type="ValueError", error_message="Échec d'export."),), Path("/private/var/out"), 1, 0, 1, 0, 0, 0)
    assert "/Users/" not in summarize_batch_run(result)
    assert "/home/" not in render_batch_report_markdown(result)


def test_human_review_labels_distinguish_true_false_and_unknown():
    items = (
        BatchCopyResult("yes", BatchCopyStatus.SUCCESS, Path("yes.ipynb"), Path("yes.html"), requires_human_review=True),
        BatchCopyResult("no", BatchCopyStatus.SUCCESS, Path("no.ipynb"), Path("no.html"), requires_human_review=False),
        BatchCopyResult("unknown", BatchCopyStatus.SUCCESS, Path("unknown.ipynb"), Path("unknown.html"), requires_human_review=None),
    )
    result = BatchRunResult("project", items, Path("out"), 3, 3, 0, 0, 0, 1)
    markdown = render_batch_report_markdown(result)
    assert "oui" in markdown and "non" in markdown and "indéterminée" in markdown
    assert "Revue humaine confirmée : 1" in markdown
