from pathlib import Path

from tpstudio.web.app import _input_signature, web_error_message
from tpstudio.web.model import SelectedCopy, WebBatchOptions


def test_signature_changes_for_same_size_content_hashes():
    first = SelectedCopy("copy-001", "tp.ipynb", Path("tp.ipynb"), "a" * 64)
    second = SelectedCopy("copy-001", "tp.ipynb", Path("tp.ipynb"), "b" * 64)
    options = WebBatchOptions()
    assert _input_signature((first,), Path("out"), options) != _input_signature((second,), Path("out"), options)


def test_web_errors_do_not_expose_workspace_paths():
    for text in ("/Users/example/private/tp.ipynb", "/home/student/tp.ipynb", "/var/folders/xx/tp.ipynb", r"C:\\Users\\Student\\tp.ipynb"):
        message = web_error_message(ValueError(text))
        assert message == "Impossible de préparer le lot."
        assert text not in message
    assert web_error_message(ValueError("Aucune copie sélectionnée.")) == "Aucune copie sélectionnée."
