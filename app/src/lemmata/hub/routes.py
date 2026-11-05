"""Hub HTTP server: guard, auth, hub API, MCP and per-project prefix routing on top of server.Handler."""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from lemmata import __version__
from lemmata.engine import tree as _tree
from lemmata.server import WEB, ApiError, Handler, _map_exc, parse_length

from .auth import Auth, cookie_header, parse_cookie, COOKIE
from .config import Config, DataDir
from .github import GitHub, GitHubError, scrub
from .overleaf import OverleafError
from .guard import Guard, peer_ok
from .projects import MAX_ZIP, HubContext, Manager, ProjectError, mask
from .sync import SyncLoop

HUB_WEB = WEB / "hub"
PUBLIC_API = {("GET", "/api/hub/status"), ("POST", "/api/hub/pair")}
PROJECT_RE = re.compile(r"^/p/([a-z0-9-]{1,64})(/.*)?$")
CSP = ("default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://avatars.githubusercontent.com; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'")
MAX_BODY = 64 * 1024


class Hub:
    """Everything the handler needs, built once per server."""

    def __init__(self, data_dir=None, port=None, extra_hosts=(), detect_tailscale=True, sync_interval=None):
        self.data = DataDir(data_dir).ensure()
        self.cfg = Config(self.data)
        c = self.cfg.load()
        self.port = port if port is not None else c["port"]
        self.guard = Guard(list(c.get("allow_hosts") or []) + list(extra_hosts), detect=detect_tailscale)
        self.auth = Auth(self.data)
        self.gh = GitHub(self.data, self.cfg)
        self.mgr = Manager(self.data, self.cfg, self.gh)
        self.ctx = HubContext(self.mgr)
        self.sync_interval = sync_interval if sync_interval is not None else c.get("sync_interval", 300)
        self.lock = threading.Lock()
        # the engine's own git calls must not read user/system git config or run LFS filters inside cloned repos
        _tree.GIT_ENV_EXTRA.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_LFS_SKIP_SMUDGE": "1"})


class HubServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def verify_request(self, request, client_address):  # closed immediately, before any bytes are read
        return peer_ok(client_address[0])


class HubHandler(Handler):
    hub: Hub = None
    timeout = 30  # seconds of silence before a connection is dropped (slow-loris); the zip stream gets longer

    def send_error(self, code, message=None, explain=None):
        """Any method/protocol error the stdlib would answer with HTML: JSON + CSP instead."""
        self.close_connection = True
        try:
            body = json.dumps({"error": {"code": "method_not_allowed" if code in (405, 501) else "bad_request",
                                         "message": "method not allowed" if code in (405, 501) else (message or "bad request")}}).encode()
            self.send_response(405 if code == 501 else code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except OSError:
            pass

    def do_PATCH(self):
        self._dispatch("PATCH")

    # --- guards
    def _host_ok(self):
        return self.hub.guard.host_ok(self.headers.get("Host"))

    def _origin_ok(self):
        return self.hub.guard.origin_ok(self.headers.get("Origin"), self.hub.port)

    def _send(self, status, body, ctype, extra=None):
        extra = dict(extra or {})
        extra.setdefault("Content-Security-Policy", CSP)
        extra.setdefault("Referrer-Policy", "no-referrer")
        super()._send(status, body, ctype, extra)

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_HEAD(self):
        self._dispatch("GET")

    def _error(self, status, code, message):
        if status >= 400 and self.command in ("POST", "DELETE"):
            self.close_connection = True
        self._json({"error": {"code": code, "message": message}}, status)

    # --- auth
    def _session(self):
        """(device, via) where via is 'bearer' or 'cookie'."""
        h = self.headers.get("Authorization") or ""
        if h.lower().startswith("bearer "):
            dev = self.hub.auth.lookup(h[7:].strip())
            return (dev, "bearer") if dev else (None, None)
        dev = self.hub.auth.lookup(parse_cookie(self.headers.get("Cookie")))
        return (dev, "cookie") if dev else (None, None)

    def _csrf(self, via, ctype_ok=True):
        """State-changing requests: JSON (or zip) content type, and with a cookie a present, allowed Origin."""
        if via == "cookie":
            if self.headers.get("Origin") is None or not self._origin_ok():
                raise ApiError(403, "forbidden", "origin not allowed")
        elif not self._origin_ok():
            raise ApiError(403, "forbidden", "origin not allowed")

    def _dispatch(self, method):
        self.app = None
        self.triage_by = None
        try:
            if self.headers.get("Tailscale-Funnel-Request") is not None:  # a request that came in through Tailscale Funnel
                raise ApiError(403, "forbidden", "public (Funnel) access is not allowed")
            if not self._host_ok():
                raise ApiError(403, "forbidden", "host not allowed")
            url = urlsplit(self.path)
            path = unquote(url.path)
            q = {k: v[-1] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
            hub = self.hub
            # --- public: status, pairing, static files of the pairing / sign-in page
            if (method, path) in PUBLIC_API:
                return self._hub_api(method, path, q, None, public=True)
            if method == "GET" and not path.startswith(("/api/", "/p/", "/mcp")):
                return self._hub_static(path)
            # --- everything else needs a session
            dev, via = self._session()
            if path == "/mcp":
                if method == "GET":
                    raise ApiError(405, "method_not_allowed", "use POST")
                if method != "POST":
                    raise ApiError(405, "method_not_allowed", "use POST")
                if via != "bearer":
                    raise ApiError(401, "unauthorized", "Bearer token required")
                if not self._origin_ok():
                    raise ApiError(403, "forbidden", "origin not allowed")
                return self._mcp(dev)
            if not dev:
                raise ApiError(401, "unauthorized", "pair this device first")
            if method != "GET":
                self._csrf(via)
            if path.startswith("/api/hub/"):
                return self._hub_api(method, path, q, via)
            m = PROJECT_RE.match(path)
            if m:
                self.triage_by = "ui:%s" % dev["device_id"]
                return self._project(method, m.group(1), m.group(2), q)
            if path.startswith("/api/"):
                raise ApiError(404, "not_found", "unknown route")
            raise ApiError(404, "not_found", "not found")
        except TimeoutError:
            self.close_connection = True
        except ApiError as e:
            self._error(e.status, e.code, e.message)
        except ProjectError as e:
            self._error(e.status, e.code, e.message)
        except (GitHubError, OverleafError) as e:
            self._error(e.status, e.code, e.message)
        except Exception as e:
            m = _map_exc(e)
            if m:
                self._error(m.status, m.code, m.message)
            else:
                self._error(500, "internal", mask(scrub("%s: %s" % (type(e).__name__, e), self.hub.gh.token(), self.hub.mgr.ol.token()))[:300])

    # --- static
    def _hub_static(self, path):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        for root in (HUB_WEB, WEB):  # hub pages first; shared css/vendor files are public code, not data
            p = (root / rel).resolve()
            if "\x00" not in rel and p.is_relative_to(root.resolve()) and p.is_file() and not (root is WEB and rel == "index.html"):
                return self._static(path, root)
        raise ApiError(404, "not_found", "not found")

    # --- body helpers
    def _json_body(self):
        return self._body()  # JSON content type, 64 KB cap, Origin check (server.Handler)

    # --- MCP
    def _mcp(self, dev):
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise ApiError(400, "bad_request", "Content-Type must be application/json")
        n = parse_length(self.headers.get("Content-Length"))
        if n > MAX_BODY:
            raise ApiError(413, "too_large", "request body over 64 KB")
        raw = self.rfile.read(n)
        try:
            from lemmata import mcp  # lazy import
        except ImportError:
            raise ApiError(501, "not_implemented", "MCP is not available in this build")
        out = mcp.handle(raw.decode("utf-8", "replace"), HubContext(self.hub.mgr, device=dev["name"], device_id=dev["device_id"]))
        status, resp = out if isinstance(out, tuple) else (200 if out is not None else 202, out)
        if resp is None or resp == "":
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if not isinstance(resp, (str, bytes)):
            resp = json.dumps(resp, ensure_ascii=False)
        self._send(status, resp if isinstance(resp, bytes) else resp.encode("utf-8"), "application/json; charset=utf-8")

    # --- hub API
    def _hub_api(self, method, path, q, via, public=False):
        hub = self.hub
        r = path[len("/api/hub"):]
        if (method, r) == ("GET", "/status"):
            dev, _ = self._session()
            gh = hub.gh.stored()
            c = hub.cfg.load()
            return self._json({"ok": True, "hub": True, "version": __version__, "authenticated": bool(dev),
                               "paired": bool(hub.auth.devices()), "github_connected": bool(gh),
                               "github_configured": bool(c.get("github_client_id")),
                               "overleaf_configured": hub.mgr.ol.configured(),
                               "owner": c.get("owner") if dev else None,
                               "user": hub.gh.user_public() if dev else None,
                               "device": dev["name"] if dev else None})
        if (method, r) == ("POST", "/pair"):
            body = self._json_body()
            code, device = body.get("code"), body.get("device", "device")
            if not isinstance(code, str) or not isinstance(device, str):
                raise ApiError(400, "bad_request", "code and device must be text")
            if not hub.auth.check_code(code):
                raise ApiError(403, "bad_code", "That pairing code is wrong or expired. Run `lemmata hub pair-code` on the Mac mini.")
            token, did = hub.auth.new_device(device)
            return self._send(200, json.dumps({"token": token, "device_id": did}).encode(), "application/json; charset=utf-8",
                              {"Set-Cookie": cookie_header(token)})
        if (method, r) == ("POST", "/session/logout"):
            self._body()
            return self._send(200, b'{"ok": true}', "application/json; charset=utf-8",
                              {"Set-Cookie": "%s=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0" % COOKIE})
        # --- GitHub
        if (method, r) == ("POST", "/github/start"):
            self._body()
            return self._json(hub.gh.start())
        if (method, r) == ("GET", "/github/poll"):
            return self._json(hub.gh.poll())
        if (method, r) == ("POST", "/github/logout"):
            self._body()
            hub.gh.logout()
            return self._json({"ok": True})
        if (method, r) == ("GET", "/github/repos"):
            return self._json(hub.gh.repos(q.get("q", "")))
        # --- Overleaf token (never echoed back)
        if r == "/overleaf/token":
            if method == "PUT":
                body = self._body()
                hub.mgr.ol.save(body.get("token"))
                return self._json({"configured": True})
            if method == "DELETE":
                hub.mgr.ol.remove()
                return self._json({"configured": False})
            raise ApiError(405, "method_not_allowed", "method not allowed")
        # --- projects
        if r == "/projects":
            if method == "GET":
                return self._json({"projects": hub.mgr.list()})
            if method == "POST":
                body = self._body()
                return self._json(hub.mgr.create(body.get("name"), body.get("code_repo"), body.get("branch"), body.get("paper_overleaf")), 201)
        m = re.match(r"^/projects/([a-z0-9-]{1,64})(/paper|/sync|/paper-source)?$", r)
        if m:
            pid, sub = m.group(1), m.group(2)
            hub.mgr.root(pid)  # 404 before any body is read
            if sub is None and method == "DELETE":
                return self._json(hub.mgr.delete(pid))
            if sub == "/sync" and method == "POST":
                self._body()
                return self._json(hub.mgr.sync(pid))
            if sub == "/paper-source" and method == "POST":
                body = self._body()
                return self._json(hub.mgr.set_paper_source(pid, body.get("kind"), body.get("project")))
            if sub == "/paper" and method == "POST":
                return self._json(self._paper(pid))
            if sub is None and method == "GET":
                return self._json(hub.mgr.summary(pid))
            if sub is None and method == "PATCH":
                body = self._body()
                if "online_refs" not in body:
                    raise ApiError(400, "bad_request", "nothing to change (online_refs)")
                return self._json(hub.mgr.set_online_refs(pid, body["online_refs"]))
            raise ApiError(405, "method_not_allowed", "method not allowed")
        raise ApiError(404, "not_found", "unknown route")

    def _paper(self, pid):
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/zip":
            raise ApiError(400, "bad_request", "Content-Type must be application/zip")
        if not self._origin_ok():
            raise ApiError(403, "forbidden", "origin not allowed")
        n = parse_length(self.headers.get("Content-Length"))
        if n <= 0:
            raise ApiError(400, "bad_request", "empty upload")
        if n > MAX_ZIP:
            raise ApiError(413, "too_large", "zip over 100 MB")
        self.connection.settimeout(120)  # the upload may be slow; individual reads still time out
        tmp = self.hub.data.tmp / ("zip-" + secrets.token_hex(6))
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as f:
                left = n
                while left:
                    chunk = self.rfile.read(min(1024 * 1024, left))
                    if not chunk:
                        raise ApiError(400, "bad_request", "upload ended early")
                    f.write(chunk)
                    left -= len(chunk)
            self.connection.settimeout(self.timeout)
            return self.hub.mgr.upload(pid, tmp)
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass

    # --- per-project prefix routing: /p/<pid>/...  ->  the existing single-project handlers
    def _project(self, method, pid, rest, q):
        if rest is None:
            self.send_response(301)
            self.send_header("Location", "/p/%s/" % pid)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.app = self.hub.mgr.app(pid)  # NotFound -> 404
        if method not in ("GET", "POST"):
            raise ApiError(405, "method_not_allowed", "method not allowed")
        if rest.startswith("/api/"):
            return self._api(method, rest, q)
        if method == "GET":
            return self._static(rest)  # relative asset URLs resolve under /p/<pid>/
        raise ApiError(405, "method_not_allowed", "method not allowed")


class HubServer6(HubServer):
    import socket as _s
    address_family = _s.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(self._s.IPPROTO_IPV6, self._s.IPV6_V6ONLY, 1)
        super().server_bind()


def make_hub_server(hub: Hub, host="127.0.0.1", port=None):
    handler = type("BoundHubHandler", (HubHandler,), {"hub": hub})
    cls = HubServer6 if ":" in host else HubServer
    srv = cls((host, hub.port if port is None else port), handler)
    hub.port = srv.server_address[1]
    srv.hub = hub
    return srv


def make_hub_servers(hub: Hub, hosts):
    """One socket per address (loopback + Tailscale IPs). The port is fixed by the first socket when it was 0."""
    servers = []
    for h in hosts:
        try:
            servers.append(make_hub_server(hub, host=h, port=hub.port))
        except OSError as e:
            if h in ("::1",) or ":" in h:  # IPv6 may be absent; IPv4 sockets are required
                continue
            for s in servers:
                s.server_close()
            raise OSError("cannot bind %s:%s: %s" % (h, hub.port, e))
    return servers


def start_background(hub):
    loop = SyncLoop(hub.mgr, hub.sync_interval)
    loop.start()
    return loop
