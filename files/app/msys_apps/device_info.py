"""UI-independent device information aggregation over mIPC only."""

from __future__ import annotations

from typing import Any, Protocol

from .ipc import MipcError, MipcRemoteError


HAL_MANAGER = "interface:org.msys.hal.manager.v1"


class RpcClient(Protocol):
    def call(
        self,
        target: str,
        method: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
        idempotent: bool = False,
    ) -> dict[str, Any]: ...


def _failure(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, MipcRemoteError):
        return {
            "available": False,
            "code": exc.code,
            "message": exc.message,
            "details": exc.payload,
        }
    code = exc.code if isinstance(exc, MipcError) else "UNAVAILABLE"
    return {
        "available": False,
        "code": code,
        "message": str(exc),
    }


def _safe_call(
    client: RpcClient,
    target: str,
    method: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = client.call(
            target,
            method,
            payload,
            timeout=6.0,
            idempotent=True,
        )
    except (MipcError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
        return _failure(exc)
    return {"available": True, "data": response}


def collect_device_info(client: RpcClient) -> dict[str, Any]:
    """Query only core and HAL; each unavailable section degrades separately."""

    core_sections = {
        "components": _safe_call(client, "msys.core", "list_components", {}),
        "roles": _safe_call(client, "msys.core", "list_roles", {}),
        "isolation": _safe_call(
            client,
            "msys.core",
            "isolation_capabilities",
            {},
        ),
    }
    core_available = any(section["available"] for section in core_sections.values())
    hal = _safe_call(client, HAL_MANAGER, "inventory", {"refresh": True})
    return {
        "schema": "org.msys.apps.device-info.v1",
        "core": {
            "available": core_available,
            "sections": core_sections,
        },
        "hal": hal,
    }

