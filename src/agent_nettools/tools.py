"""The get_device_status tool. Contract: docs/get_device_status.yml"""

import time

from agent_nettools.audit import utc_now, write_record
from agent_nettools.eapi import EapiError, run_commands
from agent_nettools.inventory import is_approved
from agent_nettools.topology import resolve_address

COMMANDS = ["show hostname", "show version"]


class ToolError(Exception):
    """Raised when the tool cannot return a trustworthy result."""

    def __init__(self, reason: str, detail: str):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}")


def get_device_status(device: str, caller: str = "cli") -> dict:
    """Return the identity of the requested device as the device itself reports it."""
    started = time.monotonic()

    record = {
        "timestamp": utc_now(),
        "tool": "get_device_status",
        "caller": caller,
        "requested_device": device,
        "approved": False,
        "target_address": None,
        "command_sent": None,
        "outcome": None,
        "blocked_reason": None,
        "detail": None,
        "duration_ms": None,
    }

    try:
        if not is_approved(device):
            raise ToolError("not_approved", f"{device} is not in the approved device list")

        record["approved"] = True

        try:
            address = resolve_address(device)
        except LookupError as exc:
            raise ToolError("not_in_topology", str(exc)) from exc
        except ValueError as exc:
            raise ToolError("wrong_kind", str(exc)) from exc

        record["target_address"] = address
        record["command_sent"] = COMMANDS

        try:
            hostname_result, version_result = run_commands(address, COMMANDS)
        except EapiError as exc:
            raise ToolError(exc.reason, exc.detail) from exc

        reported = hostname_result.get("hostname")

        if reported != device:
            raise ToolError("hostname_mismatch", f"requested {device}, device reported {reported!r}")

        record["outcome"] = "successful"

        return {
            "hostname": reported,
            "manufacturer": version_result.get("mfgName"),
            "model": version_result.get("modelName"),
            "serial_number": version_result.get("serialNumber"),
            "system_mac_address": version_result.get("systemMacAddress"),
            "software_version": version_result.get("version"),
            "uptime_seconds": version_result.get("uptime"),
        }

    except ToolError as exc:
        record["outcome"] = "refused"
        record["blocked_reason"] = exc.reason
        record["detail"] = exc.detail
        raise
    except Exception as exc:
        record["outcome"] = "error"
        record["detail"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record["duration_ms"] = round((time.monotonic() - started) * 1000, 1)
        write_record(record)