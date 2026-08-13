"""Tests for the check_bgp_neighbors mapping and its guards."""

import pytest

from agent_nettools.tools import ToolError, _bgp_from

SUMMARY = {
    "vrfs": {
        "default": {
            "vrf": "default",
            "routerId": "10.1.0.1",
            "asn": "65002",
            "peers": {
                "10.1.1.1": {
                    "asn": "65001",
                    "peerState": "Established",
                    "prefixReceived": 3,
                    "prefixAccepted": 3,
                    "msgReceived": 421,
                    "msgSent": 421,
                },
                "10.1.9.9": {
                    "asn": "65999",
                    "peerState": "Idle",
                    "peerStateIdleReason": "NoInterface",
                    "prefixReceived": 0,
                    "prefixAccepted": 0,
                    "msgReceived": 0,
                    "msgSent": 0,
                },
            },
        }
    }
}


def _peers_by_address(summary: dict) -> dict:
    return {peer["peer_address"]: peer for peer in _bgp_from(summary)["peers"]}


def test_local_asn_and_router_id_are_returned():
    result = _bgp_from(SUMMARY)

    assert result["local_asn"] == "65002"
    assert result["router_id"] == "10.1.0.1"


def test_idle_reason_is_captured_for_an_idle_peer():
    assert _peers_by_address(SUMMARY)["10.1.9.9"]["idle_reason"] == "NoInterface"


def test_idle_reason_defaults_to_empty_for_an_established_peer():
    assert _peers_by_address(SUMMARY)["10.1.1.1"]["idle_reason"] == ""


def test_a_never_established_peer_shows_zero_messages_both_ways():
    decoy = _peers_by_address(SUMMARY)["10.1.9.9"]

    assert decoy["messages_received"] == 0
    assert decoy["messages_sent"] == 0


def test_a_device_with_no_peers_is_refused():
    empty = {"vrfs": {"default": {"routerId": "10.1.0.1", "asn": "65002", "peers": {}}}}

    with pytest.raises(ToolError) as excinfo:
        _bgp_from(empty)

    assert excinfo.value.reason == "no_peers"


def test_a_peer_missing_a_field_is_refused():
    broken = {"vrfs": {"default": {"routerId": "x", "asn": "1", "peers": {"10.1.1.1": {"asn": "65001"}}}}}

    with pytest.raises(ToolError) as excinfo:
        _bgp_from(broken)

    assert excinfo.value.reason == "incomplete_result"