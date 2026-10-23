# Watchtower

A GenLayer Intelligent Contract for decentralized uptime / SLA attestation.

The problem: "is this service up?" is usually answered by a centralized monitor (or the provider itself). If uptime determines payouts — SLA credits, agent-to-agent service agreements, on-call accountability — you want that answer to come from somewhere neutral and auditable.

Watchtower is that neutral party. Anyone registers a monitor (name + URL + alert threshold). Anyone can trigger a probe — it's a permissionless keeper model, no privileged operator. Each probe makes every GenLayer validator independently fetch the endpoint and reach consensus on a single verdict: `up` or `down`. Every probe is stored on-chain with a timestamp, so the full check history is an immutable audit trail. Uptime percentage (in basis points) and SLA-breach state are computed deterministically from that history.

## Why this needs GenLayer

A normal smart contract can't fetch a URL. A centralized monitor can, but then you're trusting the monitor. Watchtower has N independent validators (each potentially running a different model and network path) agree on what they observed, and the agreement itself is what's stored. No single prober can fake an "up".

## How consensus is used

`probe` is the heart of the contract. Each validator runs `probe_once`:

1. `gl.nondet.web.get(url)` — real HTTP fetch
2. Verdict logic: `up` only on HTTP 2xx/3xx **with a non-trivial body** (a 200 serving an empty or parked page counts as down); anything else — 4xx/5xx, DNS failure, timeout, TLS error — is `down`

Consensus uses `gl.eq_principle.strict_eq`. Deliberately not comparative: liveness is binary and reproducible, so every honest validator observing the same endpoint must produce the same one-word verdict. Strict equality is the strongest claim this oracle can make.

The flip side is honest too: if validators genuinely disagree (flapping endpoint, regional routing differences), the transaction fails consensus instead of recording a possibly-false attestation. The oracle refuses to attest rather than attest something disputed. That's a feature, not a bug — it means a recorded `up`/`down` actually meant something.

All bookkeeping outside the consensus block is deterministic: per-verdict counters, consecutive-failure streak, last-check timestamp, and the append-only check log.

## Contract API

| Method | Type | What it does |
|---|---|---|
| `add_monitor(name, url, alert_threshold)` | write | Register an endpoint. Anyone can register. Returns monitor id. |
| `probe(monitor_id)` | write | Trigger a consensus probe. Permissionless — anyone can call. Returns `up`/`down`. |
| `remove_monitor(monitor_id)` | write | Owner-only. |
| `get_monitor(monitor_id)` | view | Full monitor state incl. counters and `breaching` flag. |
| `uptime_bps(monitor_id)` | view | Uptime in basis points (10000 = 100%). 0 before the first probe. |
| `get_check(check_id)` / `get_monitor_count` / `get_check_count` | view | Audit trail reads. |

SLA breach = `consecutive_failures >= alert_threshold` (exposed as `breaching` in `get_monitor`). Set the threshold to your SLA's tolerance: e.g. threshold 3 with probes every 5 minutes ≈ 15 minutes of downtime before breach.

## Try it in GenLayer Studio

1. Open [studio.genlayer.com](https://studio.genlayer.com), paste `contracts/watchtower.py`, deploy.
2. `add_monitor("example", "https://example.com", 3)` → returns `0`.
3. `add_monitor("dead", "https://no-such-domain-xyz12345.invalid", 2)` → returns `1`.
4. `probe(0)` → `"up"`. `probe(1)` → `"down"` (DNS failure → down).
5. `probe(1)` again → second consecutive failure → `get_monitor(1).breaching == true`.
6. `uptime_bps(0)` → `10000`. `get_check(0)` → the stored attestation.

Full click-by-click: see `test_flow.md`.

## Design notes and limits

- **Probes are point-in-time.** The chain can't cron — something has to call `probe`. That's the keeper model: anyone (a script, another contract, a community member) can keep a monitor fresh. Stale monitors just show an old `last_check`; they never pretend to be fresh.
- **Empty 200s count as down.** Parking pages and captive portals return 200. The 50-byte body floor is a heuristic, documented here so it can be tuned.
- **Regional disagreement fails closed.** See "How consensus is used" — no attestation on dispute.
- **No alerting pipeline.** The contract records and attests; paging a human is off-chain's job (watch `breaching`).
- Pairs well with a subjective-consensus contract (like my BountyTriage): this one shows the `strict_eq` side of GenLayer, where the fact being attested is objective.

## License

MIT
