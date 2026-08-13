# Fault Case 01 — Stale BGP peer + shut host-facing port

**Device under fault:** leaf1
**Class:** decoy + real fault, in different domains
**Configured:** 2026-08-12 (runtime only, not written to startup-config)

## Symptom as reported
Host1 cannot reach anything beyond leaf1. A BGP session on leaf1 is in a
non-established state.

## Impact
`10.100.1.0/24` is advertised nowhere in the fabric. Host1 has no gateway
and is unreachable from every device except leaf1 itself. Nothing else is
affected: leaf2, both spines, and `10.200.2.0/24` are fully operational.

## Root cause
`interface Ethernet3` on leaf1 is **administratively disabled**.

Causal chain:

1. Et3 is shut administratively (`shutdown`), not failed.
2. The connected route `10.100.1.0/24` leaves leaf1's RIB with the interface.
3. leaf1's `network 10.100.1.0/24` statement can only advertise a prefix
   present in the RIB, so BGP has nothing to advertise.
4. The prefix is withdrawn to both spines. spine1's PfxRcd from leaf1 drops
   from 2 to 1.
5. The prefix is absent fabric-wide. Host1's gateway 10.100.1.1 is down.

The BGP sessions themselves never faltered. This is not a BGP fault; it is an
interface fault whose only visible consequence is in BGP.

## Evidence

### leaf1
| Command | Observation |
|---|---|
| `show interfaces status` | `Et3 P2P_TO_HOST1 disabled` — Et1 and Et2 `connected` |
| `show ip route connected` | Lo0, 10.1.1.0/31, 10.1.2.0/31. **No 10.100.1.0/24** |
| `show ip bgp summary` | 10.1.1.1 Estab PfxRcd 3 · 10.1.2.1 Estab PfxRcd 3 · 10.1.9.9 `Idle(NoIf)` |
| `show lldp neighbors` | Et1 → spine1 Et1, Et2 → spine2 Et1 |

### spine1
| Command | Observation |
|---|---|
| `show ip bgp summary` | leaf1 (10.1.1.0) Estab **PfxRcd 1** · leaf2 (10.2.1.0) Estab **PfxRcd 2** |
| `show ip route` | 10.1.0.1/32 via Et1 present · 10.200.2.0/24 via Et2 present · **10.100.1.0/24 absent** |
| `show ip int br` | Et1, Et2, Lo0, Ma0 all up/up |
| `show lldp neighbors` | Et1 → leaf1, Et2 → leaf2 |

**No single device shows both cause and impact.** The cause is visible only on
leaf1; the impact is visible only from spine1 or above.

## Ruled out

**Peer 10.1.9.9 (AS 65999) — `Idle(NoIf)`.** Zero messages sent or received,
zero uptime, and `NoIf` means no interface or route toward the peer exists.
This session has never established and is unrelated to the impact. It is
stale configuration for a peer that does not exist.

**The fabric.** Both leaf1↔spine sessions Established ~2h22m. LLDP confirms
correct adjacencies on both ends. leaf2's equivalent host subnet is reachable
via both spines. Spine interfaces all up/up.

**Cable or link failure.** `show interfaces status` reports `disabled`, not
`notconnect`. The distinction is present in the data and rules out a physical
cause.

## Detection signature
The three tools disagree, and that disagreement is the diagnosis:

- **interfaces** — reports Et3 down. Correct, but says nothing about impact.
- **BGP** — reports two healthy sessions and one dead peer. The dead peer is
  the decoy; the healthy sessions conceal a withdrawn prefix.
- **route** — the only tool that shows the impact, and only by absence.

`PfxRcd 1` on spine1 is not wrong on its own. It is wrong only against a
comparison: leaf2's 2, or leaf1's own connected routes. **A count in isolation
carries no verdict.**

## Correct verdict
> Host1's subnet 10.100.1.0/24 is not advertised anywhere in the fabric because
> leaf1's Ethernet3 has been administratively disabled, removing the connected
> route that BGP was advertising. The fabric itself is healthy — both leaf1
> uplinks are established and leaf2's equivalent subnet is reachable. The
> 10.1.9.9 peer in Idle(NoIf) has never established, has no interface toward
> it, and is unrelated stale configuration.
>
> Suggested next check (read-only): confirm on leaf1 that Ethernet3's shutdown
> is configured rather than operational.

## Scoring — each criterion independently pass/fail
1. Names Ethernet3 on leaf1 as the cause.
2. Distinguishes administrative shutdown from a link or cable failure.
3. **Explicitly dismisses the 10.1.9.9 peer.** Silence is a fail, not a
   partial pass — the engineer would still have to go check it.
4. Cites the missing prefix (leaf1 connected routes, spine1 PfxRcd, or
   spine1's route table), not only the interface state.
5. Proposes a read-only next step.
6. Does **not** attribute the fault to the fabric, the spines, or leaf2.

## Known evidence gap
The end-to-end ping from host1 was not run. Impact is established from
control-plane evidence and the gateway interface's admin state, not from a
data-plane test. Worth closing before this case is used for scoring.

## Reset