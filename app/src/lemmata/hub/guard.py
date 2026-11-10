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


def _cache_path():
    from lemmata.hub.config import default_data_dir
    return default_data_dir() / "hub" / "tailscale.json"


def _interface_ips():
    """Tailscale addresses read straight from the network interfaces (`ifconfig`), no Tailscale CLI needed.
    Works under launchd, where the GUI app's CLI may not answer."""
    out = ""
    for cmd in (["/sbin/ifconfig"], ["ifconfig"], ["ip", "-o", "addr"]):
        try:
            out = subprocess.run(cmd, capture_output=True, timeout=5, stdin=subprocess.DEVNULL).stdout.decode("utf-8", "replace")
        except (OSError, subprocess.TimeoutExpired):
            continue
        if out:
            break
    ips = set()
    for tok in out.replace("/", " ").split():
        tok = tok.split("%")[0]
        try:
            ip = ipaddress.ip_address(tok)
        except ValueError:
            continue
        if ip in TS4 or ip in TS6:
            ips.add(str(ip))
    return ips


def _cli_info():
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


def tailscale_info():
    """({ips}, {names}) of this machine. Order: the Tailscale CLI (names + IPs); else the interface
    addresses plus the names remembered from the last successful CLI call (e.g. by `lemmata hub status`)."""
    ips, names = _cli_info()
    cache = _cache_path()
    if ips:
        try:
            if cache.parent.is_dir():
                cache.write_text(json.dumps({"ips": sorted(ips), "names": sorted(names)}))
        except OSError:
            pass
        return ips, names
    ips = _interface_ips()
    if ips:
        try:
            names = {n for n in json.loads(cache.read_text()).get("names", []) if isinstance(n, str)}
        except (OSError, ValueError):
            names = set()
    return ips, names


def _hostname(hostport):
    h = hostport.strip().lower()
    if h.startswith("["):
        return h[1:h.find("]")] if "]" in h else h
    return h.rsplit(":", 1)[0] if h.count(":") == 1 else h


PUBLIC_SCHEMES = ["https://"]  # browser tests add "http://" to reach a loopback hub; production accepts https only


def public_host(url):
    """Host of a public URL ('https://host' or 'https://host:port'), else None. Only https is accepted."""
    u = (url or "").strip().lower().rstrip("/")
    for sch in PUBLIC_SCHEMES:
        if u.startswith(sch):
            rest = u[len(sch):]
            if rest and "/" not in rest and "@" not in rest and " " not in rest:
                return rest
    return None


class Guard:
    def __init__(self, extra_hosts=(), detect=True, public_url=None):
        ips, names = tailscale_info() if detect else (set(), set())
        self.hosts = {"localhost", "127.0.0.1", "::1"} | {i.lower() for i in ips} | names | {h.lower() for h in extra_hosts}
        self.public = public_host(public_url)   # 'host' or 'host:port' the tunnel serves over https
        if self.public:
            self.hosts.add(_hostname(self.public))

    def is_public(self, host_header):
        """True when the request came in through the public URL (the tunnel), not over Tailscale or loopback."""
        return bool(self.public) and bool(host_header) and _hostname(host_header) == _hostname(self.public)

    def refresh(self):
        """Re-detect Tailscale addresses/names (it may have come up after the hub started)."""
        ips, names = tailscale_info()
        self.hosts |= {i.lower() for i in ips} | names

    def host_ok(self, header):
        return bool(header) and _hostname(header) in self.hosts

    def origin_ok(self, origin, port=None):
        """No Origin = fine; otherwise exactly http://<allowed host>:<port> (https is never used by the hub)."""
        if origin is None:
            return True
        o = origin.strip().lower()
        if self.public and any(o == sch + self.public for sch in PUBLIC_SCHEMES):
            return True
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
