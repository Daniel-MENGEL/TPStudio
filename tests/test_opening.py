from __future__ import annotations

from pathlib import Path

from tpstudio.opening import choose_summary_to_open, open_path


def test_choose_summary_to_open_prefers_html(tmp_path: Path) -> None:
    markdown = tmp_path / "bilan.md"
    html = tmp_path / "bilan.html"

    markdown.write_text("# Bilan", encoding="utf-8")
    html.write_text("<html></html>", encoding="utf-8")

    assert choose_summary_to_open(html_path=html, markdown_path=markdown) == html


def test_choose_summary_to_open_uses_markdown_when_html_missing(tmp_path: Path) -> None:
    markdown = tmp_path / "bilan.md"
    html = tmp_path / "bilan.html"

    markdown.write_text("# Bilan", encoding="utf-8")

    assert choose_summary_to_open(html_path=html, markdown_path=markdown) == markdown


def test_choose_summary_to_open_returns_none_when_no_summary_exists(tmp_path: Path) -> None:
    assert choose_summary_to_open(
        html_path=tmp_path / "bilan.html",
        markdown_path=tmp_path / "bilan.md",
    ) is None


def test_open_path_dry_run_does_not_execute(tmp_path: Path) -> None:
    target = tmp_path / "bilan.html"
    target.write_text("<html></html>", encoding="utf-8")

    result = open_path(target, dry_run=True)

    assert result.path == target
    assert result.command[-1] == str(target)
    assert result.dry_run is True
