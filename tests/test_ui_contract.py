from __future__ import annotations

from pathlib import Path
import json
import re
from types import SimpleNamespace
import unittest

from msys_sdk import responsive_columns
from msys_apps.common_ui import TouchApplication


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "files" / "app" / "msys_apps"


class LegacyTkText:
    """Debian 11-compatible Text double with no Canvas-style gain arg."""

    def __init__(self) -> None:
        self.bindings = {}
        self.marks = []
        self.drags = []

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback
        return add

    def scan_mark(self, x, y) -> None:
        self.marks.append((x, y))

    def scan_dragto(self, x, y) -> None:
        self.drags.append((x, y))

    def yview_scroll(self, _units, _what) -> None:
        pass


class AppsUiContractTests(unittest.TestCase):
    def test_shared_responsive_layout_helpers_are_used_without_a_local_copy(self) -> None:
        self.assertFalse((PACKAGE / "ui_layout.py").exists())
        common = (PACKAGE / "common_ui.py").read_text(encoding="utf-8")
        self.assertIn("TkScrollablePage", common)
        self.assertIn("bind_tk_text_wrap", common)
        self.assertIn("responsive_columns", common)

    def test_every_window_uses_its_packaged_icon(self) -> None:
        common = (PACKAGE / "common_ui.py").read_text(encoding="utf-8")
        self.assertIn("tk.PhotoImage", common)
        self.assertIn("iconphoto", common)
        for name in ("notes", "calculator", "device-info"):
            source = (PACKAGE / f"{name.replace('-', '_')}_app.py").read_text(
                encoding="utf-8"
            )
            self.assertIn(f'icon_name="{name}.ppm"', source)

    def test_long_device_information_is_carded_and_touch_scrollable(self) -> None:
        source = (PACKAGE / "device_info_app.py").read_text(encoding="utf-8")
        self.assertIn("self.scroll_page(", source)
        self.assertIn("self.info_card(", source)
        self.assertNotIn("json.dumps", source)

    def test_portrait_and_landscape_card_layout_have_stable_breakpoints(self) -> None:
        common = (PACKAGE / "common_ui.py").read_text(encoding="utf-8")
        minimum = int(
            re.search(r"(?m)^CARD_MINIMUM_WIDTH = (\d+)$", common).group(1)
        )
        maximum = int(
            re.search(r"(?m)^CARD_MAXIMUM_COLUMNS = (\d+)$", common).group(1)
        )
        self.assertEqual(minimum, 210)
        self.assertEqual(maximum, 2)
        self.assertEqual(
            responsive_columns(
                300,
                minimum_item_width=minimum,
                gap=8,
                maximum=maximum,
            ),
            1,
        )
        self.assertEqual(
            responsive_columns(
                448,
                minimum_item_width=minimum,
                gap=8,
                maximum=maximum,
            ),
            2,
        )

    def test_notes_wraps_and_directly_scrolls_long_touch_content(self) -> None:
        source = (PACKAGE / "notes_app.py").read_text(encoding="utf-8")
        self.assertIn('wrap="word"', source)
        self.assertIn("self.bind_touch_text_scroll(self.editor)", source)
        common = (PACKAGE / "common_ui.py").read_text(encoding="utf-8")
        self.assertIn("widget.scan_dragto(0, current)", common)
        self.assertNotIn("scan_dragto(0, current, gain=", common)
        self.assertNotIn("bind_all(", common)

    def test_touch_drag_uses_the_debian11_text_scan_signature(self) -> None:
        widget = LegacyTkText()
        app = object.__new__(TouchApplication)
        app.bind_touch_text_scroll(widget, drag_threshold=8)

        widget.bindings["<ButtonPress-1>"](SimpleNamespace(y=100))
        self.assertIsNone(
            widget.bindings["<B1-Motion>"](SimpleNamespace(y=105))
        )
        self.assertEqual(widget.drags, [])
        self.assertEqual(
            widget.bindings["<B1-Motion>"](SimpleNamespace(y=112)),
            "break",
        )
        self.assertEqual(widget.marks, [(0, 100)])
        self.assertEqual(widget.drags, [(0, 112)])
        self.assertEqual(
            widget.bindings["<ButtonRelease-1>"](SimpleNamespace()),
            "break",
        )

    def test_calculator_compacts_landscape_and_scrolls_long_expressions(self) -> None:
        source = (PACKAGE / "calculator_app.py").read_text(encoding="utf-8")
        self.assertIn("winfo_screenheight() <= 360", source)
        self.assertIn('self.display.xview_moveto(1.0)', source)
        self.assertIn("ACCENT_CONTAINER", source)

    def test_device_info_uses_canonical_sdk_identity_and_owns_localized_title(self) -> None:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        device = next(
            item for item in manifest["components"] if item["id"] == "device-info"
        )
        identity = device["windowing"]["identity"]
        self.assertEqual(identity["app_id"], "org.msys.apps.device-info")
        self.assertEqual(identity["x11_wm_class"], identity["app_id"])
        self.assertEqual(identity["x11_wm_instance"], "device-info")

        common = (PACKAGE / "common_ui.py").read_text(encoding="utf-8")
        device_source = (PACKAGE / "device_info_app.py").read_text(encoding="utf-8")
        self.assertIn("configure_tk_window_identity", common)
        self.assertIn("self.root.title(title)", common)
        self.assertIn('title=i18n("device.window_title")', device_source)
        self.assertIn('identity="org.msys.apps.device-info"', device_source)


if __name__ == "__main__":
    unittest.main()
