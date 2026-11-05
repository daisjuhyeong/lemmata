"""Network guard: peer-address allowlist, Host/Origin allowlist, Tailscale detection."""
from __future__ import annotations

import ipaddress
import json
import os
import shutil
import subprocess

TS4 = ipaddress.ip_network("100.64.0.0/10")
TS6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")
TAILSCALE_APP = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"


def peer_ok(addr):
    """True for loopback and Tailscale addresses only."""
    try:
        ip = ipaddress.ip_address(addr.split("%")[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_loopback or ip in TS4 or ip in TS6


def tailscale_info():
    """({ips}, {names}) of this machine from `tailscale status --json`; empty sets when unavailable."""
    cli = shutil.which("tailscale") or (TAILSCALE_APP if os.path.exists(TAILSCALE_APP) else None)
    if not cli:
        return set(), set()
    try:
        p = subprocess.run([cli, "status", "--json"], capture_output=True, timeout=10, stdin=subprocess.DEVNULL)
        me = json.loads(p.stdout.decode("utf-8", "replace")).get("Self") or {}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return set(), set()
    ips = {i for i in me.get("TailscaleIPs", []) if isinstance(i, str)}
    names = set()
    dns = (me.get("DNSName") or "").rstrip(".").lower()
    if dns:
        names.add(dns)
        names.add(dns.split(".")[0])
    if me.get("HostName"):
        names.add(str(me["HostName"]).lower())
    return ips, names


def _hostname(hostport):
    h = hostport.strip().lower()
    if h.startswith("["):
        return h[1:h.find("]")] if "]" in h else h
    return h.rsplit(":", 1)[0] if h.count(":") == 1 else h


class Guard:
    def __init__(self, extra_hosts=(), detect=True):
        ips, names = tailscale_info() if detect else (set(), set())
        self.hosts = {"localhost", "127.0.0.1", "::1"} | {i.lower() for i in ips} | names | {h.lower() for h in extra_hosts}

    def host_ok(self, header):
        return bool(header) and _hostname(header) in self.hosts

    def origin_ok(self, origin, port=None):
        """No Origin = fine; otherwise exactly http://<allowed host>:<port> (https is never used by the hub)."""
        if origin is None:
            return True
        o = origin.strip().lower()
        if not o.startswith("http://"):
            return False
        rest = o[len("http://"):]
        if "/" in rest or not self.host_ok(rest):
            return False
        if port is not None:
            h = rest
            hp = h[h.rfind("]") + 1:] if h.startswith("[") else (":" + h.rsplit(":", 1)[1] if h.count(":") == 1 else "")
            if hp != ":%d" % port:
                return False
        return True


def bind_addresses():
    """Loopback plus this machine's Tailscale IPs; never 0.0.0.0."""
    ips, _ = tailscale_info()
    out = ["127.0.0.1"]
    out += sorted(i for i in ips if ":" not in i)
    out += ["::1"] + sorted(i for i in ips if ":" in i)
    return out


def funnel_active(port):
    """True if `tailscale funnel status` shows this port exposed to the internet."""
    cli = shutil.which("tailscale") or (TAILSCALE_APP if os.path.exists(TAILSCALE_APP) else None)
    if not cli:
        return False
    try:
        p = subprocess.run([cli, "funnel", "status"], capture_output=True, timeout=10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return False
    out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
    low = out.lower()
    return "funnel on" in low and (str(port) in out)
