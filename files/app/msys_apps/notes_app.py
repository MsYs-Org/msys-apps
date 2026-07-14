"""Touch-friendly persistent Notes application."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .common_ui import FIELD, TEXT, TouchApplication
from .localization import AppsI18n
from .storage import AtomicTextStore, NoteStorageError, notes_path
from msys_sdk.ui_fonts import font_spec


class NotesApplication(TouchApplication):
    def __init__(self, store: AtomicTextStore | None = None) -> None:
        i18n = AppsI18n()
        super().__init__(
            title=i18n("notes.window_title"),
            identity="org.msys.apps.notes",
            icon_name="notes.ppm",
            i18n=i18n,
        )
        self.store = store or AtomicTextStore(notes_path())
        self._save_timer: str | None = None
        self._dirty = False

        header = self.header(self.i18n("notes.title"))
        ttk.Button(
            header,
            text=self.i18n("common.save"),
            style="Accent.TButton",
            command=self.submit,
        ).pack(
            side="right", padx=(5, 0)
        )
        ttk.Button(
            header,
            text=self.i18n("common.clear"),
            command=self.clear,
        ).pack(side="right")

        body = ttk.Frame(self.root, padding=(8, 2, 8, 8))
        body.pack(fill="both", expand=True)
        self.editor = tk.Text(
            body,
            bg=FIELD,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#285f91",
            relief="flat",
            wrap="word",
            undo=True,
            maxundo=100,
            padx=10,
            pady=9,
            font=font_spec(self.root, 12 if self.compact else 14),
        )
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.editor.yview)
        self.editor.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.editor.pack(side="left", fill="both", expand=True)
        self.bind_touch_text_scroll(self.editor)
        self.editor.bind("<<Modified>>", self._modified)
        self.root.bind("<Control-s>", self._submit_shortcut)
        self.root.bind("<Control-Return>", self._submit_shortcut)
        self._load()
        self.attach_input_method(
            self.editor,
            mode="zh" if self.i18n.locale.lower().startswith("zh") else "en",
        )
        self.editor.focus_set()
        self.activate_lifecycle()

    def _load(self) -> None:
        try:
            text = self.store.load()
        except NoteStorageError:
            self.set_status(self.i18n("notes.load_failed"), error=True)
            text = ""
        self.editor.insert("1.0", text)
        self.editor.edit_modified(False)
        self._dirty = False
        if text:
            self.set_status(self.i18n("common.loaded"))

    def _modified(self, _event: object = None) -> None:
        if not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        self._dirty = True
        self.set_status(self.i18n("common.unsaved"))
        if self._save_timer is not None:
            self.root.after_cancel(self._save_timer)
        self._save_timer = self.root.after(900, self.save)

    def save(self) -> bool:
        self._save_timer = None
        if not self._dirty:
            self.set_status(self.i18n("common.saved"))
            return True
        text = self.editor.get("1.0", "end-1c")
        try:
            size = self.store.save(text)
        except (NoteStorageError, OSError, TypeError):
            self.set_status(self.i18n("notes.save_failed"), error=True)
            return False
        self._dirty = False
        self.set_status(self.i18n("notes.saved_bytes", {"size": size}))
        return True

    def submit(self) -> bool:
        """Save an explicit user submission and dismiss the touch IME."""

        saved = self.save()
        if saved:
            self.request_input_method_hide()
        return saved

    def _submit_shortcut(self, _event: object = None) -> str:
        self.submit()
        return "break"

    def clear(self) -> None:
        if not messagebox.askyesno(
            self.i18n("notes.clear_title"),
            self.i18n("notes.clear_question"),
            parent=self.root,
        ):
            return
        self.editor.delete("1.0", "end")
        self.editor.edit_modified(False)
        self._dirty = True
        self.save()

    def close(self) -> None:
        if self.closed:
            return
        if self._save_timer is not None:
            self.root.after_cancel(self._save_timer)
            self._save_timer = None
        if self._dirty and not self.save():
            if not messagebox.askyesno(
                self.i18n("notes.close_title"),
                self.i18n("notes.close_question"),
                parent=self.root,
            ):
                return
        super().close()


def main() -> int:
    return NotesApplication().run()
