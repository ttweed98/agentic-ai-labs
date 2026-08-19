"""Load the configuration a device was designed to have."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = REPO_ROOT / "lab" / "configs"


def load_intended_config(device: str, configs_dir: Path = CONFIGS_DIR) -> str:
    """Return the intended configuration for device.

    Assumes the caller has already checked the device against the approved
    list — the device name becomes a filename here.
    """
    path = configs_dir / f"{device}.cfg"

    if not path.is_file():
        raise FileNotFoundError(f"no intended config for {device}: {path.name}")

    config = path.read_text()

    if not config.strip():
        raise ValueError(f"{path.name}: intended config is empty")

    return config