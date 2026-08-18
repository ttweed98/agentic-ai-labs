"""The read-only troubleshooting agent. Discover, collect, analyze, present."""

import json
import sys
import uuid
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from agent_nettools.tools import (
    ToolError,
    check_bgp_neighbors,
    check_interfaces,
    check_routes,
    list_devices,
)

load_dotenv()

COLLECTORS = {
    "interfaces": check_interfaces,
    "routes": check_routes,
    "bgp": check_bgp_neighbors,
}

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_FILE = REPO_ROOT / "prompts" / "analyze.md"
RUNS_DIR = REPO_ROOT / "runs"

MODEL = "claude-sonnet-5"
MAX_TOKENS = 2000


def collect(device: str, caller: str) -> dict:
    """Call every read-only tool for one device. Record refusals as evidence."""
    evidence = {}
    
    for name, tool in COLLECTORS.items():
        try:
            evidence[name] = tool(device, caller=caller)
        except ToolError as exc:
            evidence[name] = {"error": exc.reason, "detail": exc.detail}
            
    return evidence

def analyze(device: str, evidence: dict) -> str:
    """Send the evidence package to the model. Return its verdict."""
    message = (
        f"{PROMPT_FILE.read_text()}\n\n"
        f"## Evidence collected from {device}\n\n"
        f"```json\n{json.dumps(evidence, indent=2)}\n```\n"
    )
    
    response = Anthropic().messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": message}],
    )
    
    print(f"[{MODEL}: {response.usage.input_tokens} in, {response.usage.output_tokens} out]")

    return "".join(block.text for block in response.content if block.type == "text")

def save_run(device: str, session: str, evidence: dict, verdict: str) -> Path:
    """Write the whole run to a file so it can be scored later."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    
    path = RUNS_DIR / f"{device}-{session.split(':')[1]}.md"
    
    path.write_text(
        f"# Agent run - {device}\n\n"
        f"- session: `{session}`\n"
        f"- model: `{MODEL}`\n\n"
        f"## Evidence\n\n```json\n{json.dumps(evidence, indent=2)}\n```\n\n"
        f"## Verdict\n\n{verdict}\n"
    )
    
    return path
    

def main() -> None:
    device = sys.argv[1] if len(sys.argv) > 1 else "leaf1"
    session = f"agent:{uuid.uuid4().hex[:8]}"
    
    print(f"## Step 1: Discover devices   [session {session}]")
    available = list_devices(caller=session)["devices"]
    print(f"Available devices:  {', '.join(available)}")
    
    if device not in available:
        print(f"\n{device} is not an approved device. Stopping.")
        return
    
    print(f"\n## Step2: Collect evidence for {device}")
    evidence = collect(device, session)
    
    for name, result in evidence.items():
        status = "error: " + result["error"] if "error" in result else "ok"
        print(f"  {name}: {status}")
    
    print("\n## Step 3: Analyze evidence")
    verdict = analyze(device, evidence)

    print(f"\n{verdict}")

    path = save_run(device, session, evidence, verdict)
    print(f"\n[run saved to {path}]")

if __name__ == "__main__":
    main()