from __future__ import annotations

from pathlib import Path

from tpstudio.gradebook_bundle import GradebookBundlePaths
from tpstudio.gradebook_summary import format_gradebook_summary_html


def test_gradebook_summary_html_links_generated_csv_files() -> None:
    text = format_gradebook_summary_html(
        session="Séance n°2",
        tp_name="Lois de Snell Descartes",
        kholle_week="25",
        bundle_paths=GradebookBundlePaths(
            followup_csv=Path("Lois-de-Snell-Descartes-semaine-25-suivi.csv"),
            unmatched_csv=Path("Lois-de-Snell-Descartes-semaine-25-anomalies.csv"),
            missing_csv=Path("Lois-de-Snell-Descartes-semaine-25-rapports-non-rendus.csv"),
        ),
    )

    assert 'href="Lois-de-Snell-Descartes-semaine-25-suivi.csv"' in text
    assert 'href="Lois-de-Snell-Descartes-semaine-25-anomalies.csv"' in text
    assert 'href="Lois-de-Snell-Descartes-semaine-25-rapports-non-rendus.csv"' in text
    assert ">Lois-de-Snell-Descartes-semaine-25-suivi.csv</a>" in text


def test_gradebook_summary_html_escapes_links() -> None:
    text = format_gradebook_summary_html(
        session="Séance n°2",
        tp_name="TP test",
        bundle_paths=GradebookBundlePaths(
            followup_csv=Path('suivi "test".csv'),
            unmatched_csv=Path("anomalies <test>.csv"),
            missing_csv=Path("rapports & non rendus.csv"),
        ),
    )

    assert 'href="suivi &quot;test&quot;.csv"' in text
    assert "anomalies &lt;test&gt;.csv" in text
    assert "rapports &amp; non rendus.csv" in text
