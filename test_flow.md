# Test flow (GenLayer Studio, hosted)

Paste `contracts/watchtower.py` into the Studio editor and deploy. One account is
enough; a second account is useful for the access-control check.

## 1. Register monitors (account A)

`add_monitor("example", "https://example.com", 3)` → expect `0`.
`add_monitor("dead", "https://no-such-domain-xyz12345.invalid", 2)` → expect `1`.

Negative checks:
- `add_monitor("bad", "not-a-url", 3)` → `UserError: url must start with http:// or https://`
- `add_monitor("bad", "https://example.com", 0)` → `UserError: alert_threshold must be at least 1`

## 2. Probe the healthy endpoint

`probe(0)` — validators fetch https://example.com and must agree. Expect `"up"`.
`get_monitor(0)` → status `up`, up_checks `1`, consecutive_failures `0`, breaching `false`.
`uptime_bps(0)` → `10000`.

## 3. Probe the dead endpoint

`probe(1)` — DNS resolution fails on every validator. Expect `"down"`.
`get_monitor(1)` → status `down`, down_checks `1`, consecutive_failures `1`, breaching `false` (threshold is 2).
`probe(1)` again → consecutive_failures `2` → `get_monitor(1).breaching == true`.
`uptime_bps(1)` → `0`.

## 4. Audit trail

`get_check_count()` → `3` (one up probe + two down probes).
`get_check(0)` → `{monitor_id: 0, verdict: "up", checked_at: <ts>}`.
`get_check(1)` → `{monitor_id: 1, verdict: "down", ...}`.

## 5. Access control and removal (account B, then A)

`remove_monitor(0)` as account B → `UserError: only the monitor owner can remove it`.
`remove_monitor(1)` as account A → succeeds; `monitor_status(1)` → `"removed"`.
`probe(1)` afterwards → `UserError: monitor was removed`.
