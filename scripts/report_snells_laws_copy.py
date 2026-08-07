"""Build a local Markdown teacher report without executing the notebook."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from tpstudio.orchestration import CopyAnalysisOptions, NotebookCopySource, analyze_snells_laws_copy
from tpstudio.reporting import build_teacher_copy_report, render_teacher_report_markdown, summarize_teacher_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rapport professeur Snell-Descartes en lecture seule.")
    parser.add_argument("notebook", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--force", action="store_true", help="Autoriser l'écrasement explicite du rapport.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--student-feedback", action="store_true")
    group.add_argument("--teacher-feedback", action="store_true")
    parser.add_argument("--no-feedback", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.output is not None and args.output.exists() and not args.force:
        raise FileExistsError("Le rapport existe déjà ; utilisez --force pour l'écraser.")
    options = CopyAnalysisOptions(
        render_feedback=not args.no_feedback,
        student_feedback=not args.teacher_feedback,
        teacher_feedback=not args.student_feedback,
    )
    result = analyze_snells_laws_copy(
        NotebookCopySource("local-copy", args.notebook.name, args.notebook),
        options=options,
    )
    report = build_teacher_copy_report(result)
    markdown = render_teacher_report_markdown(report)
    print(summarize_teacher_report(report))
    if args.output is not None:
        args.output.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
