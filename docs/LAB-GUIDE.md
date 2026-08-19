# Lab guide

Everything needed to build the fabric, break it deliberately, and run the four
experimental conditions against it.

Diagrams are plain text on purpose — they render in a terminal, an editor, a PDF
and a browser without anything installed.

---

## 1. What you are building

```
                       AS 65001                AS 65001
                    ┌────────────┐          ┌────────────┐
                    │   spine1   │          │   spine2   │
                    │ 10.0.0.1/32│          │ 10.0.0.2/32│
                    └──┬──────┬──┘          └──┬──────┬──┘
                       │      │                │      │
              Et1      │      │      Et2       │      │
        10.1.1.0/31 ───┘      └─── 10.2.1.0/31 │      │
             │                        │        │      │
             │        ┌───────────────┼────────┘      │
             │        │               │               │
             │        │  10.1.2.0/31  │               │
             │        │               │               │
        ┌────┴────────┴───┐      ┌────┴───────────────┴───┐
        │      leaf1      │      │        leaf2           │
        │   10.1.0.1/32   │      │     10.2.0.1/32        │
        │    AS 65002     │      │      AS 65003          │
        └────────┬────────┘      └───────────┬────────────┘
                 │ Et3                       │ Et3
          10.100.1.1/24               10.200.2.1/24
                 │                           │
            ┌────┴────┐                 ┌────┴────┐
            │  host1  │                 │  host2  │
            └─────────┘                 └─────────┘
```

**Four Arista cEOS switches, two Alpine hosts.** Each leaf is its own AS and
peers eBGP with both spines. Each leaf advertises its loopback and its host
subnet.

**The symmetry is the point.** leaf2 is a working copy of leaf1. When leaf1
breaks, leaf2 is the control — and the agent can compare them.

**Management addresses** (containerlab assigns these):

| node | management IP |
|---|---|
| spine1 | 172.20.20.11 |
| spine2 | 172.20.20.12 |
| leaf1 | 172.20.20.13 |
| leaf2 | 172.20.20.14 |
| host1 | 172.20.20.15 |
| host2 | 172.20.20.16 |

Verify the fabric addressing against `lab/topology.clab.yml` and
`lab/configs/*.cfg` — those files are the source of truth, and the agent reads
them as intent.

---

## 2. Prerequisites

- **Docker** and **[containerlab](https://containerlab.dev/install/)**
- **The Arista cEOS image**, `ceos:4.34.0F`. Free with an Arista account:
  download the `.tar.xz`, then
  `docker import cEOS64-lab-4.34.0F.tar.xz ceos:4.34.0F`
- **Python 3.10+**
- **An Anthropic API key** from `console.anthropic.com`, with credit on the
  account. A full four-condition experiment costs a few cents.

Roughly 4 GB of RAM for the four cEOS nodes.

---

## 3. Build it

```bash
git clone <this repo> && cd AI-Agents-for-Networking

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

Edit `.env` — three lines, no quotes:

```
EOS_USERNAME=admin
EOS_PASSWORD=admin
ANTHROPIC_API_KEY=sk-ant-...
```

Deploy the fabric:

```bash
cd lab
containerlab deploy -t topology.clab.yml
cd ..
```

Give it 30–60 seconds. cEOS takes a moment to bring eAPI up after the container
is running, and a tool call made too early fails with a connection error rather
than anything informative.

---

## 4. Verify it is healthy — before you break it

**Do not skip this.** If you inject a fault into a fabric that was already
broken, every result afterwards is meaningless.

```bash
containerlab inspect -t lab/topology.clab.yml
```

All six nodes `running`. Then:

```bash
pytest -q
```

20 passing. Then confirm the tools reach the devices and the fabric is
converged:

```bash
PYTHONPATH=src:. python3 scripts/test_mcp_client.py
```

**What healthy looks like:**

- `leaf1` interfaces: Et1, Et2, Et3 and Lo0 all `connected` / `up`
- `leaf1` routes: **`10.100.1.0/24` present as connected**, plus eBGP routes for
  both spine loopbacks, leaf2's loopback and `10.200.2.0/24`
- `leaf1` BGP: exactly **two** peers, both `Established`, both receiving
  prefixes
- `spine1` BGP: **`prefixes_received: 2`** from *both* leaves

That last line is the one that changes when the fault lands.

---

## 5. The experiment

```
   ┌─────────────────────────────────────────────────────────┐
   │  1. deploy fabric        containerlab deploy            │
   │  2. verify healthy       pytest + test_mcp_client.py    │
   │  3. inject fault         case-01-inject.cfg             │
   │  4. verify fault landed  show ip bgp summary            │
   └───────────────────────────┬─────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
        ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼──────┐
        │  single   │    │  fabric   │    │   intent   │   ← conditions
        │  ×5 runs  │    │  ×5 runs  │    │  ×5 runs   │
        └─────┬─────┘    └─────┬─────┘    └─────┬──────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  score each run     │
                    │  6 criteria         │
                    │  runs/*.md          │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  5. reset the lab   │
                    │  case-01-reset.cfg  │
                    └─────────────────────┘
```

Inside one run:

```
  ┌────────────┐   ┌───────────┐   ┌───────────┐   ┌──────────┐
  │ 1 DISCOVER │──▶│ 2 COLLECT │──▶│ 3 ANALYSE │──▶│ 4 REPORT │──▶ human
  │ list_      │   │ your code │   │ the model │   │ verdict  │    decides
  │ devices    │   │ calls the │   │ reads     │   │ saved to │
  │            │   │ tools     │   │ evidence  │   │ runs/    │
  └────────────┘   └───────────┘   └───────────┘   └──────────┘
        ▲                ▲               ▲
        │                │               │
    allowlist       read-only        no ability to
     gate here       tools only      run anything
```

**The model is only involved in step 3.** It receives a finished evidence
package as text and returns text. It cannot call a tool, reach a device or
execute a command — steps 1 and 2 have already finished by the time it sees
anything. Read-only is enforced by there being no write path in the codebase,
not by asking the model nicely.

---

## 6. Inject the fault

```bash
docker exec -it clab-ai-network-leaf1 Cli
```

Then, at the prompt:

```
enable
configure
router bgp 65002
   neighbor 10.1.9.9 remote-as 65999
!
interface Ethernet3
   shutdown
!
end
exit
```

(Also in `docs/faults/case-01-inject.cfg`.)

**Two changes, doing very different things:**

`interface Ethernet3 / shutdown` is **the real fault**. It removes the connected
route for `10.100.1.0/24`, so the `network 10.100.1.0/24` statement has nothing
to advertise and the prefix disappears fabric-wide. host1 becomes unreachable
from everywhere.

`neighbor 10.1.9.9 remote-as 65999` is **the decoy**. There is no interface in
that subnet, so the session sits in `Idle(NoIf)` having never exchanged a single
message. It is loud, obviously wrong, and harmless — exactly like the leftover
configuration that accumulates in every real network.

### Verify the fault landed

```bash
docker exec -it clab-ai-network-leaf1 Cli -c "show ip bgp summary"
docker exec -it clab-ai-network-leaf1 Cli -c "show interfaces status"
docker exec -it clab-ai-network-spine1 Cli -c "show ip bgp summary"
```

Expect: `10.1.9.9 ... Idle(NoIf)` with zero messages, `Et3 ... disabled`, and on
spine1 **`PfxRcd 1` from leaf1 against `2` from leaf2.**

That last asymmetry is the impact. **No single device shows both the cause and
the effect** — which is the whole reason the conditions below differ.

---

## 7. Run the four conditions

```bash
PYTHONPATH=src python3 scripts/agent_loop.py leaf1
PYTHONPATH=src python3 scripts/agent_loop.py leaf1 --fabric
PYTHONPATH=src python3 scripts/agent_loop.py leaf1 --fabric --impact
PYTHONPATH=src python3 scripts/agent_loop.py leaf1 --fabric --intent
```

| flags | evidence collected | prompt used | what it tests |
|---|---|---|---|
| *(none)* | leaf1 only | `analyze-single.md` | can it diagnose from the device it was asked about? |
| `--fabric` | all four devices | `analyze-fabric.md` | does more evidence help? |
| `--fabric --impact` | all four devices | `analyze-impact.md` | does asking about *impact* rather than *abnormality* help? |
| `--fabric --intent` | all four **+ intended configs** | `analyze-intent.md` | does knowing what was *designed* help? |

Five runs each, unattended:

```bash
for i in 1 2 3 4 5; do
  PYTHONPATH=src python3 scripts/agent_loop.py leaf1 --fabric --intent </dev/null
done
```

`</dev/null` skips the interactive follow-up prompt.

Without `</dev/null` you get a `>` prompt after the verdict and can interrogate
the same evidence — *"what is the impact of Ethernet3 being down?"*, *"is
10.100.1.0/24 in the route table?"* Useful for exploring; **keep scored runs
one-shot** so they stay comparable.

### What the prompts are for

There are four prompts in `prompts/`, and **they differ only where the
experiment requires it**:

- **`analyze-single.md`** — the baseline. States that the evidence is from a
  single device, asks for four sections: summary, evidence, possible cause,
  recommended next check.
- **`analyze-fabric.md`** — identical, except it says "one or more devices."
  `diff` the two: two lines.
- **`analyze-impact.md`** — changes the *shape of the answer*. Instead of one
  "possible cause," it asks for **every** anomaly, what depends on each, and
  which are actually causing something to fail. This forces the agent to write
  down its dismissals instead of skipping them.
- **`analyze-intent.md`** — the impact prompt plus one sentence naming the new
  evidence source. It does **not** say "compare them" or "absences are
  meaningful." Whether the agent works that out is the experiment.

**The prompts deliberately contain no hint about Case 01.** No mention of stale
configuration, prefix counts or interface states. A prompt that gestures at the
answer tests your prompt-writing, not the agent's reasoning.

---

## 8. Score the runs

Each run writes `runs/<device>-<mode>-<prompt>-<session>.md` containing the
prompt used, the exact evidence, and the verdict.

Score each against the six criteria in
`docs/faults/case-01-stale-peer-shut-host-port.md`:

| # | criterion |
|---|---|
| 1 | names Ethernet3 on leaf1 as the cause |
| 2 | distinguishes administrative shutdown from a link failure |
| 3 | explicitly dismisses the 10.1.9.9 peer as unrelated |
| 4 | cites the missing `10.100.1.0/24` prefix, not just the interface state |
| 5 | proposes a read-only next check |
| 6 | does not blame the fabric, the spines or leaf2 |

**Score at least five runs per condition before drawing any conclusion.** The
first five single-device runs in this repository, on identical evidence with an
identical prompt, scored 2, 3, 2, 4 and 5.

Trace any run back through the audit log with its session ID:

```bash
grep <session-id> logs/audit.jsonl
```

Every tool call, in order, with duration and outcome.

---

## 9. Reset

```bash
docker exec -it clab-ai-network-leaf1 Cli
```

```
enable
configure
no router bgp 65002 neighbor 10.1.9.9
interface Ethernet3
   no shutdown
!
end
```

Or destroy and redeploy — the fault only ever exists in the running
configuration, so a redeploy always returns a clean fabric:

```bash
cd lab && containerlab destroy -t topology.clab.yml --cleanup
containerlab deploy -t topology.clab.yml
```

**That is also why `lab/configs/*.cfg` is a trustworthy intent source.** The
fault has never been in those files, and a redeploy proves it.

---

## 10. When the lab misbehaves

**cEOS nodes show `exited` while the Alpine hosts still run.** The usual state
after a host reboot or an ungraceful shutdown. The veth links do not reattach
cleanly, so `docker start` is not enough:

```bash
cd lab
containerlab destroy -t topology.clab.yml --cleanup
for ip in 172.20.20.1{1,2,3,4}; do ssh-keygen -f ~/.ssh/known_hosts -R $ip; done
containerlab deploy -t topology.clab.yml
```

**Redeploying wipes the fault.** It only ever lived in the running config.
Re-inject after every redeploy, and verify before running the agent — otherwise
you are scoring a healthy device.

**`connect_failed` from every tool.** Usually eAPI has not finished starting.
Wait 30 seconds. If it persists, confirm eAPI is up in the management VRF:

```bash
docker exec -it clab-ai-network-leaf1 Cli -c "show management api http-commands"
```

You want `VRFs: MGMT` and a URL on port 443. The startup configs set this; if
it is missing, the config did not apply.

**Certificate warnings on every call.** Expected — cEOS presents a self-signed
certificate and the tools skip verification. The warning is deliberately not
suppressed, because it is true.

**Serial numbers and MAC addresses change on every redeploy.** cEOS generates
them fresh. Runs recorded before a redeploy will show different values; that is
correct and expected — they record what was true at the time.