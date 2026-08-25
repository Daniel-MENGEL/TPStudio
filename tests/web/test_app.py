from pathlib import Path

import tpstudio.web.app as app
from tpstudio.web.app import _analysis_signature, _build_semantic_provider, _input_signature, web_error_message
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


def test_semantic_provider_factory_is_explicit_and_does_not_store_key(monkeypatch):
    assert _build_semantic_provider(False, environ={"OPENAI_API_KEY": "secret"}) is None
    assert _build_semantic_provider(True, environ={}) is None
    observed = {}

    class FakeProvider:
        def __init__(self, *, model=None, **kwargs):
            observed["model"] = model
            observed["kwargs"] = kwargs

    monkeypatch.setenv("TPSTUDIO_OPENAI_MODEL", "public-test-model")
    monkeypatch.setattr(app, "OpenAISemanticAnalysisProvider", FakeProvider)
    provider = _build_semantic_provider(True, environ={"OPENAI_API_KEY": "secret"})
    assert isinstance(provider, FakeProvider)
    assert observed == {"model": "public-test-model", "kwargs": {}}
    assert "secret" not in repr(provider)


def test_analysis_signature_is_stable_and_option_model_specific():
    base = (("copy",), "out", WebBatchOptions())
    assert _analysis_signature(base, False, "gpt-5-mini") == _analysis_signature(base, False, "gpt-5-mini")
    assert _analysis_signature(base, False, "gpt-5-mini") != _analysis_signature(base, True, "gpt-5-mini")
    assert _analysis_signature(base, True, "gpt-5-mini") != _analysis_signature(base, True, "other-model")
