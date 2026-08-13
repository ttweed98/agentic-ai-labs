"""MCP server exposing the approved read-only network tools."""

from mcp.server import MCPServer

from agent_nettools.tools import (
    DeviceList,
    DeviceStatus,
    InterfaceList,
    RouteList,
    BgpSummary,
    check_interfaces,
    check_routes,
    get_device_status,
    list_devices,
    check_bgp_neighbors,
)

mcp = MCPServer("AI Network Lab Tools")


@mcp.tool()
def list_lab_devices() -> DeviceList:
    """List the devices this toolset is permitted to reach."""
    return list_devices(caller="mcp")


@mcp.tool()
def device_status(device: str) -> DeviceStatus:
    """Return the identity of one approved device as the device itself reports it."""
    return get_device_status(device, caller="mcp")


@mcp.tool()
def interfaces(device: str) -> InterfaceList:
    """Return the operational state of each fabric interface on one approved device."""
    return check_interfaces(device, caller="mcp")


@mcp.tool()
def routes(device: str) -> RouteList:
    """Return the connected and BGP-learned routes on one approved device."""
    return check_routes(device, caller="mcp")

@mcp.tool()
def bgp_neighbors(device: str) -> BgpSummary:
    """Return the state of each BGP peer on one approved device."""
    return check_bgp_neighbors(device, caller="mcp")


if __name__ == "__main__":
    mcp.run()