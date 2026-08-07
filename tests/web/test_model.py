from pathlib import Path

import pytest

from tpstudio.web.model import SelectedCopy, WebBatchOptions, validate_upload_filename, validate_web_source_id


def test_selected_copy_and_options_are_immutable():
    copy = SelectedCopy("copy-001", "tp.ipynb", Path("/tmp/tp.ipynb"), "0" * 64)
    assert copy.source_id == "copy-001"
    with pytest.raises(AttributeError):
        copy.source_id = "x"
    assert not WebBatchOptions().overwrite


@pytest.mark.parametrize("name", ["../tp.ipynb", "folder/tp.ipynb", "folder\\tp.ipynb", "tp.txt", ""])
def test_upload_filename_is_restricted(name):
    with pytest.raises(ValueError):
        validate_upload_filename(name)


def test_uppercase_notebook_extension_is_accepted():
    assert validate_upload_filename("TP.IPYNB") == "TP.IPYNB"


def test_source_id_and_hash_validation():
    assert validate_web_source_id("copy-001") == "copy-001"
    for source_id in ("../copy-001", "copy/x", "copy-1"):
        with pytest.raises(ValueError):
            validate_web_source_id(source_id)
    with pytest.raises(ValueError):
        SelectedCopy("copy-001", "tp.ipynb", Path("tp.ipynb"), "bad")
