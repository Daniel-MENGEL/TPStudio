import nbformat

from tpstudio.annotation import AnnotationKind, AnnotationPlacement, NotebookAnnotation, render_notebook_annotation
from tpstudio.feedback import FeedbackAudience
from tpstudio.reporting import TeacherReportSeverity
from tpstudio.export import CopyExportOptions, render_annotated_notebook_html


def _notebook():
    image = nbformat.v4.new_output("display_data", data={"image/png": "iVBORw0KGgo=", "text/plain": "figure"})
    code = nbformat.v4.new_code_cell("plot()", execution_count=1); code.outputs = [image]
    return nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("Formule $n=\\sin(i)$\n\n$$n=1.5$$"), code])


def test_html_preserves_markdown_latex_images_and_hides_internal_markers():
    html = render_annotated_notebook_html(_notebook(), options=CopyExportOptions())
    assert html.lower().count("<html") == 1
    assert html.lower().count("</html>") == 1
    assert html.lower().count("<body") == 1
    assert html.lower().count("</body>") == 1
    assert html.lower().count("<title") == 1
    assert html.count('class="tpstudio-banner"') == 1
    assert "Copie corrigée" in html and "TPStudio" not in html
    assert "sin" in html and "\\sin" in html
    assert "plot" in html and "data:image/png" in html


def test_html_can_hide_code_and_outputs():
    notebook = _notebook()
    html = render_annotated_notebook_html(notebook, options=CopyExportOptions(include_code=False, include_outputs=False))
    assert "plot()" not in html


def test_html_contains_annotation_palette_css():
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell(
        '<div class="tpstudio-annotation tpstudio-severity-info"></div>\n\n> **Très bien**'
    )])
    html = render_annotated_notebook_html(notebook, options=CopyExportOptions())
    assert "tpstudio-severity-info" in html
    assert "background: #edf7ee" in html


def test_html_tolerates_missing_student_attachment_without_mutation():
    for reference in ("attachment:??", "attachment:"):
        cell = nbformat.v4.new_markdown_cell(
            f"### Schéma expérimental\n\n![Schéma du binôme]({reference})"
        )
        notebook = nbformat.v4.new_notebook(cells=[cell])

        html = render_annotated_notebook_html(
            notebook,
            options=CopyExportOptions(),
        )

        assert "Image non insérée" in html
        assert "Schéma du binôme" in html
        assert reference not in html
        assert reference in notebook.cells[0].source


def test_html_removes_stray_closing_div_without_mutating_student_copy():
    source = '<div class="answer">Réponse complète.</div>\n</div>\n\n## Question 2'
    notebook = nbformat.v4.new_notebook(
        cells=[nbformat.v4.new_markdown_cell(source)]
    )

    html = render_annotated_notebook_html(
        notebook,
        options=CopyExportOptions(),
    )

    assert "Réponse complète." in html
    assert "Question 2" in html
    assert notebook.cells[0].source == source


def test_html_multiple_annotations_use_one_global_palette_and_escape_message():
    cells = [
        nbformat.v4.new_markdown_cell('<blockquote class="tpstudio-annotation tpstudio-severity-info" style="background:#edf7ee"><strong>Très bien</strong><br>Premier</blockquote>'),
        nbformat.v4.new_markdown_cell('<blockquote class="tpstudio-annotation tpstudio-severity-blocking" style="background:#fceeee"><strong>Problème</strong><br>&lt;tag&gt; &amp; **gras**</blockquote>'),
    ]
    html = render_annotated_notebook_html(nbformat.v4.new_notebook(cells=cells), options=CopyExportOptions())
    assert html.count(".tpstudio-annotation { margin") == 1
    assert html.count("tpstudio-annotation") >= 2
    assert "&lt;tag&gt; &amp;" in html


def test_annotation_markdown_is_rendered_and_untrusted_html_stays_text():
    message = "**gras**\n\n`code`\n\n- élément 1\n- élément 2\n\n$x^2$\n\n<tag> & texte\n\n<script>alert(1)</script>\n<img src=x onerror=alert(1)>"
    annotation = NotebookAnnotation(
        "tpstudio:rendering", AnnotationKind.FEEDBACK, FeedbackAudience.STUDENT,
        message, ("feedback",), None, None, 0, AnnotationPlacement.AFTER_CELL,
        TeacherReportSeverity.INFO,
    )
    source = render_notebook_annotation(annotation)
    assert "<style>" not in source
    assert "tpstudio-annotation" in source and "&lt;tag&gt; &amp;" in source
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell(source)])
    html = render_annotated_notebook_html(notebook, options=CopyExportOptions())
    assert "<strong>gras</strong>" in html
    assert "<code>code</code>" in html
    assert "<ul>" in html and "<li>élément 1</li>" in html
    assert "$x^2$" in html
    assert "&lt;tag&gt; &amp; texte" in html
    assert "<script>alert" not in html.lower() and "<img" not in html.lower()
    assert "<img src" not in html.lower()
