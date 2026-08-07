"""Run an explicit, sequential Snell-Descartes export batch."""

from __future__ import annotations

import argparse
from pathlib import Path

from tpstudio.batch import (
    BatchCopySource, BatchOptions, build_batch_plan, render_batch_report_markdown,
    run_snells_laws_batch, summarize_batch_run, write_batch_report,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export explicite d'un petit lot Snell-Descartes.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--teacher-copy", action="store_true")
    parser.add_argument("--include-diagnostics", action="store_true")
    parser.add_argument("--hide-code", action="store_true")
    parser.add_argument("--hide-outputs", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("notebooks", nargs="+", type=Path)
    args = parser.parse_args(argv)
    sources = tuple(BatchCopySource(f"copy-{index:03d}", path, path.name) for index, path in enumerate(args.notebooks, 1))
    plan = build_batch_plan(sources, args.output_dir, BatchOptions(
        overwrite=args.overwrite, continue_on_error=not args.stop_on_error,
        include_teacher_feedback=args.teacher_copy,
        include_diagnostics=args.include_diagnostics,
        hide_code=args.hide_code, hide_outputs=args.hide_outputs,
    ))
    result = run_snells_laws_batch(plan)
    print(summarize_batch_run(result))
    if args.report:
        write_batch_report(render_batch_report_markdown(result), args.report, overwrite=args.overwrite)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
