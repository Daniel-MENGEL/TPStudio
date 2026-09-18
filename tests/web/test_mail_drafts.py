from email import policy
from email.parser import BytesParser

import pytest

from tpstudio.web.identity import (
    CopyIdentity,
    CopyIdentitySource,
    CopyIdentityStatus,
    StudentIdentity,
)
from tpstudio.web.mail_drafts import (
    open_correction_mail_in_apple_mail,
    prepare_correction_mail_draft,
)
from tpstudio.web.mail_drafts import load_sender_email, save_sender_email


def _identity(*, second_email="paul@example.net"):
    return CopyIdentity(
        (
            StudentIdentity("Alice DURAND", "DURAND", "Alice", "alice@example.net"),
            StudentIdentity("Paul ROUX", "ROUX", "Paul", second_email),
        ),
        CopyIdentitySource.MANUAL,
        CopyIdentityStatus.CONFIRMED,
    )


def test_prepare_draft_attaches_html_and_never_sends(tmp_path) -> None:
    html = tmp_path / "Lois-de-Snell-DURAND-Alice-ROUX-Paul-Correction.html"
    html.write_text("<html><body>Correction</body></html>", encoding="utf-8")

    draft = prepare_correction_mail_draft(
        source_id="copy-001",
        identity=_identity(),
        html_path=html,
        output_dir=tmp_path / "Brouillons",
        tp_title="Lois de Snell-Descartes",
        sender_email="professeur@example.net",
    )

    message = BytesParser(policy=policy.default).parsebytes(draft.draft_path.read_bytes())
    assert message["To"] == "alice@example.net, paul@example.net"
    assert message["Subject"] == "TP corrigé — Lois de Snell-Descartes"
    assert message["From"] == "professeur@example.net"
    assert draft.sender_email == "professeur@example.net"
    assert message.get_body().get_content().replace("\r\n", "\n") == (
        "Bonjour Alice, bonjour Paul\n\n"
        "Vous trouverez en pièce jointe la correction de votre compte rendu "
        "de TP au format HTML.\n\n"
        "Cordialement.\n\n"
        "Daniel MENGEL\n"
    )
    attachment = next(message.iter_attachments())
    assert attachment.get_filename() == "Lois-de-Snell-DURAND-Alice-ROUX-Paul-Correction.html"
    assert attachment.get_content_type() == "text/html"
    assert attachment.get_payload(decode=True) == html.read_bytes()


def test_prepare_draft_requires_every_roster_email(tmp_path) -> None:
    html = tmp_path / "correction.html"
    html.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="adresse électronique manque"):
        prepare_correction_mail_draft(
            source_id="copy-001",
            identity=_identity(second_email=None),
            html_path=html,
            output_dir=tmp_path / "Brouillons",
            tp_title="TP",
            sender_email="professeur@example.net",
        )


def test_prepare_draft_does_not_overwrite_without_permission(tmp_path) -> None:
    html = tmp_path / "correction.html"
    html.write_text("<html></html>", encoding="utf-8")
    arguments = dict(
        source_id="copy-001",
        identity=_identity(),
        html_path=html,
        output_dir=tmp_path / "Brouillons",
        tp_title="TP",
        sender_email="professeur@example.net",
    )
    prepare_correction_mail_draft(**arguments)
    with pytest.raises(FileExistsError, match="existe déjà"):
        prepare_correction_mail_draft(**arguments)


def test_sender_email_is_stored_locally(tmp_path) -> None:
    settings = tmp_path / "mail.json"

    save_sender_email("Professeur@Example.NET", settings)

    assert load_sender_email(settings) == "professeur@example.net"


def test_draft_uses_crlf_and_ascii_attachment_name_for_apple_mail(tmp_path) -> None:
    html = tmp_path / "Premières-mesures-Correction.html"
    html.write_text("<html></html>", encoding="utf-8")

    draft = prepare_correction_mail_draft(
        source_id="copy-001",
        identity=_identity(),
        html_path=html,
        output_dir=tmp_path / "Brouillons",
        tp_title="TP",
        sender_email="professeur@example.net",
    )

    payload = draft.draft_path.read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(payload)
    attachment = next(message.iter_attachments())
    assert b"\r\n" in payload
    assert attachment.get_filename() == "Premieres-mesures-Correction.html"


def test_open_in_apple_mail_creates_visible_outgoing_message_without_sending(tmp_path) -> None:
    html = tmp_path / 'Correction "élève".html'
    html.write_text("<html></html>", encoding="utf-8")
    draft = prepare_correction_mail_draft(
        source_id="copy-001",
        identity=_identity(),
        html_path=html,
        output_dir=tmp_path / "Brouillons",
        tp_title="TP de l’élève",
        sender_email="professeur@example.net",
    )
    calls = []

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs))

    open_correction_mail_in_apple_mail(draft, runner=fake_runner)

    command, kwargs = calls[0]
    assert command[:2] == ["osascript", "-e"]
    script = command[2]
    assert "make new outgoing message" in script
    assert "visible:true" in script
    assert 'set sender to "professeur@example.net"' in script
    assert 'address:"alice@example.net"' in script
    assert 'address:"paul@example.net"' in script
    assert str(html).replace('"', '\\"') in script
    assert ".zip" not in script
    assert "send newMessage" not in script
    assert kwargs == {"check": True, "capture_output": True, "text": True}
