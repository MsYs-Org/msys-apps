from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from msys_apps.storage import AtomicTextStore, NoteStorageError, notes_path


class AtomicTextStoreTests(unittest.TestCase):
    def test_missing_note_is_empty_and_utf8_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = AtomicTextStore(Path(temporary) / "state" / "note.txt")
            self.assertEqual(store.load(), "")
            size = store.save("你好, MSYS\n")
            self.assertEqual(size, len("你好, MSYS\n".encode("utf-8")))
            self.assertEqual(store.load(), "你好, MSYS\n")

    def test_replacement_is_atomic_and_leaves_no_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "note.txt"
            store = AtomicTextStore(path)
            store.save("old")
            store.save("new")
            self.assertEqual(store.load(), "new")
            self.assertEqual(list(path.parent.glob(".*.tmp")), [])

    def test_failed_replace_preserves_previous_note(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "note.txt"
            store = AtomicTextStore(path)
            store.save("committed")
            with mock.patch("msys_apps.storage.os.replace", side_effect=OSError("disk")):
                with self.assertRaises(NoteStorageError):
                    store.save("uncommitted")
            self.assertEqual(store.load(), "committed")
            self.assertEqual(list(path.parent.glob(".*.tmp")), [])

    def test_byte_limit_applies_to_utf8_not_character_count(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = AtomicTextStore(Path(temporary) / "note.txt", maximum_bytes=5)
            store.save("12345")
            with self.assertRaisesRegex(NoteStorageError, "too large"):
                store.save("你好")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_load_refuses_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.txt"
            target.write_text("secret", encoding="utf-8")
            link = root / "note.txt"
            link.symlink_to(target)
            with self.assertRaises(NoteStorageError):
                AtomicTextStore(link).load()

    def test_state_path_prefers_component_state_directory(self) -> None:
        self.assertEqual(
            notes_path({"MSYS_APP_STATE_DIR": "/state/app", "HOME": "/home/user"}),
            Path("/state/app/notes/note.txt"),
        )


if __name__ == "__main__":
    unittest.main()

