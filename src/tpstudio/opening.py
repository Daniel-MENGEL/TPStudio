from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import subprocess


@dataclass(frozen=True)
class OpenResult:
    path: Path
    command: list[str]
    dry_run: bool = False


def open_path(path: str | Path, *, dry_run: bool | None = None) -> OpenResult:
    target = Path(path)

    if dry_run is None:
        dry_run = os.environ.get("TPSTUDIO_OPEN_DRY_RUN") == "1"

    command = build_open_command(target)

    if not dry_run:
        subprocess.run(command, check=False)

    return OpenResult(path=target, command=command, dry_run=dry_run)


def build_open_command(path: str | Path) -> list[str]:
    target = str(Path(path))
    system = platform.system()

    if system == "Darwin":
        return ["open", target]

    if system == "Windows":
        return ["cmd", "/c", "start", "", target]

    return ["xdg-open", target]


def choose_summary_to_open(
    *,
    html_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
) -> Path | None:
    if html_path is not None and Path(html_path).exists():
        return Path(html_path)

    if markdown_path is not None and Path(markdown_path).exists():
        return Path(markdown_path)

    return None
