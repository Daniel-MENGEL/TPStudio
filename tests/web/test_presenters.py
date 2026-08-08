from pathlib import Path

from tpstudio.batch import BatchCopySource, BatchOptions, build_batch_plan
from tpstudio.web.presenters import batch_plan_rows, has_output_name_collision


def test_presenters_use_planned_basenames_only(tmp_path):
    first = tmp_path / "a" / "tp.ipynb"; second = tmp_path / "b" / "tp.ipynb"
    first.parent.mkdir(); second.parent.mkdir(); first.write_bytes(b"x"); second.write_bytes(b"y")
    plan = build_batch_plan((BatchCopySource("copy-001", first, "tp.ipynb"), BatchCopySource("copy-002", second, "tp.ipynb")), tmp_path / "out", BatchOptions())
    rows = batch_plan_rows(plan)
    assert rows[0].notebook_output_name == "copy-001-tp-correction.ipynb"
    assert all("/" not in value for row in rows for value in (row.original_filename, row.notebook_output_name, row.html_output_name))
    assert has_output_name_collision(plan)
    rows = batch_plan_rows(plan)
    assert rows[0].copy_label == "Copie 1"
