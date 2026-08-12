"""Send read-only show commands to a device over Arista eAPI."""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

TIMEOUT_SECONDS = 5


class EapiError(Exception):
    """Raised when eAPI cannot be reached, refuses us, or rejects a command."""


def _credentials() -> tuple[str, str]:
    username = os.environ.get("EOS_USERNAME")
    password = os.environ.get("EOS_PASSWORD")

    if not username or not password:
        raise EapiError("EOS_USERNAME and EOS_PASSWORD must be set (see .env.example)")

    return username, password


def run_commands(address: str, commands: list[str]) -> list[dict]:
    """Run show commands on one device and return one result per command, in order."""
    username, password = _credentials()

    payload = {
        "jsonrpc": "2.0",
        "method": "runCmds",
        "params": {"version": 1, "cmds": commands, "format": "json"},
        "id": "get_device_status",
    }

    try:
        response = requests.post(
            f"https://{address}/command-api",
            json=payload,
            auth=(username, password),
            verify=False,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout as exc:
        raise EapiError(f"no response from {address} within {TIMEOUT_SECONDS}s") from exc
    except requests.exceptions.ConnectionError as exc:
        raise EapiError(f"could not connect to {address}: {exc}") from exc

    if response.status_code == 401:
        raise EapiError(f"authentication rejected by {address}")

    response.raise_for_status()

    body = response.json()

    if "error" in body:
        raise EapiError(f"{address} rejected a command: {body['error'].get('message')}")

    return body["result"]