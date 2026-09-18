"""Prepare local RFC 5322 drafts without sending any message."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import parseaddr
import json
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from zipfile import ZIP_DEFLATED, ZipFile

from .identity import CopyIdentity, CopyIdentityStatus


@dataclass(frozen=True, slots=True)
class CorrectionMailDraft:
    source_id: str
    recipients: tuple[str, ...]
    student_names: tuple[str, ...]
    subject: str
    sender_email: str
    html_path: Path
    draft_path: Path


_MAIL_BODY_HTML = (
    "Bonjour,\n\n"
    "Vous trouverez en pièce jointe la correction de votre compte rendu "
    "de TP au format HTML. Ce fichier peut être ouvert directement dans "
    "un navigateur.\n\n"
    "Cordialement.\n"
)

_MAIL_BODY_ZIP = (
    "Bonjour,\n\n"
    "Vous trouverez en pièce jointe la correction de votre compte rendu "
    "de TP. Décompressez l’archive ZIP, puis ouvrez le fichier HTML dans "
    "un navigateur.\n\n"
    "Cordialement.\n"
)


def default_mail_settings_path() -> Path:
    return Path.home() / ".tpstudio" / "mail.json"


def load_sender_email(path: Path | None = None) -> str:
    settings_path = default_mail_settings_path() if path is None else path
    if not settings_path.exists():
        return ""
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        return _validated_email(str(payload.get("sender_email", "")), allow_empty=True)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return ""


def save_sender_email(sender_email: str, path: Path | None = None) -> Path:
    settings_path = default_mail_settings_path() if path is None else path
    sender = _validated_email(sender_email)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps({"sender_email": sender}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return settings_path


def _validated_email(value: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError("L'adresse d'expédition est invalide.")
    email = parseaddr(value.strip())[1]
    if allow_empty and not email:
        return ""
    if not email or "@" not in email or email != value.strip():
        raise ValueError("L'adresse d'expédition est invalide.")
    return email.casefold()


def _mail_safe_attachment_name(name: str) -> str:
    """Use a conservative ASCII filename for Apple Mail attachments."""

    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_name).strip("-.")
    ascii_name = re.sub(r"-+\.", ".", ascii_name)
    return ascii_name or "correction.html"


def _applescript_string(value: str) -> str:
    """Return text escaped for an AppleScript string literal."""

    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "\\n")


def open_correction_mail_in_apple_mail(
    draft: CorrectionMailDraft,
    *,
    runner=subprocess.run,
) -> None:
    """Open a real, unsent compose window in Apple Mail.

    Opening an RFC 5322 ``.eml`` file in Mail displays a received-message
    preview.  Creating an outgoing message through AppleScript instead gives
    the teacher a normal editable window with Mail's Send button.  Nothing is
    sent by this function.
    """

    if not isinstance(draft, CorrectionMailDraft):
        raise TypeError("Le brouillon de courriel est invalide.")
    if not draft.html_path.is_file():
        raise FileNotFoundError("La correction HTML est introuvable.")

    # Apple Mail opens HTML attachments through a short-lived SavedAttachment
    # path.  On some macOS versions that file is removed before Safari reads
    # it (NSURLErrorDomain -3001).  A ZIP bypasses that broken preview path and
    # leaves the actual HTML available after normal extraction.
    attachment_dir = draft.draft_path.parent / "Pieces-jointes"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    safe_html_name = _mail_safe_attachment_name(draft.html_path.name)
    stable_html_path = attachment_dir / safe_html_name
    shutil.copyfile(draft.html_path, stable_html_path)
    attachment_path = attachment_dir / f"{Path(safe_html_name).stem}.zip"
    with ZipFile(attachment_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.write(stable_html_path, arcname=safe_html_name)

    recipients = "\n".join(
        "make new to recipient at end of to recipients with properties "
        f'{{address:"{_applescript_string(address)}"}}'
        for address in draft.recipients
    )
    script = f'''set attachmentFile to POSIX file "{_applescript_string(str(attachment_path))}"
tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:"{_applescript_string(draft.subject)}", content:"{_applescript_string(_MAIL_BODY_ZIP)}", visible:true}}
    tell newMessage
        try
            set sender to "{_applescript_string(draft.sender_email)}"
        end try
        {recipients}
        make new attachment with properties {{file name:attachmentFile}} at after last paragraph
    end tell
    activate
end tell'''
    try:
        runner(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise OSError(f"Mail n'a pas pu ouvrir le brouillon : {detail.strip()}") from exc


def prepare_correction_mail_draft(
    *,
    source_id: str,
    identity: CopyIdentity,
    html_path: Path,
    output_dir: Path,
    tp_title: str,
    sender_email: str,
    overwrite: bool = False,
) -> CorrectionMailDraft:
    """Create one ``.eml`` draft with the corrected HTML attached.

    This function deliberately has no sending capability.  The resulting file
    can be opened and reviewed in a mail client before the teacher sends it.
    """

    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("L'identifiant de la copie est absent.")
    if not isinstance(identity, CopyIdentity):
        raise TypeError("L'identité de la copie est invalide.")
    if identity.status is not CopyIdentityStatus.CONFIRMED or not identity.students:
        raise ValueError("L'identité doit être confirmée avant de préparer le courriel.")
    if not isinstance(html_path, Path) or html_path.suffix.casefold() != ".html":
        raise ValueError("La correction HTML est invalide.")
    if not html_path.is_file():
        raise FileNotFoundError("La correction HTML est introuvable.")
    if not isinstance(output_dir, Path):
        raise TypeError("Le dossier des brouillons est invalide.")
    if not isinstance(tp_title, str) or not tp_title.strip():
        raise ValueError("Le titre du TP est absent.")
    if type(overwrite) is not bool:
        raise TypeError("L'option de remplacement doit être booléenne.")
    sender = _validated_email(sender_email)

    recipients = tuple(
        student.email for student in identity.students if student.email is not None
    )
    if len(recipients) != len(identity.students):
        raise ValueError("Une adresse électronique manque dans le roster.")
    if len(set(recipients)) != len(recipients):
        raise ValueError("Une même adresse électronique apparaît plusieurs fois.")

    names = tuple(student.display_name for student in identity.students)
    subject = f"TP corrigé — {tp_title}"
    message = EmailMessage(policy=SMTP)
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(_MAIL_BODY_HTML)
    message.add_attachment(
        html_path.read_bytes(),
        maintype="text",
        subtype="html",
        filename=_mail_safe_attachment_name(html_path.name),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    draft_path = output_dir / f"{html_path.stem}.eml"
    if draft_path.exists() and not overwrite:
        raise FileExistsError("Un brouillon existe déjà pour cette copie.")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{draft_path.stem}-", suffix=".eml.tmp", dir=output_dir
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(message.as_bytes(policy=SMTP))
        os.replace(temporary_path, draft_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return CorrectionMailDraft(
        source_id=source_id,
        recipients=recipients,
        student_names=names,
        subject=subject,
        sender_email=sender,
        html_path=html_path,
        draft_path=draft_path,
    )
