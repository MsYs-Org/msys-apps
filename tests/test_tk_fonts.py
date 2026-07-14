from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "files/app/msys_apps"


class TkFontIntegrationTests(unittest.TestCase):
    def test_apps_use_the_sdk_policy_without_a_local_copy(self) -> None:
        self.assertFalse((PACKAGE / "tk_fonts.py").exists())
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")
        )
        self.assertIn(
            "from msys_sdk.ui_fonts import configure_tk_fonts, font_spec",
            source,
        )
        self.assertGreaterEqual(
            source.count("from msys_sdk.ui_fonts import font_spec"),
            2,
        )
        self.assertNotIn('font=("Sans",', source)

    def test_release_build_vendors_the_sdk_beside_the_entrypoints(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "msys-sdk/msys_sdk=files/app/msys_sdk",
            readme.replace("/mnt/g/Code/MsYs/", ""),
        )


if __name__ == "__main__":
    unittest.main()
