import pytest
from tpstudio.export import default_export_names


@pytest.mark.parametrize(("source", "expected"), (
    ("tp.ipynb", ("tp-correction.ipynb", "tp-correction.html")),
    ("tp", ("tp-correction.ipynb", "tp-correction.html")),
    ("foo.bar.ipynb", ("foo.bar-correction.ipynb", "foo.bar-correction.html")),
    ("foo-correction.ipynb", ("foo-correction.ipynb", "foo-correction.html")),
))
def test_default_export_names(source, expected):
    assert default_export_names(source) == expected


def test_names_use_only_filename_and_reject_empty():
    assert default_export_names("/private/path/tp.ipynb")[0] == "tp-correction.ipynb"
    with pytest.raises(ValueError): default_export_names(" ")
