"""Small application-local facade for the shared MSYS i18n contract."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

try:  # The release build overlays msys_sdk into files/app.
    from msys_sdk import CatalogError, Translator
except (ImportError, ModuleNotFoundError):  # pragma: no cover - recovery path
    CatalogError = ValueError  # type: ignore[assignment,misc]
    Translator = None  # type: ignore[assignment,misc]


ENGLISH_FALLBACK: dict[str, str] = {
    "package.name": "MSYS Everyday Apps",
    "package.summary": "Touch-friendly everyday applications",
    "notes.name": "Notes",
    "notes.summary": "A touch-friendly persistent note",
    "calculator.name": "Calculator",
    "calculator.summary": "A safe touch calculator",
    "device.name": "Device info",
    "device.summary_short": "System and hardware status",
    "common.ready": "Ready",
    "common.standalone": "Standalone",
    "common.save": "Save",
    "common.clear": "Clear",
    "common.refresh": "Refresh",
    "common.loaded": "Loaded",
    "common.saved": "Saved",
    "common.unsaved": "Unsaved",
    "common.available": "Available",
    "common.unavailable": "Unavailable",
    "common.yes": "Yes",
    "common.no": "No",
    "common.not_reported": "Not reported",
    "common.connection_failed": "Unable to connect to MSYS services",
    "state.ready": "Ready",
    "state.starting": "Starting",
    "state.stopped": "Stopped",
    "state.failed": "Failed",
    "state.manual": "Manual",
    "state.background": "Background",
    "state.on_demand": "On demand",
    "state.never": "Never",
    "state.on_failure": "On failure",
    "state.automatic": "Automatic",
    "state.degraded": "Degraded",
    "state.optional_helper": "Optional helper",
    "state.deferred_to_child": "Checked when the component starts",
    "state.partial_isolation": "Partial isolation (not a filesystem sandbox)",
    "calculator.title": "Calculator",
    "calculator.window_title": "MSYS Calculator",
    "calculator.result": "Result",
    "calculator.invalid": "Invalid expression",
    "notes.title": "Notes",
    "notes.window_title": "MSYS Notes",
    "notes.saved_bytes": "Saved · {size} B",
    "notes.clear_title": "Clear note",
    "notes.clear_question": "Delete all text in this note?",
    "notes.close_title": "Note not saved",
    "notes.close_question": "The note could not be saved. Close anyway?",
    "notes.load_failed": "The note could not be loaded",
    "notes.save_failed": "The note could not be saved",
    "device.title": "Device info",
    "device.window_title": "MSYS Device Info",
    "device.not_loaded": "Not loaded",
    "device.reading": "Reading…",
    "device.summary": "{ready}/{total} ready · {devices} HAL devices",
    "device.hal_unavailable": "{ready}/{total} ready · HAL unavailable",
    "device.updated": "Updated",
    "device.services_unavailable": "MSYS services unavailable",
    "device.section.components": "Components",
    "device.section.roles": "System roles",
    "device.section.isolation": "Process isolation",
    "device.section.hardware": "Hardware and HAL",
    "device.no_details": "No diagnostic details were reported",
    "device.unnamed": "Unnamed item",
    "device.empty": "Nothing reported",
    "device.reason.no_provider": "No provider is installed",
    "device.reason.provider_failed": "The selected provider failed",
    "device.domain.power": "Power",
    "device.domain.display": "Display",
    "device.domain.input": "Input",
    "device.domain.network": "Network",
    "device.domain.bluetooth": "Bluetooth",
    "device.domain.thermal": "Thermal",
    "device.domain.storage": "Storage",
    "device.field.linux": "Linux isolation support",
    "device.field.no_new_privs": "Privilege escalation blocked",
    "device.field.dumpable": "Process dump control",
    "device.field.unshare_api": "Namespace API",
    "device.field.namespaces": "Namespaces",
    "device.field.rlimits": "Resource limits",
    "device.field.seccomp": "System-call filtering",
    "device.field.permission_probe": "Permission check",
    "device.field.security_boundary": "Security boundary",
}


class AppsI18n:
    """Use :class:`msys_sdk.Translator` while retaining a recovery UI."""

    def __init__(
        self,
        catalog_path: str | os.PathLike[str] | None = None,
        *,
        locale: str | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.catalog_path = Path(catalog_path) if catalog_path else default_catalog_path()
        self.load_error = ""
        self._translator: Any = None
        if Translator is not None:
            try:
                self._translator = Translator.from_file(
                    self.catalog_path,
                    locale,
                    environ=environ,
                )
            except (CatalogError, OSError, UnicodeError, ValueError) as exc:
                self.load_error = str(exc)

    @property
    def locale(self) -> str:
        if self._translator is None:
            return "en-US"
        return str(self._translator.resolved_locale)

    @property
    def fallback_chain(self) -> tuple[str, ...]:
        if self._translator is None:
            return ("en-US",)
        return tuple(str(item) for item in self._translator.fallback_chain)

    def set_locale(
        self,
        locale: str | None,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> str:
        if self._translator is None:
            return "en-US"
        return str(self._translator.set_locale(locale, environ=environ))

    def text(
        self,
        key: str,
        params: Mapping[str, object] | None = None,
        *,
        fallback: str | None = None,
    ) -> str:
        english = fallback if fallback is not None else ENGLISH_FALLBACK.get(key, key)
        if self._translator is not None:
            return str(self._translator.text(key, params, fallback=english))
        return _render_fallback(english, params)

    __call__ = text


def default_catalog_path() -> Path:
    configured = os.environ.get("MSYS_I18N_CATALOG")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "share" / "i18n" / "catalog.json"


def _render_fallback(
    template: str,
    params: Mapping[str, object] | None,
) -> str:
    rendered = template
    for key, value in (params or {}).items():
        if isinstance(value, str) or (
            isinstance(value, int) and not isinstance(value, bool)
        ):
            rendered = rendered.replace("{" + str(key) + "}", str(value))
    return rendered


__all__ = ["AppsI18n", "ENGLISH_FALLBACK", "default_catalog_path"]
