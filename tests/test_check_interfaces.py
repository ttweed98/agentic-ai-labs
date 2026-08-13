"""Tests for the check_interfaces mapping and its guards."""

import pytest

from agent_nettools.tools import ToolError, _interfaces_from

BRIEF = {
    "interfaces": {
        "Ethernet3": {
            "name": "Ethernet3",
            "interfaceStatus": "disabled",
            "lineProtocolStatus": "down",
            "interfaceAddress": {"ipAddr": {"address": "10.100.1.1", "maskLen": 24}},
        },
        "Management0": {
            "name": "Management0",
            "interfaceStatus": "connected",
            "lineProtocolStatus": "up",
            "interfaceAddress": {"ipAddr": {"address": "172.20.20.13", "maskLen": 24}},
        },
    }
}


def test_management0_is_excluded():
    names = {record["name"] for record in _interfaces_from(BRIEF)}

    assert names == {"Ethernet3"}


def test_admin_down_is_distinguishable_from_link_down():
    record = _interfaces_from(BRIEF)[0]

    assert record["link_status"] == "disabled"
    assert record["protocol_status"] == "down"


def test_address_and_mask_are_joined():
    assert _interfaces_from(BRIEF)[0]["ip_address"] == "10.100.1.1/24"


def test_a_device_with_only_management0_returns_no_interfaces():
    only_mgmt = {"interfaces": {"Management0": BRIEF["interfaces"]["Management0"]}}

    with pytest.raises(ToolError) as excinfo:
        _interfaces_from(only_mgmt)

    assert excinfo.value.reason == "no_interfaces"


def test_a_record_missing_a_field_is_refused():
    broken = {"interfaces": {"Ethernet1": {"name": "Ethernet1", "interfaceStatus": "connected"}}}

    with pytest.raises(ToolError) as excinfo:
        _interfaces_from(broken)

    assert excinfo.value.reason == "incomplete_result"