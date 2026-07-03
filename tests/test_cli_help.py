from __future__ import annotations

import subprocess
import sys


def test_python_module_cli_help_lists_main_commands() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tpstudio.cli", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "usage: tpstudio" in result.stdout
    assert "check-gradebook" in result.stdout
    assert "export-gradebook" in result.stdout
    assert "export-gradebook-bundle" in result.stdout


def test_export_gradebook_bundle_help_lists_important_options() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tpstudio.cli", "export-gradebook-bundle", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    for expected in [
        "--session",
        "--tp-name",
        "--week",
        "--kholle-week",
        "--students-file",
        "--check-first",
        "--summary-md",
        "--summary-html",
        "--open-summary",
        "--open-folder",
        "--prefix",
        "--output-dir",
        "--allow-issues",
    ]:
        assert expected in result.stdout


def test_check_gradebook_help_lists_important_options() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tpstudio.cli", "check-gradebook", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    for expected in [
        "--session",
        "--tp-name",
        "--week",
        "--kholle-week",
        "--students-file",
        "--pattern",
    ]:
        assert expected in result.stdout
