from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from msys_apps.localization import AppsI18n, ENGLISH_FALLBACK, default_catalog_path


class LocalizationTests(unittest.TestCase):
    def test_catalog_has_complete_english_and_chinese_key_sets(self) -> None:
        document = json.loads(default_catalog_path().read_text(encoding="utf-8"))
        self.assertEqual(document["schema"], "msys.i18n.catalog.v1")
        messages = document["messages"]
        self.assertEqual(set(messages["en-US"]), set(messages["zh-CN"]))
        self.assertEqual(set(messages["en-US"]), set(messages["zh"]))
        self.assertEqual(messages["zh"], messages["zh-CN"])
        self.assertEqual(set(messages["en-US"]), set(ENGLISH_FALLBACK))

    def test_english_recovery_formats_only_safe_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing.json"
            i18n = AppsI18n(missing, locale="zh-CN")
        self.assertEqual(
            i18n("notes.saved_bytes", {"size": 12}),
            "Saved · 12 B",
        )
        self.assertEqual(
            i18n("notes.saved_bytes", {"size": True}),
            "Saved · {size} B",
        )

    def test_shared_translator_selects_chinese_when_available(self) -> None:
        i18n = AppsI18n(locale="zh_CN.UTF-8")
        if i18n.load_error or i18n.locale == "en-US":
            self.skipTest("msys_sdk source overlay is not on PYTHONPATH")
        self.assertEqual(i18n("common.save"), "保存")
        self.assertEqual(
            i18n("device.summary", {"ready": 2, "total": 3, "devices": 1}),
            "2/3 个组件就绪 · 1 个 HAL 设备",
        )
        self.assertEqual(i18n("device.field.no_new_privs"), "禁止提升权限")
        self.assertEqual(i18n("notes.save_failed"), "无法保存便笺")

    def test_locale_switch_and_parent_fallback_use_the_shared_contract(self) -> None:
        i18n = AppsI18n(locale="zh_CN.UTF-8")
        self.assertEqual(i18n.locale, "zh-CN")
        self.assertEqual(i18n.fallback_chain, ("zh-CN", "zh", "en-US"))
        self.assertEqual(i18n.set_locale("en_GB"), "en-US")
        self.assertEqual(i18n.fallback_chain, ("en-US",))

    def test_locale_environment_priority_is_consistent(self) -> None:
        i18n = AppsI18n(
            environ={
                "MSYS_LOCALE": "zh_CN.UTF-8",
                "LC_ALL": "en_US.UTF-8",
            }
        )
        self.assertEqual(i18n.locale, "zh-CN")
        self.assertEqual(i18n("common.save"), "保存")

    def test_script_locale_uses_generic_chinese_parent_not_english(self) -> None:
        i18n = AppsI18n(locale="zh_Hans_CN.UTF-8")
        self.assertEqual(i18n.locale, "zh")
        self.assertEqual(i18n.fallback_chain, ("zh", "en-US"))
        self.assertEqual(i18n("common.save"), "保存")


if __name__ == "__main__":
    unittest.main()
