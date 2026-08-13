"""Tests for the surface the MCP server exposes."""

import asyncio

from mcp_server.server import mcp

EXPECTED_TOOLS = {"list_lab_devices", "device_status", "interfaces", "routes", "bgp_neighbors"}

FORBIDDEN_TOOLS = {"run_command", "configure_device", "execute", "send_cli", "shell", "reload"}


def _tool_names() -> set:
    return {tool.name for tool in asyncio.run(mcp.list_tools())}


def test_exactly_the_intended_tools_are_registered():
    assert _tool_names() == EXPECTED_TOOLS


def test_no_generic_execution_tool_is_registered():
    names = _tool_names()

    assert names, "no tools are registered at all — the server is not wired up"
    assert not (names & FORBIDDEN_TOOLS)