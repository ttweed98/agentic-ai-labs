# Agentic AI Labs — Case 01

A read-only network troubleshooting agent, a four-node BGP fabric, a planted
fault, and a written rubric — built to answer one question:

**What does an AI agent actually need in order to diagnose a network fault
correctly?**

The short answer, measured over twenty scored runs:

| evidence given to the agent | mean score (out of 6) |
|---|---|
| one device's live state | 3.2 |
| the whole fabric's live state | 2.9 |
| the whole fabric + a question that asks about impact | 3.1 |
| **the above + each device's intended configuration** | **6.0** (5 runs of 5) |

More observation did not help. **What was missing was intent** — a record of
what the network was designed to be. Full write-up in
[`docs/case-01-findings.md`](docs/case-01-findings.md).

---

## What's here

```
src/agent_nettools/     the tool layer  — six read-only tools, each with a contract
mcp_server/             an MCP server exposing those tools
scripts/agent_loop.py   the agent — discover, collect, analyse, present
prompts/                one prompt per experimental condition
docs/                   tool contracts, the fault case, the findings
lab/                    containerlab topology and device configs
runs/                   every scored run, with its prompt and evidence
tests/                  20 tests
```

### The tools

| tool | answers |
|---|---|
| `list_devices` | which devices may this toolset reach? |
| `get_device_status` | what is this device, as it reports itself? |
| `check_interfaces` | what is the operational state of each interface? |
| `check_routes` | what connected and BGP routes does it hold? |
| `check_bgp_neighbors` | what is the state of each BGP peer? |
| `get_intended_config` | what was this device *designed* to look like? |

Every tool is read-only, gated against a hand-written device allowlist, and
writes an audit record on every path — success, refusal, or error. There is no
generic "run a command" tool, and no write path anywhere in the codebase.

**Each tool has a contract in `docs/` written before its code**, specifying what
it returns, where each field comes from, and every condition under which it
refuses. The refusal tokens in the contracts are the same strings that appear in
the audit log.

---

## The experiment

**The fault** (`docs/faults/case-01-*`): `leaf1 Ethernet3` administratively shut
down, which removes the connected route for `10.100.1.0/24` and stops that
prefix being advertised anywhere in the fabric.

**The decoy**: a BGP neighbour that does not exist — `10.1.9.9`, remote-as
65999, in a subnet no interface owns. Idle, zero messages ever exchanged,
completely harmless, and much louder than the real fault.

**No single device shows both cause and effect.** leaf1 shows the disabled
interface. Only the spines show that the prefix stopped arriving.

**The rubric** is six pass/fail criteria written before any run — including
*"explicitly dismisses the 10.1.9.9 peer as unrelated,"* which failed **0 for
15** until intent was added, then passed 5 for 5.

---

## Running it

### Requirements

- Docker and [containerlab](https://containerlab.dev/)
- The Arista cEOS image (`ceos:4.34.0F`) — free with an Arista account
- Python 3.10+
- An Anthropic API key

### Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then add EOS_USERNAME, EOS_PASSWORD, ANTHROPIC_API_KEY

cd lab && containerlab deploy -t topology.clab.yml && cd ..
pytest -q
```

### Reproduce the experiment

Inject the fault:

```bash
docker exec -it clab-ai-network-leaf1 Cli
# enable, configure, then paste docs/faults/case-01-inject.cfg
```

Run the four conditions:

```bash
PYTHONPATH=src python3 scripts/agent_loop.py leaf1
PYTHONPATH=src python3 scripts/agent_loop.py leaf1 --fabric
PYTHONPATH=src python3 scripts/agent_loop.py leaf1 --fabric --impact
PYTHONPATH=src python3 scripts/agent_loop.py leaf1 --fabric --intent
```

Score each verdict against the six criteria in
`docs/faults/case-01-stale-peer-shut-host-port.md`. Reset with
`docs/faults/case-01-reset.cfg`.

**Run each condition at least five times.** The first five single-device runs in
this repository, on identical evidence with an identical prompt, scored 2, 3, 2,
4 and 5. One run tells you almost nothing — including when it looks good.

Every run writes `runs/<device>-<mode>-<prompt>-<session>.md` containing the
exact prompt and evidence used, and every tool call writes a line to
`logs/audit.jsonl` tagged with the session ID.

---

## Try it yourself

The interesting exercise isn't re-running Case 01 — it's **building Case 02**.

Design a fault, write the gold answer and its pass/fail criteria *before* you
run anything, then find out what evidence the agent needs to reach it. The
`docs/faults/` directory shows the format.

Faults worth trying: a single spine link down (symptom, no impact) versus both
down (real outage); a prefix filtered inbound so a session is Established but
under-receiving; a fabric that is entirely healthy — which is the hardest case,
because the agent will want to find something.

---

## A note on the credential in `lab/configs/`

There is a plaintext credential in the device configurations
(`username admin ... secret admin`), and it is sent to the model as part of the
intent evidence. **This is deliberate and it is left visible on purpose.**

The lab is disposable, the credential is `admin/admin`, and it grants access to
nothing that outlives a `containerlab destroy`. Stripping it would make this
repository look more careful without making anything safer, and would break
reproduction.

**In production the same reasoning gives the opposite answer.** Device
configurations contain real credentials, ACLs, customer-identifying interface
descriptions and addressing — and in this design all of that would be sent to a
hosted model. Before that happens it needs sanitising, and **by allowlist**,
returning only the sections the agent needs, rather than by denylist, which only
removes the secrets someone thought to name.

The relevant question is never "is there a secret in this file." It is "what
happens if this leaks."

---

## Limitations

One fault case, one model, five runs per condition, and the person who designed
the fault also scored the answers. See the limitations section of
[`docs/case-01-findings.md`](docs/case-01-findings.md) for the full list — they
bound what this result supports.

## License

MIT.