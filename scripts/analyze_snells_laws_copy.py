"""Local, read-only A71c demonstration entry point."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from tpstudio.orchestration import (
    CopyAnalysisOptions,
    NotebookCopySource,
    analyze_snells_laws_copy,
    summarize_copy_analysis,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyse locale Snell-Descartes sans exécution.")
    parser.add_argument("notebook", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--teacher-only", action="store_true")
    group.add_argument("--student-only", action="store_true")
    parser.add_argument("--no-feedback", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    options = CopyAnalysisOptions(
        render_feedback=not args.no_feedback,
        student_feedback=not args.teacher_only,
        teacher_feedback=not args.student_only,
    )
    source = NotebookCopySource("local-copy", args.notebook.name, args.notebook)
    result = analyze_snells_laws_copy(source, options=options)
    print(summarize_copy_analysis(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
