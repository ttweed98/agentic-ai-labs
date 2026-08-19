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
    get_intended_config,
    list_devices,
)

load_dotenv()

COLLECTORS = {
    "interfaces": check_interfaces,
    "routes": check_routes,
    "bgp": check_bgp_neighbors,
}

INTENT_COLLECTORS = {**COLLECTORS, "intent": get_intended_config}

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = REPO_ROOT / "prompts"
RUNS_DIR = REPO_ROOT / "runs"

MODEL = "claude-sonnet-5"
MAX_TOKENS = 10000


def collect(device: str, caller: str, collectors: dict) -> dict:
    """Call every tool in collectors for one device. Record refusals as evidence."""
    evidence = {}

    for name, tool in collectors.items():
        try:
            evidence[name] = tool(device, caller=caller)
        except ToolError as exc:
            evidence[name] = {"error": exc.reason, "detail": exc.detail}

    return evidence


def collect_fabric(target: str, available: list[str], caller: str, collectors: dict) -> dict:
    """Collect from every approved device, marking which one we started from."""
    return {
        "target": target,
        "devices": {device: collect(device, caller, collectors) for device in available},
    }


def build_message(device: str, evidence: dict, prompt_file: Path) -> str:
    """The opening message: the prompt plus the evidence package."""
    return (
        f"{prompt_file.read_text()}\n\n"
        f"## Evidence collected for {device}\n\n"
        f"```json\n{json.dumps(evidence, indent=2)}\n```\n"
    )


def ask(messages: list[dict]) -> tuple[str, str]:
    """Send the whole conversation so far. Return (reply, thinking)."""
    response = Anthropic().messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        messages=messages,
    )

    print(f"[{MODEL}: {response.usage.input_tokens} in, {response.usage.output_tokens} out]")

    text = "".join(b.text for b in response.content if b.type == "text")
    thinking = "\n\n".join(
        getattr(b, "thinking", "") for b in response.content if b.type == "thinking"
    )

    return text, thinking


def save_run(
    device: str,
    session: str,
    evidence: dict,
    verdict: str,
    mode: str,
    prompt_file: Path,
) -> Path:
    """Write the whole run to a file so it can be scored and reproduced later."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    path = RUNS_DIR / f"{device}-{mode}-{prompt_file.stem}-{session.split(':')[1]}.md"

    path.write_text(
        f"# Agent run — {device} ({mode})\n\n"
        f"- session: `{session}`\n"
        f"- model: `{MODEL}`\n"
        f"- prompt: `{prompt_file.name}`\n\n"
        f"## Prompt\n\n```\n{prompt_file.read_text()}\n```\n\n"
        f"## Evidence\n\n```json\n{json.dumps(evidence, indent=2)}\n```\n\n"
        f"## Verdict\n\n{verdict}\n"
    )

    return path


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    device = args[0] if args else "leaf1"

    fabric = "--fabric" in sys.argv
    intent = "--intent" in sys.argv

    mode = "fabric" if fabric else "single"
    collectors = INTENT_COLLECTORS if intent else COLLECTORS

    if intent:
        prompt_name = "analyze-intent"
    elif "--impact" in sys.argv:
        prompt_name = "analyze-impact"
    else:
        prompt_name = f"analyze-{mode}"

    prompt_file = PROMPTS_DIR / f"{prompt_name}.md"

    session = f"agent:{uuid.uuid4().hex[:8]}"

    print(f"## Step 1: Discover devices   [session {session}, mode {mode}]")
    available = list_devices(caller=session)["devices"]
    print(f"Available devices: {', '.join(available)}")

    if device not in available:
        print(f"\n{device} is not an approved device. Stopping.")
        return

    print(f"\n## Step 2: Collect evidence for {device}")

    if fabric:
        evidence = collect_fabric(device, available, session, collectors)

        for name, result in evidence["devices"].items():
            print(f"  {name}: {', '.join(result)}")
    else:
        evidence = collect(device, session, collectors)

        for name, result in evidence.items():
            status = "error: " + result["error"] if "error" in result else "ok"
            print(f"  {name}: {status}")

    print(f"\n## Step 3: Analyze evidence   [prompt {prompt_file.name}]")

    messages = [{"role": "user", "content": build_message(device, evidence, prompt_file)}]
    verdict, thinking = ask(messages)
    messages.append({"role": "assistant", "content": verdict})

    print(f"\n{verdict}")

    path = save_run(device, session, evidence, verdict, mode, prompt_file)
    print(f"\n[run saved to {path}]")

    print("\n## Step 4: Ask follow-up questions (blank line to finish)")

    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            break

        if not question:
            break

        messages.append({"role": "user", "content": question})
        answer, _ = ask(messages)
        messages.append({"role": "assistant", "content": answer})

        print(f"\n{answer}")


if __name__ == "__main__":
    main()