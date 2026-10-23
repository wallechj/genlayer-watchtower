# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from dataclasses import dataclass


@allow_storage
@dataclass
class Monitor:
    owner: str
    name: str
    url: str
    alert_threshold: u256
    status: str  # unknown | up | down
    up_checks: u256
    down_checks: u256
    consecutive_failures: u256
    last_check: u256
    created_at: u256


@allow_storage
@dataclass
class Check:
    monitor_id: u256
    verdict: str  # up | down
    checked_at: u256


class Watchtower(gl.Contract):
    monitor_counter: u256
    check_counter: u256
    monitors: TreeMap[u256, Monitor]
    checks: TreeMap[u256, Check]

    def __init__(self):
        self.monitor_counter = u256(0)
        self.check_counter = u256(0)

    @gl.public.write
    def add_monitor(self, name: str, url: str, alert_threshold: u256) -> u256:
        if not name.strip():
            raise gl.vm.UserError("name is required")
        url = url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            raise gl.vm.UserError("url must start with http:// or https://")
        if alert_threshold < u256(1):
            raise gl.vm.UserError("alert_threshold must be at least 1")

        monitor_id = self.monitor_counter
        self.monitors[monitor_id] = Monitor(
            owner=str(gl.message.sender_address),
            name=name,
            url=url,
            alert_threshold=alert_threshold,
            status="unknown",
            up_checks=u256(0),
            down_checks=u256(0),
            consecutive_failures=u256(0),
            last_check=u256(0),
            created_at=gl.block.timestamp,
        )
        self.monitor_counter = monitor_id + u256(1)
        return monitor_id

    @gl.public.write
    def remove_monitor(self, monitor_id: u256) -> None:
        monitor = self.monitors[monitor_id]
        if str(gl.message.sender_address) != monitor.owner:
            raise gl.vm.UserError("only the monitor owner can remove it")
        del self.monitors[monitor_id]

    @gl.public.write
    def probe(self, monitor_id: u256) -> str:
        monitor = self.monitors[monitor_id]
        url = monitor.url  # storage is not visible inside the nondet block

        def probe_once() -> str:
            try:
                res = gl.nondet.web.get(url)
                code = int(res.status)
                if 200 <= code < 400:
                    body = res.body
                    if isinstance(body, bytes):
                        body = body.decode("utf-8", errors="ignore")
                    # a 200 with an empty/parked page is not "up"
                    if len(str(body).strip()) >= 50:
                        return "up"
                return "down"
            except Exception:
                # DNS failure, timeout, TLS error: the endpoint is not serving
                return "down"

        # Liveness is binary and reproducible across validators, so strict
        # equality is the right equivalence here: every honest validator that
        # reaches the same endpoint must produce the same one-word verdict.
        # If validators disagree (flapping endpoint, regional outage), the
        # transaction fails instead of recording a false attestation.
        verdict = gl.eq_principle.strict_eq(probe_once)

        check_id = self.check_counter
        self.checks[check_id] = Check(
            monitor_id=monitor_id,
            verdict=verdict,
            checked_at=gl.block.timestamp,
        )
        self.check_counter = check_id + u256(1)

        if verdict == "up":
            monitor.up_checks = monitor.up_checks + u256(1)
            monitor.consecutive_failures = u256(0)
        else:
            monitor.down_checks = monitor.down_checks + u256(1)
            monitor.consecutive_failures = monitor.consecutive_failures + u256(1)
        monitor.status = verdict
        monitor.last_check = gl.block.timestamp
        self.monitors[monitor_id] = monitor
        return verdict

    # ---------- views ----------

    @gl.public.view
    def get_monitor(self, monitor_id: u256) -> dict:
        m = self.monitors[monitor_id]
        total = m.up_checks + m.down_checks
        return {
            "id": int(monitor_id),
            "owner": m.owner,
            "name": m.name,
            "url": m.url,
            "alert_threshold": int(m.alert_threshold),
            "status": m.status,
            "up_checks": int(m.up_checks),
            "down_checks": int(m.down_checks),
            "total_checks": int(total),
            "consecutive_failures": int(m.consecutive_failures),
            "breaching": bool(m.consecutive_failures >= m.alert_threshold and total > u256(0)),
            "last_check": int(m.last_check),
            "created_at": int(m.created_at),
        }

    @gl.public.view
    def uptime_bps(self, monitor_id: u256) -> int:
        # Uptime in basis points (10000 = 100%). 0 when nothing has been probed yet.
        m = self.monitors[monitor_id]
        total = m.up_checks + m.down_checks
        if total == u256(0):
            return 0
        return int(m.up_checks * u256(10000) / total)

    @gl.public.view
    def get_check(self, check_id: u256) -> dict:
        c = self.checks[check_id]
        return {
            "id": int(check_id),
            "monitor_id": int(c.monitor_id),
            "verdict": c.verdict,
            "checked_at": int(c.checked_at),
        }

    @gl.public.view
    def get_monitor_count(self) -> int:
        return int(self.monitor_counter)

    @gl.public.view
    def get_check_count(self) -> int:
        return int(self.check_counter)
