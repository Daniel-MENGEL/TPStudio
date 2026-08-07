"""Export one Snell-Descartes copy to a derived notebook and HTML file."""

from __future__ import annotations

import argparse
from pathlib import Path

from tpstudio.export import CopyExportOptions, export_snells_laws_copy, summarize_copy_export


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export local Snell-Descartes artifacts without execution.")
    parser.add_argument("notebook", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--teacher-copy", action="store_true")
    parser.add_argument("--include-diagnostics", action="store_true")
    parser.add_argument("--hide-code", action="store_true")
    parser.add_argument("--hide-outputs", action="store_true")
    args = parser.parse_args(argv)
    result = export_snells_laws_copy(
        args.notebook, args.output_dir,
        options=CopyExportOptions(
            overwrite=args.overwrite,
            include_teacher_feedback=args.teacher_copy,
            include_diagnostics=args.include_diagnostics,
            include_code=not args.hide_code,
            include_outputs=not args.hide_outputs,
        ),
    )
    print(summarize_copy_export(result))
    print(f"Notebook: {result.notebook_artifact.path.name}")
    print(f"HTML: {result.html_artifact.path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
