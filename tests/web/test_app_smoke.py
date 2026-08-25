from streamlit.testing.v1 import AppTest

from tpstudio.web.app import _graph_detail_label


def test_streamlit_app_smoke_without_network():
    app = AppTest.from_file("src/tpstudio/web/app.py").run()
    assert app.exception == []
    assert any("TPStudio" in title.value for title in app.title)
    assert "tpstudio_web_uploads_0" in app.session_state
    assert not any("Dossier des corrections" in item.label for item in app.text_input)
    assert any("détection automatique du TP par copie" in item.value for item in app.info)
    assert any("Vérifier le lot" in button.label for button in app.button)
    semantic = next(item for item in app.checkbox if item.label == "Activer l’analyse sémantique (API OpenAI)")
    assert semantic.value is False
    assert any("Réinitialiser" in button.label for button in app.button)


def test_graph_detail_labels_are_stable_and_unique_per_copy():
    labels = {
        _graph_detail_label(source, index)
        for source in ("review-copy-a-12345678", "review-copy-b-87654321")
        for index in (1, 2)
    }
    assert labels == {
        "Détails 1 · 12345678", "Détails 2 · 12345678",
        "Détails 1 · 87654321", "Détails 2 · 87654321",
    }
    assert _graph_detail_label("review-copy-a-12345678", 1) == _graph_detail_label("review-copy-a-12345678", 1)
