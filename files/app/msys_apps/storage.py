"""Small atomic UTF-8 store for the Notes application."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Final


MAX_NOTE_BYTES: Final = 512 * 1024


class NoteStorageError(OSError):
    """A note could not be safely loaded or committed."""


def notes_path(environment: dict[str, str] | None = None) -> Path:
    env = os.environ if environment is None else environment
    state = env.get("MSYS_APP_STATE_DIR") or env.get("MSYS_STATE_DIR")
    if state:
        return Path(state) / "notes" / "note.txt"
    home = Path(env.get("HOME", str(Path.home())))
    return home / ".local" / "state" / "msys" / "apps" / "notes" / "note.txt"


class AtomicTextStore:
    def __init__(self, path: Path, *, maximum_bytes: int = MAX_NOTE_BYTES) -> None:
        self.path = Path(path)
        self.maximum_bytes = int(maximum_bytes)
        if self.maximum_bytes <= 0:
            raise ValueError("maximum_bytes must be positive")

    def load(self) -> str:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.path, flags)
        except FileNotFoundError:
            return ""
        except OSError as exc:
            raise NoteStorageError(f"Cannot open note: {exc}") from exc
        try:
            size = os.fstat(descriptor).st_size
            if size > self.maximum_bytes:
                raise NoteStorageError("Saved note exceeds the size limit")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(65536, self.maximum_bytes + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > self.maximum_bytes:
                    raise NoteStorageError("Saved note exceeds the size limit")
        finally:
            os.close(descriptor)
        try:
            return b"".join(chunks).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NoteStorageError("Saved note is not valid UTF-8") from exc

    def save(self, text: str) -> int:
        if not isinstance(text, str):
            raise TypeError("Note must be text")
        encoded = text.encode("utf-8")
        if len(encoded) > self.maximum_bytes:
            raise NoteStorageError(
                f"Note is too large ({len(encoded)} bytes; limit {self.maximum_bytes})"
            )
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError as exc:
            raise NoteStorageError(f"Cannot create note directory: {exc}") from exc
        temporary = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor: int | None = None
        try:
            descriptor = os.open(temporary, flags, 0o600)
            view = memoryview(encoded)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise NoteStorageError("Short write while saving note")
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.replace(temporary, self.path)
            self._sync_directory()
        except NoteStorageError:
            raise
        except OSError as exc:
            raise NoteStorageError(f"Cannot save note: {exc}") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass
        return len(encoded)

    def _sync_directory(self) -> None:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0)
        try:
            descriptor = os.open(self.path.parent, flags)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)

