"""Read-only network tools. Contracts: docs/*.yml"""

import time
from contextlib import contextmanager
from typing_extensions import TypedDict

from agent_nettools.audit import utc_now, write_record
from agent_nettools.eapi import EapiError, run_commands
from agent_nettools.inventory import is_approved, load_approved_devices
from agent_nettools.topology import resolve_address


class DeviceStatus(TypedDict):
    hostname: str
    manufacturer: str
    model: str
    serial_number: str
    system_mac_address: str
    software_version: str
    uptime_seconds: float


class DeviceList(TypedDict):
    devices: list[str]


class InterfaceRecord(TypedDict):
    name: str
    link_status: str
    protocol_status: str
    ip_address: str


class InterfaceList(TypedDict):
    interfaces: list[InterfaceRecord]


COMMANDS = ["show hostname", "show version"]

VERSION_FIELDS = {
    "manufacturer": "mfgName",
    "model": "modelName",
    "serial_number": "serialNumber",
    "system_mac_address": "systemMacAddress",
    "software_version": "version",
    "uptime_seconds": "uptime",
}

INTERFACE_COMMANDS = ["show ip interface brief", "show hostname"]

EXCLUDED_INTERFACES = {"Management0"}


class ToolError(Exception):
    """Raised when the tool cannot return a trustworthy result."""

    def __init__(self, reason: str, detail: str):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}")


@contextmanager
def audited(tool: str, caller: str, **initial):
    """Write one audit record for this call, whatever happens inside the block."""
    started = time.monotonic()

    record = {
        "timestamp": utc_now(),
        "tool": tool,
        "caller": caller,
        "outcome": None,
        "blocked_reason": None,
        "detail": None,
        "duration_ms": None,
        **initial,
    }

    try:
        yield record
        record["outcome"] = "successful"
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


def _connect(device: str, record: dict, commands: list[str]) -> list[dict]:
    """Gate, resolve, connect. Raise ToolError on any refusal."""
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
    record["command_sent"] = commands

    try:
        return run_commands(address, commands)
    except EapiError as exc:
        raise ToolError(exc.reason, exc.detail) from exc


def _verify_hostname(requested: str, hostname_result: dict) -> str:
    """Confirm we reached the device we asked for."""
    reported = hostname_result.get("hostname")

    if reported != requested:
        raise ToolError("hostname_mismatch", f"requested {requested}, device reported {reported!r}")

    return reported


def _identity_from(version_result: dict) -> dict:
    """Map the device's fields to the contract's fields. Raise if any are absent."""
    identity = {}
    missing = []

    for contract_field, device_field in VERSION_FIELDS.items():
        if device_field not in version_result:
            missing.append(device_field)
        else:
            identity[contract_field] = version_result[device_field]

    if missing:
        raise ToolError("incomplete_result", f"show version omitted: {', '.join(missing)}")

    return identity


def _interfaces_from(brief_result: dict) -> list[InterfaceRecord]:
    """Map the device's interface mapping to the contract's records."""
    interfaces = brief_result.get("interfaces")

    if not isinstance(interfaces, dict):
        raise ToolError("incomplete_result", "no 'interfaces' mapping in show ip interface brief")

    records: list[InterfaceRecord] = []

    for name, entry in interfaces.items():
        if name in EXCLUDED_INTERFACES:
            continue

        address = entry.get("interfaceAddress", {}).get("ipAddr", {})
        missing = [f for f in ("interfaceStatus", "lineProtocolStatus") if f not in entry]

        if "address" not in address or "maskLen" not in address:
            missing.append("interfaceAddress.ipAddr")

        if missing:
            raise ToolError("incomplete_result", f"{name} omitted: {', '.join(missing)}")

        records.append({
            "name": name,
            "link_status": entry["interfaceStatus"],
            "protocol_status": entry["lineProtocolStatus"],
            "ip_address": f"{address['address']}/{address['maskLen']}",
        })

    if not records:
        raise ToolError("no_interfaces", "device returned no interfaces outside the excluded set")

    return records


def get_device_status(device: str, caller: str = "cli") -> DeviceStatus:
    """Return the identity of the requested device as the device itself reports it."""
    with audited(
        "get_device_status",
        caller,
        requested_device=device,
        approved=False,
        target_address=None,
        command_sent=None,
    ) as record:
        hostname_result, version_result = _connect(device, record, COMMANDS)

        identity = _identity_from(version_result)
        identity["hostname"] = _verify_hostname(device, hostname_result)

        return identity


def list_devices(caller: str = "cli") -> DeviceList:
    """Return the names of the devices this toolset is permitted to reach."""
    with audited("list_devices", caller, device_count=None) as record:
        try:
            devices = load_approved_devices()
        except FileNotFoundError as exc:
            raise ToolError("list_unreadable", str(exc)) from exc
        except ValueError as exc:
            raise ToolError("list_malformed", str(exc)) from exc

        record["device_count"] = len(devices)

        return {"devices": devices}


def check_interfaces(device: str, caller: str = "cli") -> InterfaceList:
    """Return the operational state of each fabric interface on the requested device."""
    with audited(
        "check_interfaces",
        caller,
        requested_device=device,
        approved=False,
        target_address=None,
        command_sent=None,
        interface_count=None,
    ) as record:
        brief_result, hostname_result = _connect(device, record, INTERFACE_COMMANDS)

        _verify_hostname(device, hostname_result)

        interfaces = _interfaces_from(brief_result)
        record["interface_count"] = len(interfaces)

        return {"interfaces": interfaces}