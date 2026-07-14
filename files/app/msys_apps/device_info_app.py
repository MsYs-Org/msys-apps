"""Touch Device Info UI; all device data arrives through mIPC."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Any

from .common_ui import TouchApplication
from .device_info import collect_device_info
from .ipc import PublicMipcClient
from .localization import AppsI18n


class DeviceInfoApplication(TouchApplication):
    VALUE_LABELS = {
        "ready": "state.ready",
        "starting": "state.starting",
        "stopped": "state.stopped",
        "failed": "state.failed",
        "available": "common.available",
        "unavailable": "common.unavailable",
        "manual": "state.manual",
        "background": "state.background",
        "on-demand": "state.on_demand",
        "never": "state.never",
        "on-failure": "state.on_failure",
        "automatic": "state.automatic",
        "degraded": "state.degraded",
        "optional-helper": "state.optional_helper",
        "deferred-to-child": "state.deferred_to_child",
        "partial-not-a-filesystem-sandbox": "state.partial_isolation",
        "no-provider": "device.reason.no_provider",
        "provider-failed": "device.reason.provider_failed",
        "power": "device.domain.power",
        "display": "device.domain.display",
        "input": "device.domain.input",
        "network": "device.domain.network",
        "bluetooth": "device.domain.bluetooth",
        "thermal": "device.domain.thermal",
        "storage": "device.domain.storage",
    }
    FIELD_LABELS = {
        "linux": "device.field.linux",
        "no_new_privs": "device.field.no_new_privs",
        "dumpable": "device.field.dumpable",
        "unshare_api": "device.field.unshare_api",
        "namespaces": "device.field.namespaces",
        "rlimits": "device.field.rlimits",
        "seccomp": "device.field.seccomp",
        "permission_probe": "device.field.permission_probe",
        "security_boundary": "device.field.security_boundary",
    }

    def __init__(self) -> None:
        i18n = AppsI18n()
        super().__init__(
            title=i18n("device.window_title"),
            identity="org.msys.apps.device-info",
            icon_name="device-info.ppm",
            i18n=i18n,
        )
        self.client = PublicMipcClient()
        self._refresh_generation = 0
        self._refreshing = False

        header = self.header(self.i18n("device.title"))
        self.refresh_button = ttk.Button(
            header,
            text=self.i18n("common.refresh"),
            style="Accent.TButton",
            command=self.refresh,
        )
        self.refresh_button.pack(side="right")
        self.summary = tk.StringVar(value=self.i18n("device.not_loaded"))
        self.page = self.scroll_page()
        summary_label = ttk.Label(
            self.page.content,
            textvariable=self.summary,
            style="Muted.TLabel",
            anchor="w",
            justify="left",
            padding=(2, 0, 2, 8),
        )
        summary_label.pack(fill="x")
        self.bind_wrap(summary_label, self.page.canvas, horizontal_padding=24)
        self.cards = self.card_grid(self.page.content)
        self.page.bind_touch_scroll(self.page.content)
        private_client = self.activate_lifecycle()
        if private_client is not None:
            self.client = private_client
        self.refresh()

    def refresh(self) -> None:
        if self._refreshing or self.closed:
            return
        self._refreshing = True
        self._refresh_generation += 1
        generation = self._refresh_generation
        self.refresh_button.configure(state="disabled")
        self.set_status(self.i18n("device.reading"))

        def worker() -> None:
            data = collect_device_info(self.client)
            self.post("device-info", (generation, data))

        threading.Thread(target=worker, name="device-info-rpc", daemon=True).start()

    def handle_message(self, kind: str, payload: Any) -> None:
        if kind != "device-info" or not isinstance(payload, tuple) or len(payload) != 2:
            return
        generation, data = payload
        if generation != self._refresh_generation or not isinstance(data, dict):
            return
        self._refreshing = False
        self.refresh_button.configure(state="normal")
        self._replace(data)
        self._summarise(data)

    def _replace(self, data: dict[str, Any]) -> None:
        self.cards.clear()
        core = data.get("core", {})
        sections = core.get("sections", {}) if isinstance(core, dict) else {}
        for key, title_key in (
            ("components", "device.section.components"),
            ("roles", "device.section.roles"),
            ("isolation", "device.section.isolation"),
        ):
            raw = sections.get(key, {}) if isinstance(sections, dict) else {}
            available = bool(isinstance(raw, dict) and raw.get("available"))
            payload = raw.get("data", {}) if available and isinstance(raw, dict) else {}
            rows = self._section_rows(key, payload) if available else self._error_rows(raw)
            card = self.info_card(
                self.cards,
                title=self.i18n(title_key),
                items=rows,
                available=available,
                status=self.i18n("common.available" if available else "common.unavailable"),
            )
            self.cards.add(card)
            self.page.bind_touch_scroll(card)

        hal = data.get("hal", {})
        hal_available = bool(isinstance(hal, dict) and hal.get("available"))
        hal_payload = hal.get("data", {}) if hal_available and isinstance(hal, dict) else {}
        hal_rows = self._section_rows("hal", hal_payload) if hal_available else self._error_rows(hal)
        hal_card = self.info_card(
            self.cards,
            title=self.i18n("device.section.hardware"),
            items=hal_rows,
            available=hal_available,
            status=self.i18n("common.available" if hal_available else "common.unavailable"),
        )
        self.cards.add(hal_card)
        self.page.bind_touch_scroll(hal_card)
        self.page.refresh()

    def _error_rows(self, section: object) -> list[tuple[str, str]]:
        raw = section if isinstance(section, dict) else {}
        code = str(raw.get("code") or "UNAVAILABLE")
        message = str(raw.get("message") or self.i18n("device.no_details"))
        return [(code, message[:512])]

    def _section_rows(
        self,
        section: str,
        payload: object,
    ) -> list[tuple[str, str]]:
        raw = payload if isinstance(payload, dict) else {}
        rows: list[tuple[str, str]] = []
        if section == "components":
            values = raw.get("components", [])
            for item in values[:64] if isinstance(values, list) else ():
                if not isinstance(item, dict):
                    continue
                rows.append((
                    str(item.get("id") or self.i18n("device.unnamed")),
                    self._join(item.get("state"), item.get("lifecycle"), item.get("restart")),
                ))
        elif section == "roles":
            values = raw.get("roles", [])
            for item in values[:64] if isinstance(values, list) else ():
                if not isinstance(item, dict):
                    continue
                rows.append((
                    str(item.get("role") or item.get("id") or self.i18n("device.unnamed")),
                    self._join(
                        item.get("active"),
                        item.get("provider"),
                        item.get("component"),
                    ),
                ))
        elif section == "hal":
            domains = raw.get("domains", [])
            for item in domains[:32] if isinstance(domains, list) else ():
                if not isinstance(item, dict):
                    continue
                rows.append((
                    self._display_value(
                        item.get("domain") or self.i18n("device.unnamed")
                    ),
                    self._join(item.get("status"), item.get("provider"), item.get("reason")),
                ))
            devices = raw.get("devices", [])
            for item in devices[:48] if isinstance(devices, list) else ():
                if not isinstance(item, dict):
                    continue
                rows.append((
                    str(item.get("name") or item.get("id") or self.i18n("device.unnamed")),
                    self._join(item.get("domain"), item.get("status"), item.get("provider")),
                ))
        else:
            for key, value in list(raw.items())[:48]:
                label_key = self.FIELD_LABELS.get(str(key))
                rows.append((
                    self.i18n(label_key) if label_key else str(key),
                    self._display_value(value),
                ))
        return rows or [(self.i18n("device.empty"), "")]

    def _join(self, *values: object) -> str:
        return " · ".join(
            self._display_value(value)
            for value in values
            if value is not None and value != ""
        )[:512]

    def _display_value(self, value: object) -> str:
        if isinstance(value, bool):
            return self.i18n("common.yes" if value else "common.no")
        if value is None:
            return self.i18n("common.not_reported")
        if isinstance(value, str):
            key = self.VALUE_LABELS.get(value.strip().lower())
            return self.i18n(key) if key else value[:512]
        if isinstance(value, (int, float)):
            return str(value)[:512]
        if isinstance(value, list):
            return ", ".join(self._display_value(item) for item in value[:16])[:512]
        if isinstance(value, dict):
            return " · ".join(
                f"{self.i18n(self.FIELD_LABELS[str(key)]) if str(key) in self.FIELD_LABELS else key}: "
                f"{self._display_value(item)}"
                for key, item in list(value.items())[:16]
            )[:512]
        return str(value)[:512]

    def _summarise(self, data: dict[str, Any]) -> None:
        core = data.get("core", {})
        sections = core.get("sections", {}) if isinstance(core, dict) else {}
        component_section = sections.get("components", {}) if isinstance(sections, dict) else {}
        component_data = component_section.get("data", {}) if isinstance(component_section, dict) else {}
        components = component_data.get("components", []) if isinstance(component_data, dict) else []
        ready = sum(
            1
            for component in components
            if isinstance(component, dict) and component.get("state") == "ready"
        )
        hal = data.get("hal", {})
        hal_data = hal.get("data", {}) if isinstance(hal, dict) else {}
        devices = hal_data.get("devices", []) if isinstance(hal_data, dict) else []
        hal_available = bool(isinstance(hal, dict) and hal.get("available"))
        summary_key = "device.summary" if hal_available else "device.hal_unavailable"
        self.summary.set(self.i18n(summary_key, {
            "ready": ready,
            "total": len(components),
            "devices": len(devices),
        }))
        if bool(isinstance(core, dict) and core.get("available")) or hal_available:
            self.set_status(self.i18n("device.updated"))
        else:
            self.set_status(self.i18n("device.services_unavailable"), error=True)

    def close(self) -> None:
        self._refresh_generation += 1
        super().close()


def main() -> int:
    return DeviceInfoApplication().run()
