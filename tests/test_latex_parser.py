from pathlib import Path

from tpstudio.parsers import LatexParser


def test_latex_parser_extracts_basic_blocks(tmp_path: Path):
    tex = tmp_path / "test.tex"
    tex.write_text(
        r'''
\title{Lois de Snell Descartes}
\def\nompdf{Lois-de-Snell-Descartes}
\maketitle{Séance de TP}{TP$_2$}
\objectifs
\begin{itemize}
\item Vérifier les lois de Snell Descartes.
\item Déterminer l'indice de réfraction.
\end{itemize}
\materiel
\begin{itemize}
\item Laser.
\item Disque de Péchard.
\end{itemize}
\section*{Première méthode}
\questions
\begin{itemize}
\item Mesurer l'angle limite.
\end{itemize}
''',
        encoding="utf-8",
    )
    document = LatexParser(tex).parse()
    assert document.metadata.title == "Lois de Snell Descartes"
    assert document.metadata.pdf_slug == "Lois-de-Snell-Descartes"
    assert document.objectives == [
        "Vérifier les lois de Snell Descartes",
        "Déterminer l'indice de réfraction",
    ]
    assert document.equipment == ["Laser", "Disque de Péchard"]
    assert document.questions == ["Mesurer l'angle limite"]
    assert any(section.title == "Première méthode" for section in document.sections)
    first_section = document.sections[0]
    assert first_section.level == 1
    assert first_section.items == ["Mesurer l'angle limite"]
