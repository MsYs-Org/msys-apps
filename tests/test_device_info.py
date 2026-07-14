from __future__ import annotations

import unittest

from msys_apps.device_info import HAL_MANAGER, collect_device_info
from msys_apps.ipc import MipcRemoteError, MipcUnavailable


class FakeRpc:
    def __init__(self, *, hal_missing: bool = False, all_missing: bool = False) -> None:
        self.hal_missing = hal_missing
        self.all_missing = all_missing
        self.calls: list[tuple[str, str, dict, dict]] = []

    def call(self, target, method, payload=None, **options):
        self.calls.append((target, method, payload or {}, options))
        if self.all_missing:
            raise MipcUnavailable("control socket missing")
        if target == HAL_MANAGER:
            if self.hal_missing:
                raise MipcRemoteError(
                    "NO_PROVIDER",
                    "HAL manager is not installed",
                    {"interface": "org.msys.hal.manager.v1"},
                )
            return {
                "domains": [{"domain": "power", "status": "unavailable"}],
                "devices": [],
            }
        if method == "list_components":
            return {"components": [{"id": "org.msys.apps:device-info", "state": "ready"}]}
        if method == "list_roles":
            return {"roles": []}
        return {"no_new_privs": True}


class DeviceInfoTests(unittest.TestCase):
    def test_queries_only_core_and_hal_read_interfaces(self) -> None:
        rpc = FakeRpc()
        result = collect_device_info(rpc)
        self.assertTrue(result["core"]["available"])
        self.assertTrue(result["hal"]["available"])
        self.assertEqual(
            [(target, method) for target, method, _payload, _options in rpc.calls],
            [
                ("msys.core", "list_components"),
                ("msys.core", "list_roles"),
                ("msys.core", "isolation_capabilities"),
                (HAL_MANAGER, "inventory"),
            ],
        )
        self.assertTrue(all(options["idempotent"] for *_, options in rpc.calls))
        self.assertEqual(rpc.calls[-1][2], {"refresh": True})

    def test_missing_hal_is_a_structured_degraded_section(self) -> None:
        result = collect_device_info(FakeRpc(hal_missing=True))
        self.assertTrue(result["core"]["available"])
        self.assertFalse(result["hal"]["available"])
        self.assertEqual(result["hal"]["code"], "NO_PROVIDER")
        self.assertEqual(
            result["hal"]["details"]["interface"],
            "org.msys.hal.manager.v1",
        )

    def test_missing_control_socket_degrades_every_section(self) -> None:
        result = collect_device_info(FakeRpc(all_missing=True))
        self.assertFalse(result["core"]["available"])
        self.assertFalse(result["hal"]["available"])
        self.assertEqual(result["hal"]["code"], "IPC_UNAVAILABLE")
        self.assertTrue(
            all(
                not section["available"]
                for section in result["core"]["sections"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()

