"""Resolve an approved device name to the address the tools connect to."""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY_DATA_FILE = REPO_ROOT / "lab" / "clab-ai-network" / "topology-data.json"

EOS_KIND = "arista_ceos"


def resolve_address(device: str, path: Path = TOPOLOGY_DATA_FILE) -> str:
    """Return the management address for device. Raise if it cannot be resolved."""
    if not path.is_file():
        raise FileNotFoundError(f"Topology data not found (is the lab deployed?): {path}")

    with path.open() as handle:
        data = json.load(handle)

    nodes = data.get("nodes")

    if not isinstance(nodes, dict):
        raise ValueError(f"{path}: expected a 'nodes' mapping")

    node = nodes.get(device)

    if node is None:
        raise LookupError(f"{device} not present in {path}")

    kind = node.get("kind")

    if kind != EOS_KIND:
        raise ValueError(f"{device} has kind {kind!r}, not {EOS_KIND!r}")

    address = node.get("mgmt-ipv4-address")

    if not address:
        raise ValueError(f"{device} has no mgmt-ipv4-address in {path}")

    return address