"""Append-only audit log of tool calls."""

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_LOG_FILE = REPO_ROOT / "logs" / "audit.jsonl"


def utc_now() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_record(record: dict, path: Path = AUDIT_LOG_FILE) -> None:
    """Append one record to the audit log as a single JSON line."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")