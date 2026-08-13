# Tool roadmap

Derived from Fault Case 01, not from a feature list. Each tool exists because
diagnosing a real, verified fault required it.

## What Case 01 proved

The three tools disagree, and the disagreement is the diagnosis:

- **interfaces** showed the cause (Et3 disabled) and nothing about impact.
- **BGP** showed a decoy (10.1.9.9 Idle) and two healthy sessions that
  concealed a withdrawn prefix.
- **route** was the only tool that showed the impact, and only by absence.

No single device held both cause and impact. That is the constraint the tool
set has to satisfy.

## Build order

### 1. check_interfaces
`show interfaces status` + `show ip interfaces brief`

First because it is the simplest instance of the new shape — a **list** return
rather than the flat record `get_device_status` produces — and because Case 01's
cause lives here.

Decisions to make:
- Include Management0 and flag it, or exclude it? It is out-of-band; it is also
  the only interface that is up when the fabric is down.
- `disabled` vs `notconnect` **must survive into the return.** The gold answer
  scores on that distinction, so a tool that collapses both to "down" makes the
  correct verdict unreachable.

### 2. check_routes
`show ip route connected` + `show ip route bgp`, or prefix-scoped

Second because Case 01 proved it is the only tool that shows impact.

Never unscoped — the full table is unbounded output into a model's context, and
it grows with the fabric.

### 3. check_bgp_neighbors
`show ip bgp summary`

Third and hardest. Multi-peer output reopens partial state: one peer Idle, two
Established — success or failure? And `PfxRcd` carries no verdict on its own;
it means something only against a comparison.

This is also where the **decorator refactor** lands. By the third tool the
record dict and the try/except/finally scaffolding will have been written three
times, so the shared shape is proven rather than guessed.

### 4. check_lldp_neighbors
`show lldp neighbors`

Two contract rules already known from real output:
- Exclude Management0 from fabric reasoning. Every node shares the management
  bridge, so Ma0 reports every other node as a neighbour.
- **Absence of a neighbour is not a fault.** Hosts do not run LLDP, so Et3 will
  never have a neighbour even when perfectly healthy.

### 5. ping_device
Deferred longest, and needs the most justification.

Its argument is a **destination**, not an approved device name, so the existing
allowlist does not fit. Unrestricted it is a reachability scanner. Needs either
a separate allowlist of permitted destinations, or a rule that the destination
must be a prefix the fabric already advertises.

## Cross-cutting

All four read tools return **lists**, unlike `get_device_status`. Solve the
shape once: nested TypedDicts, and a decision about what happens when one entry
in a list cannot be read.