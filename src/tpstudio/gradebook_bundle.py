from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from tpstudio.gradebook_export import export_gradebook_csv


@dataclass(frozen=True)
class GradebookBundlePaths:
    followup_csv: Path
    unmatched_csv: Path
    missing_csv: Path


def export_gradebook_bundle(
    copies_dir: str | Path,
    *,
    session: str,
    tp_name: str,
    kholle_week: str | None = None,
    date_value: str | None = None,
    pattern: str = "*.ipynb",
    students_file: str | Path | None = None,
    output_dir: str | Path | None = None,
    prefix: str | None = None,
) -> GradebookBundlePaths:
    directory = Path(copies_dir)
    destination = Path(output_dir) if output_dir else directory

    paths = build_gradebook_bundle_paths(
        destination,
        tp_name=tp_name,
        kholle_week=kholle_week or date_value or "",
        prefix=prefix,
    )

    export_gradebook_csv(
        directory,
        paths.followup_csv,
        session=session,
        tp_name=tp_name,
        week_value=kholle_week,
        date_value=date_value,
        pattern=pattern,
        students_file=students_file,
        unmatched_output_path=paths.unmatched_csv,
        missing_output_path=paths.missing_csv,
    )

    return paths


def build_gradebook_bundle_paths(
    output_dir: str | Path,
    *,
    tp_name: str,
    kholle_week: str = "",
    prefix: str | None = None,
) -> GradebookBundlePaths:
    directory = Path(output_dir)
    base = prefix or build_gradebook_bundle_prefix(
        tp_name=tp_name,
        kholle_week=kholle_week,
    )

    return GradebookBundlePaths(
        followup_csv=directory / f"{base}-suivi.csv",
        unmatched_csv=directory / f"{base}-anomalies.csv",
        missing_csv=directory / f"{base}-rapports-non-rendus.csv",
    )


def build_gradebook_bundle_prefix(
    *,
    tp_name: str,
    kholle_week: str = "",
) -> str:
    slug = slugify_filename(tp_name)

    if kholle_week:
        week_slug = slugify_filename(str(kholle_week))
        return f"{slug}-semaine-{week_slug}"

    return slug


def slugify_filename(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    without_accents = "".join(
        char
        for char in normalized
        if unicodedata.category(char) != "Mn"
    )

    cleaned = without_accents.replace("°", "")
    cleaned = cleaned.replace("№", "")
    cleaned = cleaned.replace("'", " ")
    cleaned = cleaned.replace("’", " ")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", cleaned)
    cleaned = cleaned.strip("-")
    cleaned = re.sub(r"-+", "-", cleaned)

    return cleaned or "export-tpstudio"
