from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from msys_apps import __version__


ROOT = Path(__file__).resolve().parents[1]


def read_ppm(path: Path) -> tuple[int, int, list[int]]:
    data = path.read_bytes()
    offset = 0

    def token() -> bytes:
        nonlocal offset
        while True:
            while offset < len(data) and data[offset] in b" \t\r\n":
                offset += 1
            if offset < len(data) and data[offset] == ord("#"):
                newline = data.find(b"\n", offset)
                if newline < 0:
                    raise ValueError("unterminated PPM comment")
                offset = newline + 1
                continue
            break
        start = offset
        while offset < len(data) and data[offset] not in b" \t\r\n#":
            offset += 1
        if start == offset:
            raise ValueError("truncated PPM header")
        return data[start:offset]

    if token() != b"P6":
        raise ValueError("not a Tk-compatible binary PPM")
    width, height, maximum = (int(token()), int(token()), int(token()))
    if maximum != 255:
        raise ValueError("unexpected PPM maximum")
    if offset >= len(data) or data[offset] not in b" \t\r\n":
        raise ValueError("PPM header has no raster delimiter")
    offset += 1
    return width, height, list(data[offset:])


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_package_version_and_three_launchable_components(self) -> None:
        self.assertEqual(self.manifest["schema"], "msys.manifest.v1")
        package = self.manifest["package"]
        self.assertEqual(package["id"], "org.msys.apps")
        self.assertEqual(__version__, "0.1.11")
        self.assertEqual(package["version"], __version__)
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertEqual(
            re.search(r'(?m)^version\s*=\s*"([^"]+)"', project).group(1),
            __version__,
        )
        self.assertEqual(
            {item["id"] for item in self.manifest["components"]},
            {"notes", "calculator", "device-info"},
        )

    def test_components_are_isolated_inherited_x11_apps(self) -> None:
        identities: set[str] = set()
        for component in self.manifest["components"]:
            with self.subTest(component=component["id"]):
                self.assertEqual(component["runtime"], "tk")
                self.assertEqual(component["lifecycle"], "manual")
                self.assertEqual(component["restart"], "never")
                self.assertEqual(component["isolation"], "baseline")
                self.assertEqual(component["readiness"]["mode"], "mipc-ready")
                self.assertTrue(component["activation"]["launchable"])
                self.assertNotIn("DISPLAY", component.get("env", {}))
                self.assertNotIn("PYTHONPATH", component.get("env", {}))
                self.assertEqual(component["windowing"]["display"], "inherit")
                identity = component["windowing"]["identity"]
                self.assertEqual(identity["app_id"], identity["x11_wm_class"])
                self.assertNotIn(identity["app_id"], identities)
                identities.add(identity["app_id"])
                entry = component["exec"][1].removeprefix("@package/")
                self.assertTrue((ROOT / entry).is_file())

    def test_package_and_component_icons_are_real_ppm_images(self) -> None:
        icon_paths = [self.manifest["package"]["icons"][0]["path"]]
        icon_paths.extend(
            item["icons"][0]["path"] for item in self.manifest["components"]
        )
        self.assertEqual(len(set(icon_paths)), 4)
        for relative in icon_paths:
            with self.subTest(icon=relative):
                width, height, pixels = read_ppm(ROOT / relative)
                self.assertEqual((width, height), (32, 32))
                self.assertEqual(len(pixels), width * height * 3)
                self.assertTrue(all(0 <= value <= 255 for value in pixels))
                self.assertGreater(len(set(zip(pixels[0::3], pixels[1::3], pixels[2::3]))), 2)

    def test_launcher_i18n_metadata_resolves_inside_the_package_catalog(self) -> None:
        catalog = json.loads(
            (ROOT / "files/share/i18n/catalog.json").read_text(encoding="utf-8")
        )
        english = catalog["messages"]["en-US"]
        declarations = [self.manifest["package"]["x-msys-i18n"]]
        declarations.extend(
            component["x-msys-i18n"] for component in self.manifest["components"]
        )
        for declaration in declarations:
            with self.subTest(name_key=declaration["name_key"]):
                path = ROOT / declaration["catalog"]
                self.assertEqual(path.resolve(), (ROOT / "files/share/i18n/catalog.json").resolve())
                self.assertIn(declaration["name_key"], english)
                self.assertIn(declaration["summary_key"], english)

    def test_calculator_source_never_invokes_python_eval(self) -> None:
        source = (ROOT / "files/app/msys_apps/calculator.py").read_text(encoding="utf-8")
        self.assertNotIn("eval(", source)
        self.assertNotIn("exec(", source)

    def test_device_info_model_contains_no_direct_host_probes(self) -> None:
        source = (ROOT / "files/app/msys_apps/device_info.py").read_text(encoding="utf-8")
        for forbidden in ("/proc", "/sys", "uname", "platform", "subprocess"):
            self.assertNotIn(forbidden, source)

    def test_no_forbidden_runtime_dependency_in_manifest(self) -> None:
        text = (ROOT / "manifest.json").read_text(encoding="utf-8").lower()
        for forbidden in ("systemd", "dbus", "apt", "pip"):
            self.assertNotIn(forbidden, text)

    def test_application_modules_do_not_import_system_implementations(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "files/app").rglob("*.py")
        ).lower()
        for forbidden in ("import msys_core", "import msys_hal", "import dbus"):
            self.assertNotIn(forbidden, sources)

    def test_notes_declares_replaceable_input_method_permission(self) -> None:
        notes = next(
            item for item in self.manifest["components"] if item["id"] == "notes"
        )
        self.assertEqual(
            set(notes["permissions"]),
            {
                "state:notes:read-write",
                "mipc.call:role:input-method",
            },
        )
        source = (ROOT / "files/app/msys_apps/notes_app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("self.attach_input_method(", source)
        self.assertNotIn("org.msys.input.touch", source)


if __name__ == "__main__":
    unittest.main()
