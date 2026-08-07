import nbformat

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
    assert "TPStudio" in html and "sin" in html and "\\sin" in html
    assert "plot" in html and "data:image/png" in html


def test_html_can_hide_code_and_outputs():
    notebook = _notebook()
    html = render_annotated_notebook_html(notebook, options=CopyExportOptions(include_code=False, include_outputs=False))
    assert "plot()" not in html
