from streamlit.testing.v1 import AppTest


def test_streamlit_app_smoke_without_network():
    app = AppTest.from_file("src/tpstudio/web/app.py").run()
    assert app.exception == []
    assert any("TPStudio" in title.value for title in app.title)
    assert "tpstudio_web_uploads_0" in app.session_state
    assert any("Dossier des corrections" in item.label for item in app.text_input)
    assert any("Vérifier le lot" in button.label for button in app.button)
    assert any("Réinitialiser" in button.label for button in app.button)
