"""Create an explicit, read-only-derived Snell-Descartes annotated copy."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from tpstudio.annotation import (
    AnnotationOptions, apply_annotation_plan, build_annotation_plan,
    summarize_annotation_plan, write_annotated_notebook,
)
from tpstudio.orchestration import NotebookCopySource, analyze_snells_laws_copy, load_notebook_copy
from tpstudio.reporting import build_teacher_copy_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Annotation locale Snell-Descartes sans exécution.")
    parser.add_argument("notebook", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--teacher-copy", action="store_true")
    parser.add_argument("--include-diagnostics", action="store_true")
    parser.add_argument("--keep-existing", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source = NotebookCopySource("local-copy", args.notebook.name, args.notebook)
    analysis = analyze_snells_laws_copy(source)
    report = build_teacher_copy_report(analysis)
    options = AnnotationOptions(
        include_teacher_feedback=args.teacher_copy,
        include_diagnostics=args.include_diagnostics,
        replace_existing_tpstudio_annotations=not args.keep_existing,
    )
    plan = build_annotation_plan(analysis, report, options)
    print(summarize_annotation_plan(plan))
    if args.output is not None:
        notebook = load_notebook_copy(source)
        annotated = apply_annotation_plan(notebook, plan, options)
        write_annotated_notebook(
            annotated, args.output, overwrite=args.overwrite,
            source_path=args.notebook,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
