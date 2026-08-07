"""Session-scoped temporary materialization of uploaded notebooks."""

from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import shutil
import tempfile

from .model import SelectedCopy, validate_upload_filename, validate_web_source_id


class WebWorkspace:
    def __init__(self, root: Path | None = None) -> None:
        self._temporary = None
        if root is None:
            self._temporary = tempfile.TemporaryDirectory(prefix="tpstudio-web-")
            root = Path(self._temporary.name)
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def materialize(self, filename: str, content: bytes, source_id: str) -> SelectedCopy:
        filename = validate_upload_filename(filename)
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError("Le contenu uploadé doit être binaire.")
        validate_web_source_id(source_id)
        destination = self.root / source_id / Path(filename).name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.resolve().relative_to(self.root)
        destination.write_bytes(bytes(content))
        return SelectedCopy(source_id, filename, destination, sha256(bytes(content)).hexdigest())

    def replace_selection(self, uploads: tuple[tuple[str, bytes], ...]) -> tuple[SelectedCopy, ...]:
        fingerprint = tuple((name, sha256(content).hexdigest()) for name, content in uploads)
        if getattr(self, "_selection_fingerprint", None) == fingerprint:
            return self._selection
        self.reset()
        self._selection = tuple(self.materialize(name, content, f"copy-{index:03d}") for index, (name, content) in enumerate(uploads, 1))
        self._selection_fingerprint = fingerprint
        return self._selection

    def reset(self) -> None:
        for child in self.root.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        self._selection = ()
        self._selection_fingerprint = ()

    def cleanup(self) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def __enter__(self) -> "WebWorkspace":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.cleanup()
