"""MCP server exposing the approved read-only network tools."""

from mcp.server import MCPServer

from agent_nettools.tools import DeviceList, DeviceStatus, InterfaceList, get_device_status, list_devices, check_interfaces

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


if __name__ == "__main__":
    mcp.run()