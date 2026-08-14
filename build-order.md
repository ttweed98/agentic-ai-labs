# Build order and call path

Two views of the same codebase. The first is the order the files were written
in and why. The second is what happens on one call at runtime.

They are close to mirror images: the code was built **bottom-up**, and a call
enters at the **top** and falls through the same layers in reverse.

---

## 1. Build order

Each file could be written and tested with nothing above it existing yet,
because no file calls upward.

```mermaid
%%{init: {'theme':'base','themeVariables':{
  'primaryColor':'#eef4fb',
  'primaryTextColor':'#1b2733',
  'primaryBorderColor':'#8fb0d4',
  'lineColor':'#7a8b9c',
  'fontSize':'15px',
  'clusterBkg':'#fbfcfe',
  'clusterBorder':'#cdd8e3'
}}}%%
flowchart TB
    B1["<b>1 · inventory.py</b><br/>the gate<br/><i>may this tool touch this device?</i><br/>no network · pure logic"]
    B2["<b>2 · topology.py</b><br/>the lookup<br/><i>what address? is it an EOS box?</i><br/>reads topology-data.json"]
    B3["<b>3 · eapi.py</b><br/>the transport<br/><i>send commands, get JSON back</i><br/>the only file that touches the network"]
    B4["<b>4 · audit.py</b><br/>the record<br/><i>append one line per call</i>"]
    B5["<b>5 · tools.py</b><br/>the tools<br/><i>compose the layers below,</i><br/><i>map the device's answer to the contract</i>"]
    B6["<b>6 · mcp_server/server.py</b><br/>the surface<br/><i>publish the tools over MCP</i><br/>adds no safety of its own"]

    B1 --> B2 --> B3 --> B5
    B4 --> B5
    B5 --> B6

    style B1 fill:#e8f2ea,stroke:#8fbfa0,color:#1b2733
    style B2 fill:#e8f2ea,stroke:#8fbfa0,color:#1b2733
    style B3 fill:#eef4fb,stroke:#8fb0d4,color:#1b2733
    style B4 fill:#fdf5e8,stroke:#dcc08a,color:#1b2733
    style B5 fill:#eef4fb,stroke:#8fb0d4,color:#1b2733
    style B6 fill:#f4eefb,stroke:#b79fd4,color:#1b2733
```

**Why this order**

| # | File | Built when it was because |
|---|---|---|
| 1 | `inventory.py` | Everything depends on "am I allowed to touch this device". No network, no credentials — if this is wrong, nothing else matters. |
| 2 | `topology.py` | Only an *approved* name is worth resolving. Gate first, lookup second. |
| 3 | `eapi.py` | You cannot connect until you know where to. |
| 4 | `audit.py` | Small and standalone; the tools call it, so it exists before they do. |
| 5 | `tools.py` | Each tool composes the four files below it. |
| 6 | `server.py` | Publishes tools that must already exist and already work. |

---

## 2. Runtime — one call to `check_interfaces('leaf1')`

```mermaid
%%{init: {'theme':'base','themeVariables':{
  'primaryColor':'#eef4fb',
  'primaryTextColor':'#1b2733',
  'primaryBorderColor':'#8fb0d4',
  'lineColor':'#7a8b9c',
  'fontSize':'15px'
}}}%%
flowchart TB
    R0["MCP client asks for<br/><b>interfaces(device='leaf1')</b>"]
    R1["<b>server.py</b> wrapper calls<br/>check_interfaces(caller='mcp')"]
    R2["<b>audited(...)</b> opens the audit record"]
    R3{"is_approved('leaf1')?<br/><i>inventory.py</i>"}
    R4["ToolError<br/><b>not_approved</b><br/>~0.4 ms · no socket opened"]
    R5{"resolve_address('leaf1')<br/><i>topology.py</i>"}
    R6["ToolError<br/><b>not_in_topology</b> · <b>wrong_kind</b>"]
    R7["run_commands(172.20.20.13, cmds)<br/><i>eapi.py</i>"]
    R8["ToolError<br/><b>connect_failed</b> · <b>no_response</b><br/><b>auth_rejected</b> · <b>command_failed</b>"]
    R9{"hostname returned ==<br/>hostname requested?"}
    R10["ToolError<br/><b>hostname_mismatch</b>"]
    R11["_interfaces_from(...)<br/>drop Management0<br/>map to contract fields"]
    R12["return<br/>{'interfaces': [ ... ]}"]
    R13["<b>finally: write_record()</b><br/>runs on every path"]

    R0 --> R1 --> R2 --> R3
    R3 -->|no| R4
    R3 -->|yes| R5
    R5 -->|fails| R6
    R5 -->|ok| R7
    R7 -->|fails| R8
    R7 -->|ok| R9
    R9 -->|no| R10
    R9 -->|yes| R11 --> R12
    R12 --> R13
    R4 --> R13
    R6 --> R13
    R8 --> R13
    R10 --> R13

    style R4 fill:#fbeeee,stroke:#d49f9f,color:#1b2733
    style R6 fill:#fbeeee,stroke:#d49f9f,color:#1b2733
    style R8 fill:#fbeeee,stroke:#d49f9f,color:#1b2733
    style R10 fill:#fbeeee,stroke:#d49f9f,color:#1b2733
    style R12 fill:#e8f2ea,stroke:#8fbfa0,color:#1b2733
    style R13 fill:#fdf5e8,stroke:#dcc08a,color:#1b2733
```

**Two things this makes visible**

- **Every path ends at `write_record()`.** Approved or refused, connected or
  timed out — the audit line is written. That is the `finally` block, and it is
  why the log can be trusted.
- **Refusals get cheaper the earlier they fire.** `not_approved` costs about
  0.4 ms and never opens a socket; `hostname_mismatch` costs a full round trip.
  Cheapest and most restrictive check first, deliberately.