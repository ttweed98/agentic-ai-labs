"""Load and check the list of devices this toolset is allowed to reach."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
APPROVED_DEVICES_FILE = REPO_ROOT / "inventory" / "approved_devices.yml"


def load_approved_devices(path: Path = APPROVED_DEVICES_FILE) -> list[str]:
    """Return the approved device names. Raise if the list cannot be trusted."""
    if not path.is_file():
        raise FileNotFoundError(f"Approved device list not found: {path}")

    with path.open() as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping, got {type(data).__name__}")

    devices = data.get("devices")

    if not isinstance(devices, list):
        raise ValueError(f"{path}: 'devices' must be a list, got {type(devices).__name__}")

    if not all(isinstance(name, str) for name in devices):
        raise ValueError(f"{path}: every entry under 'devices' must be a string")

    return devices


def is_approved(device: str) -> bool:
    """True only if device exactly matches an entry in the approved list."""
    return device in load_approved_devices()