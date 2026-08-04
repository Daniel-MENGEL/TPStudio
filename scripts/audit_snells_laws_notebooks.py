"""Inspect notebook structure without executing or modifying student code."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Sequence

import nbformat


MARKERS = (
    "Réponse",
    "Résultat",
    "Interprétation",
    "Conclusion",
    "Protocole",
    "Objectif",
    "checklist",
    "texte à compléter",
    "TODO",
)
_EXTERNAL_REFERENCE = re.compile(
    r"(?:https?://[^\s)\]>]+|[\w./ -]+\.(?:csv|txt|dat|png|jpe?g|svg|pdf))",
    re.IGNORECASE,
)


def _source(cell: Any) -> str:
    source = cell.get("source", "")
    return source if isinstance(source, str) else "".join(source)


def _source_digest(cell: Any) -> str:
    payload = f"{cell.get('cell_type', '')}\0{_source(cell)}".encode()
    return hashlib.sha256(payload).hexdigest()


def _heading(source: str) -> str | None:
    for line in source.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            return match.group(1)
    return None


def audit_notebook(path: str | Path) -> dict[str, Any]:
    """Return a deterministic, structural summary of one notebook."""

    notebook_path = Path(path)
    notebook = nbformat.read(notebook_path, as_version=4)
    cells = notebook.cells
    code_cells = [cell for cell in cells if cell.cell_type == "code"]
    outputs = [output for cell in code_cells for output in cell.get("outputs", ())]
    metadata = notebook.metadata

    marker_counts = {marker: 0 for marker in MARKERS}
    question_mark_cells: list[int] = []
    empty_cells: list[int] = []
    headings: list[dict[str, Any]] = []
    external_references: list[str] = []
    cell_records: list[dict[str, Any]] = []

    for index, cell in enumerate(cells):
        source = _source(cell)
        source_casefold = source.casefold()
        for marker in MARKERS:
            marker_counts[marker] += source_casefold.count(marker.casefold())
        if cell.cell_type == "code" and "?" in source:
            question_mark_cells.append(index)
        if not source.strip():
            empty_cells.append(index)
        title = _heading(source) if cell.cell_type == "markdown" else None
        if title is not None:
            headings.append({"cell_index": index, "title": title})
        for reference in _EXTERNAL_REFERENCE.findall(source):
            if reference not in external_references:
                external_references.append(reference)
        cell_records.append(
            {
                "index": index,
                "id": cell.get("id"),
                "cell_type": cell.cell_type,
                "source_digest": _source_digest(cell),
                "heading": title,
                "empty": not source.strip(),
                "execution_count": cell.get("execution_count")
                if cell.cell_type == "code"
                else None,
                "output_types": [
                    output.get("output_type") for output in cell.get("outputs", ())
                ]
                if cell.cell_type == "code"
                else [],
            }
        )

    return {
        "path": str(notebook_path),
        "valid_notebook": True,
        "nbformat": notebook.nbformat,
        "nbformat_minor": notebook.nbformat_minor,
        "cell_count": len(cells),
        "cell_types": {
            kind: sum(cell.cell_type == kind for cell in cells)
            for kind in ("markdown", "code", "raw")
        },
        "output_count": len(outputs),
        "error_output_count": sum(
            output.get("output_type") == "error" for output in outputs
        ),
        "unexecuted_code_cells": [
            index
            for index, cell in enumerate(cells)
            if cell.cell_type == "code" and cell.get("execution_count") is None
        ],
        "metadata_keys": sorted(metadata.keys()),
        "kernel": dict(metadata.get("kernelspec", {})),
        "attachment_count": sum(
            len(cell.get("attachments", {})) for cell in cells
        ),
        "marker_counts": marker_counts,
        "question_mark_cells": question_mark_cells,
        "empty_cells": empty_cells,
        "headings": headings,
        "external_references": external_references,
        "cells": cell_records,
    }


def compare_notebooks(reference: str | Path, candidate: str | Path) -> dict[str, Any]:
    """Compare cell structure using exact type-and-source signatures."""

    reference_audit = audit_notebook(reference)
    candidate_audit = audit_notebook(candidate)
    reference_signatures = [cell["source_digest"] for cell in reference_audit["cells"]]
    candidate_signatures = [cell["source_digest"] for cell in candidate_audit["cells"]]
    matcher = SequenceMatcher(a=reference_signatures, b=candidate_signatures, autojunk=False)
    added: list[int] = []
    removed: list[int] = []
    modified: list[dict[str, int]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            added.extend(range(j1, j2))
        elif tag == "delete":
            removed.extend(range(i1, i2))
        else:
            paired = min(i2 - i1, j2 - j1)
            modified.extend(
                {"reference_index": i1 + offset, "candidate_index": j1 + offset}
                for offset in range(paired)
            )
            removed.extend(range(i1 + paired, i2))
            added.extend(range(j1 + paired, j2))
    return {
        "reference": str(Path(reference)),
        "candidate": str(Path(candidate)),
        "unchanged_cell_count": sum(
            block.size for block in matcher.get_matching_blocks()
        ),
        "added_candidate_cells": added,
        "removed_reference_cells": removed,
        "modified_cells": modified,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit interne, structurel et non exécutant de notebooks."
    )
    parser.add_argument("notebooks", nargs="+", type=Path)
    parser.add_argument(
        "--reference",
        type=Path,
        help="Compare chaque notebook fourni à cette référence.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result: dict[str, Any] = {
        "notebooks": [audit_notebook(path) for path in args.notebooks]
    }
    if args.reference is not None:
        result["comparisons"] = [
            compare_notebooks(args.reference, path) for path in args.notebooks
        ]
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
