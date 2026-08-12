"""Headless MCP client — proves the server's tools respond."""

import asyncio
import sys

from mcp import Client

from mcp_server.server import mcp


async def main() -> None:
    device = sys.argv[1] if len(sys.argv) > 1 else "leaf1"

    async with Client(mcp) as client:
        print("=== TOOLS EXPOSED BY THE SERVER ===")
        listed = await client.list_tools()
        for tool in listed.tools:
            print(f"  - {tool.name}: {tool.description}")

        print("\n=== CALL: list_lab_devices ===")
        result = await client.call_tool("list_lab_devices", {})
        print(result)

        print(f"\n=== CALL: device_status (device={device}) ===")
        result = await client.call_tool("device_status", {"device": device})
        print(result)


if __name__ == "__main__":
    asyncio.run(main())