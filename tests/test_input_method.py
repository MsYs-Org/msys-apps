from __future__ import annotations

import threading
import types
import unittest
from unittest import mock

from msys_sdk import tk_app as sdk_tk_app
from msys_apps.common_ui import (
    INPUT_METHOD_FOCUS_SETTLE_MS,
    INPUT_METHOD_HIDE_TIMEOUT,
    INPUT_METHOD_SHOW_TIMEOUT,
    TouchApplication,
)
from msys_apps.notes_app import NotesApplication


class InlineThread:
    def __init__(self, *, target, **_kwargs) -> None:
        self.target = target

    def start(self) -> None:
        self.target()


class FakeRoot:
    def __init__(self) -> None:
        self.bindings = {}
        self.scheduled = {}
        self.cancelled = []
        self.focused = None
        self.destroyed = False
        self._next_after = 1

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback
        return add

    def after(self, delay, callback):
        handle = f"after-{self._next_after}"
        self._next_after += 1
        self.scheduled[handle] = (delay, callback)
        return handle

    def after_idle(self, callback):
        callback()
        return "idle"

    def after_cancel(self, handle):
        self.cancelled.append(handle)
        self.scheduled.pop(handle, None)

    def focus_get(self):
        return self.focused

    def run_scheduled(self) -> None:
        pending = list(self.scheduled.values())
        self.scheduled.clear()
        for _delay, callback in pending:
            callback()

    def destroy(self) -> None:
        self.destroyed = True


class FakeWidget:
    def __init__(self, master) -> None:
        self.master = master
        self.bindings = {}

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback
        return add


class FakeChannel:
    def __init__(self) -> None:
        self.calls = []
        self.handshakes = 0
        self.callbacks = []
        self.closed = False

    def handshake(self) -> None:
        self.handshakes += 1

    def start(self, callback) -> None:
        self.callbacks.append(callback)

    def call(self, target, method, payload, *, timeout):
        self.calls.append((target, method, payload, timeout))
        return {"ok": True}

    def close(self) -> None:
        self.closed = True


def application(channel: FakeChannel | None = None) -> TouchApplication:
    app = object.__new__(TouchApplication)
    app.root = FakeRoot()
    app.closed = False
    app._channel = channel
    app._input_widgets = {}
    app._input_root_bound = False
    app._input_lock = threading.Lock()
    app._input_pending = None
    app._input_desired = None
    app._input_worker_running = False
    app._input_focus_check = None
    app._wrap_bindings = []
    return app


@mock.patch("msys_sdk.tk_app.threading.Thread", InlineThread)
class InputMethodBindingTests(unittest.TestCase):
    def test_real_touches_reassert_show_and_non_editor_touch_hides(self) -> None:
        channel = FakeChannel()
        app = application(channel)
        editor = FakeWidget(app.root)
        outside = FakeWidget(app.root)
        app.attach_input_method(editor, mode="zh")

        editor.bindings["<ButtonPress-1>"](types.SimpleNamespace(widget=editor))
        editor.bindings["<FocusIn>"](types.SimpleNamespace(widget=editor))
        self.assertEqual(
            channel.calls,
            [
                (
                    "role:input-method",
                    "show",
                    {"mode": "zh"},
                    INPUT_METHOD_SHOW_TIMEOUT,
                )
            ],
        )

        # Once the prior request is complete, a new real touch must wake a
        # provider that may have dismissed itself while focus stayed in Notes.
        editor.bindings["<ButtonPress-1>"](types.SimpleNamespace(widget=editor))
        self.assertEqual([item[1] for item in channel.calls], ["show", "show"])

        app.root.bindings["<ButtonPress-1>"](
            types.SimpleNamespace(widget=outside)
        )
        self.assertEqual(
            channel.calls[-1],
            ("role:input-method", "hide", {}, INPUT_METHOD_HIDE_TIMEOUT),
        )

    def test_focus_jitter_is_debounced_but_real_focus_loss_hides(self) -> None:
        channel = FakeChannel()
        app = application(channel)
        editor = FakeWidget(app.root)
        app.attach_input_method(editor)
        app.root.focused = editor
        editor.bindings["<FocusIn>"](types.SimpleNamespace(widget=editor))

        editor.bindings["<FocusOut>"](types.SimpleNamespace(widget=editor))
        pending = app._input_focus_check
        self.assertIsNotNone(pending)
        self.assertEqual(
            app.root.scheduled[pending][0],
            INPUT_METHOD_FOCUS_SETTLE_MS,
        )
        editor.bindings["<FocusIn>"](types.SimpleNamespace(widget=editor))
        self.assertIn(pending, app.root.cancelled)
        app.root.run_scheduled()
        self.assertEqual([item[1] for item in channel.calls], ["show"])

        app.root.focused = None
        editor.bindings["<FocusOut>"](types.SimpleNamespace(widget=editor))
        app.root.run_scheduled()
        self.assertEqual([item[1] for item in channel.calls], ["show", "hide"])

    def test_handshake_reconciles_editor_focused_before_channel_exists(self) -> None:
        channel = FakeChannel()
        app = application()
        editor = FakeWidget(app.root)
        app.attach_input_method(editor, mode="numeric")
        app.root.focused = editor

        with mock.patch.object(
            sdk_tk_app.ComponentChannel,
            "from_environment",
            return_value=channel,
        ):
            self.assertIs(app.activate_lifecycle(), channel)

        self.assertEqual(channel.handshakes, 1)
        self.assertEqual(len(channel.callbacks), 1)
        self.assertEqual(
            channel.calls,
            [
                (
                    "role:input-method",
                    "show",
                    {"mode": "numeric"},
                    INPUT_METHOD_SHOW_TIMEOUT,
                )
            ],
        )

    def test_close_orders_hide_before_channel_close(self) -> None:
        channel = FakeChannel()
        app = application(channel)
        app._input_desired = (True, "zh")

        app.close()

        self.assertEqual(
            channel.calls,
            [("role:input-method", "hide", {}, INPUT_METHOD_HIDE_TIMEOUT)],
        )
        self.assertTrue(channel.closed)
        self.assertTrue(app.root.destroyed)


class NotesSubmissionTests(unittest.TestCase):
    def test_successful_explicit_submit_hides_but_failed_save_does_not(self) -> None:
        notes = object.__new__(NotesApplication)
        notes.save = mock.Mock(return_value=True)
        notes.request_input_method_hide = mock.Mock()
        self.assertTrue(notes.submit())
        notes.request_input_method_hide.assert_called_once_with()

        notes.save = mock.Mock(return_value=False)
        notes.request_input_method_hide.reset_mock()
        self.assertFalse(notes.submit())
        notes.request_input_method_hide.assert_not_called()

    def test_submit_shortcut_consumes_the_key_event(self) -> None:
        notes = object.__new__(NotesApplication)
        notes.submit = mock.Mock(return_value=True)
        self.assertEqual(notes._submit_shortcut(), "break")
        notes.submit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
