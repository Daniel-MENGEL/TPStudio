from __future__ import annotations

import copy
import json
from pathlib import Path

from tpstudio.copy_comparison import (
    compare_copy_to_model,
    student_feedback_for_comparison,
)


def create_feedback_notebook(
    model_path: str | Path,
    copy_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """Create a non-destructive notebook copy with TPStudio feedback inserted."""

    model = Path(model_path)
    source = Path(copy_path)

    if output_path is None:
        output = _next_available_feedback_path(source)
    else:
        output = Path(output_path)

    comparison = compare_copy_to_model(model, source)
    feedback_messages = student_feedback_for_comparison(comparison)

    data = json.loads(source.read_text(encoding="utf-8"))
    updated = copy.deepcopy(data)

    cells = updated.setdefault("cells", [])
    if not isinstance(cells, list):
        cells = []
        updated["cells"] = cells

    cells.insert(0, _feedback_markdown_cell(feedback_messages))

    metadata = updated.setdefault("metadata", {})
    if isinstance(metadata, dict):
        tpstudio_metadata = metadata.setdefault("tpstudio", {})
        if isinstance(tpstudio_metadata, dict):
            tpstudio_metadata["feedback_inserted"] = True
            tpstudio_metadata["feedback_source_model"] = model.name
            tpstudio_metadata["feedback_source_copy"] = source.name

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(updated, ensure_ascii=False, indent=1), encoding="utf-8")
    return output


def _feedback_markdown_cell(messages: list[str]) -> dict:
    if messages:
        bullet_lines = "\n".join(f"- {message}" for message in messages)
    else:
        bullet_lines = "- Aucune remarque technique bloquante évidente."

    source = (
        "## Retour TPStudio\n\n"
        "Ce retour automatique signale les points techniques à vérifier avant une correction détaillée.\n\n"
        f"{bullet_lines}\n"
    )

    return {
        "cell_type": "markdown",
        "metadata": {"tpstudio": {"cell_role": "student_feedback"}},
        "source": source.splitlines(keepends=True),
    }


def _next_available_feedback_path(copy_path: Path) -> Path:
    base = copy_path.with_name(copy_path.stem + "-retour-tpstudio.ipynb")
    if not base.exists():
        return base

    counter = 2
    while True:
        candidate = copy_path.with_name(copy_path.stem + f"-retour-tpstudio-{counter}.ipynb")
        if not candidate.exists():
            return candidate
        counter += 1
