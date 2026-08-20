"""Tests for the get_device_status tool and its guards."""

import json

import pytest

from agent_nettools.inventory import is_approved, load_approved_devices
from agent_nettools.topology import resolve_address
from agent_nettools.tools import ToolError, get_device_status, list_devices


def test_approved_list_loads_as_a_list_of_names():
    devices = load_approved_devices()

    assert isinstance(devices, list)
    assert all(isinstance(name, str) for name in devices)


def test_membership_is_exact_not_substring():
    assert is_approved("leaf1")
    assert not is_approved("eaf")
    assert not is_approved("leaf9")


def test_unapproved_device_is_refused():
    with pytest.raises(ToolError) as excinfo:
        get_device_status("leaf9")

    assert excinfo.value.reason == "not_approved"


def test_non_eos_node_is_refused_by_kind(tmp_path):
    topology = tmp_path / "topology-data.json"
    topology.write_text(json.dumps({"nodes": {"host1": {"kind": "linux"}}}))

    with pytest.raises(ValueError, match="not 'arista_ceos'"):
        resolve_address("host1", path=topology)


def test_refusal_is_recorded_before_any_contact(monkeypatch):
    captured = []
    monkeypatch.setattr("agent_nettools.tools.write_record", captured.append)

    with pytest.raises(ToolError):
        get_device_status("leaf9")

    record = captured[0]

    assert record["outcome"] == "refused"
    assert record["blocked_reason"] == "not_approved"
    assert record["target_address"] is None
    assert record["command_sent"] is None


def test_the_password_never_reaches_the_audit_record(monkeypatch):
    captured = []
    monkeypatch.setattr("agent_nettools.tools.write_record", captured.append)
    monkeypatch.setenv("EOS_PASSWORD", "planted-secret-value")

    with pytest.raises(ToolError):
        get_device_status("leaf9")

    assert "planted-secret-value" not in json.dumps(captured[0])

def test_list_devices_returns_the_approved_names(monkeypatch):
    captured = []
    monkeypatch.setattr("agent_nettools.tools.write_record", captured.append)

    result = list_devices()

    assert result["devices"] == load_approved_devices()
    assert captured[0]["outcome"] == "successful"
    assert captured[0]["device_count"] == len(result["devices"])