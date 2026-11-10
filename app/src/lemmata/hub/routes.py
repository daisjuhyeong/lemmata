"""Hub HTTP server: guard, auth, hub API, MCP and per-project prefix routing on top of server.Handler."""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
import time
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
PUBLIC_API = {("GET", "/api/hub/status"), ("POST", "/api/hub/pair"), ("POST", "/api/hub/login/start"), ("GET", "/api/hub/login/poll")}
EVENTS = {"tutorial_shown", "tutorial_done", "tutorial_skipped", "view_open", "view_switch", "project_created", "project_opened", "claim_confirmed",
          "claim_rejected", "claim_linked", "feedback_added", "task_done", "ask", "digest_sent", "signup", "useful_yes", "useful_no"}
MAX_EVENTS_FILE = 20 * 1024 * 1024
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
        self.guard = Guard(list(c.get("allow_hosts") or []) + list(extra_hosts), detect=detect_tailscale, public_url=c.get("public_url"))
        self.rate = {}   # bucket -> [timestamps]; small in-memory limiter for the public sign-in endpoints
        self.checked = {}  # login -> time of the last "is the GitHub sign-in still valid" check
        self.auth = Auth(self.data)
        self.gh = GitHub(self.data, self.cfg)
        self.mgr = Manager(self.data, self.cfg, self.gh)
        self.ctx = HubContext(self.mgr)
        self.sync_interval = sync_interval if sync_interval is not None else c.get("sync_interval", 300)
        self.lock = threading.Lock()
        self.ev_lock = threading.Lock()
        # the engine's own git calls must not read user/system git config or run LFS filters inside cloned repos
        _tree.GIT_ENV_EXTRA.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_LFS_SKIP_SMUDGE": "1"})


    # --- helpers for the public site
    def public_mode(self):
        return bool(self.guard.public)

    def allow(self, bucket, limit, per=60):
        """True if this bucket has had fewer than `limit` hits in the last `per` seconds."""
        now = time.time()
        with self.lock:
            hits = [t for t in self.rate.get(bucket, []) if now - t < per]
            ok = len(hits) < limit
            if ok:
                hits.append(now)
            self.rate[bucket] = hits
        return ok

    def log_event(self, user, event, **kw):
        """One line per event in hub/events.jsonl. The user is stored as a short hash, never as a name."""
        import hashlib
        rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "u": hashlib.sha256(("lemmata-ab:" + (user or "?").lower()).encode()).hexdigest()[:12],
               "e": event}
        rec.update({k: v for k, v in kw.items() if v is not None})
        with self.ev_lock:
            p = self.data.events_path
            try:
                if p.exists() and p.stat().st_size > MAX_EVENTS_FILE:
                    return
                fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except OSError:
                pass

    def ab_summary(self):
        """Per start view: people, and how many of them got to each milestone."""
        from .github import VARIANTS
        users = {v: set() for v in VARIANTS}
        marks = {v: {} for v in VARIANTS}
        opens = {v: {} for v in VARIANTS}
        try:
            lines = self.data.events_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        days = {}
        for ln in lines:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            v = r.get("v")
            if v not in users:
                continue
            users[v].add(r["u"])
            marks[v].setdefault(r["e"], set()).add(r["u"])
            days.setdefault((v, r["u"]), set()).add(r["t"][:10])
            if r["e"] == "view_open" and r.get("view"):
                opens[v][r["view"]] = opens[v].get(r["view"], 0) + 1
        out = []
        for v in VARIANTS:
            n = len(users[v])
            g = lambda e: len(marks[v].get(e, ()))
            out.append({"variant": v, "users": n, "created_project": g("project_created"), "confirmed_a_claim": g("claim_confirmed"),
                        "added_feedback": g("feedback_added"), "asked": g("ask"), "switched_view": g("view_switch"),
                        "came_back_another_day": sum(1 for (vv, u), d in days.items() if vv == v and len(d) > 1),
                        "useful_yes": g("useful_yes"), "useful_no": g("useful_no"), "views_opened": opens[v]})
        return {"variants": out, "events": len(lines), "note": "Counts are people, not clicks. With few users the differences are not significant."}


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

    def _user(self, dev):
        """GitHub login a session acts as: the one it signed in with, or the hub owner for paired devices (private hub)."""
        return (dev or {}).get("user") or self.hub.cfg.load().get("owner")

    def _is_admin(self, dev):
        o = self.hub.cfg.load().get("owner")
        return bool(dev) and bool(o) and (self._user(dev) or "").lower() == o.lower()

    def _via_public(self):
        return self.hub.guard.is_public(self.headers.get("Host"))

    def _own(self, pid, dev):
        self.hub.mgr.root(pid)   # NotFound for an unknown id
        if not self.hub.mgr.owns(pid, self._user(dev)):
            raise ApiError(404, "not_found", "unknown project")   # same answer as a project that does not exist

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
            if self.headers.get("Tailscale-Funnel-Request") is not None and not self.hub.public_mode():
                # a request that came in through Tailscale Funnel while the hub is private (no public_url configured)
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
            if dev and self._via_public() and not dev.get("user"):
                dev, via = None, None   # pairing-code sessions are for the private hub only; the public site needs a GitHub sign-in
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
                raise ApiError(401, "unauthorized", "Sign in to continue." if self._via_public() else "pair this device first")
            if method != "GET":
                self._csrf(via)
            if path.startswith("/api/hub/"):
                return self._hub_api(method, path, q, via, dev=dev)
            m = PROJECT_RE.match(path)
            if m:
                self._own(m.group(1), dev)
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
        out = mcp.handle(raw.decode("utf-8", "replace"), HubContext(self.hub.mgr, device=dev["name"], device_id=dev["device_id"], user=self._user(dev)))
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
    def _hub_api(self, method, path, q, via, public=False, dev=None):
        hub = self.hub
        r = path[len("/api/hub"):]
        c = hub.cfg.load()
        pub = self._via_public()
        if (method, r) == ("GET", "/status"):
            dev, _ = self._session()
            if dev and pub and not dev.get("user"):
                dev = None
            user = self._user(dev) if dev else None
            acct = hub.gh.user_public(user) if dev else None
            if acct and time.time() - hub.checked.get(user.lower(), 0) > 600:   # at most every 10 minutes per person
                hub.checked[user.lower()] = time.time()
                if hub.gh.check(user) is False:
                    acct = hub.gh.user_public(user)
            st = {"ok": True, "hub": True, "version": __version__, "authenticated": bool(dev),
                  "mode": "public" if pub else "private", "public_url": c.get("public_url") if dev and self._is_admin(dev) else None,
                  "signup": c.get("signup", "owner") if pub else None,
                  "paired": bool(dev) if pub else bool(hub.auth.devices()), "github_connected": bool(acct) if dev else (False if pub else bool(hub.gh.stored())),
                  "github_configured": bool(c.get("github_client_id")),
                  "github_needs_reauth": bool(acct and acct.get("needs_reauth")),
                  "owner": c.get("owner") if dev else None, "is_admin": self._is_admin(dev),
                  "user": acct, "device": dev["name"] if dev else None,
                  "start_view": (acct or {}).get("view") or (acct or {}).get("variant"), "variant": (acct or {}).get("variant")}
            if hub.mgr.overleaf_on() and not pub:
                st["overleaf_configured"] = hub.mgr.ol.configured()
            return self._json(st)
        if (method, r) == ("POST", "/pair"):
            if pub:
                raise ApiError(404, "not_found", "Pairing codes are for the private hub. Sign in with GitHub instead.")
            body = self._json_body()
            code, device = body.get("code"), body.get("device", "device")
            if not isinstance(code, str) or not isinstance(device, str):
                raise ApiError(400, "bad_request", "code and device must be text")
            if not hub.auth.check_code(code):
                raise ApiError(403, "bad_code", "That pairing code is wrong or expired. Run `lemmata hub pair-code` on the Mac mini.")
            token, did = hub.auth.new_device(device)
            return self._send(200, json.dumps({"token": token, "device_id": did}).encode(), "application/json; charset=utf-8",
                              {"Set-Cookie": cookie_header(token)})
        # --- public site: sign in with GitHub, no pairing code. The browser holds a random flow id until GitHub approves.
        if (method, r) == ("POST", "/login/start"):
            if not hub.public_mode():
                raise ApiError(404, "not_found", "This hub is private. Pair this device with a code instead.")
            if self.headers.get("Origin") is None or not self._origin_ok():
                raise ApiError(403, "forbidden", "origin not allowed")
            body = self._json_body()
            if not hub.allow("login", 30):
                raise ApiError(429, "busy", "Too many sign-ins right now. Try again in a minute.")
            flow = "web_" + secrets.token_urlsafe(24)
            out = hub.gh.start(flow, private=body.get("private_repos", True) is not False)
            out["flow"] = flow
            return self._json(out)
        if (method, r) == ("GET", "/login/poll"):
            flow = q.get("flow", "")
            if not hub.public_mode() or not flow.startswith("web_") or len(flow) > 80:
                raise ApiError(404, "not_found", "unknown sign-in")
            if not hub.allow("poll:" + flow, 30):
                raise ApiError(429, "busy", "Slow down.")
            res = hub.gh.poll(flow)
            if res.get("state") != "ok":
                return self._json(res)
            login = res["login"]
            first = not any((d.get("user") or "").lower() == login.lower() for d in hub.auth._load()["devices"])
            token, _did = hub.auth.new_device("Browser", user=login, kind="web")
            if first:
                hub.log_event(login, "signup", v=res["user"].get("variant"))
            return self._send(200, json.dumps({"state": "ok", "user": res["user"]}).encode(), "application/json; charset=utf-8",
                              {"Set-Cookie": cookie_header(token, secure=pub)})
        user = self._user(dev)
        if (method, r) == ("POST", "/session/logout"):
            self._body()
            if dev.get("kind") == "web":
                hub.auth.revoke(dev["device_id"])
            return self._send(200, b'{"ok": true}', "application/json; charset=utf-8",
                              {"Set-Cookie": "%s=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0" % COOKIE})
        # --- GitHub (signed-in session): connect, or reconnect in place when GitHub stopped accepting the saved sign-in
        if (method, r) == ("POST", "/github/start"):
            body = self._body()
            flow = "dev_" + dev["device_id"] if dev.get("user") else "owner"
            return self._json(hub.gh.start(flow, private=body.get("private_repos", True) is not False, expect=dev.get("user")))
        if (method, r) == ("GET", "/github/poll"):
            res = hub.gh.poll("dev_" + dev["device_id"] if dev.get("user") else "owner")
            if res.get("state") == "ok":
                hub.checked[(res.get("login") or "").lower()] = time.time()
            res.pop("login", None)
            return self._json(res)
        if (method, r) == ("POST", "/github/logout"):
            self._body()
            if dev.get("user"):   # public site: "sign out" ends this browser's session; the account and its projects stay
                hub.auth.revoke(dev["device_id"])
                return self._send(200, b'{"ok": true}', "application/json; charset=utf-8",
                                  {"Set-Cookie": "%s=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0" % COOKIE})
            hub.gh.logout()
            return self._json({"ok": True})
        if (method, r) == ("GET", "/github/repos"):
            return self._json(hub.gh.repos(q.get("q", ""), login=user, refresh=q.get("refresh") == "1"))
        if (method, r) == ("DELETE", "/account"):
            if self._is_admin(dev):
                raise ApiError(400, "bad_request", "The hub owner's account cannot be deleted from the site.")
            n = 0
            for pid in hub.mgr.ids(user):
                hub.mgr.delete(pid)
                n += 1
            hub.gh.logout(user)
            hub.auth.revoke_user(user)
            return self._send(200, json.dumps({"ok": True, "projects_removed": n}).encode(), "application/json; charset=utf-8",
                              {"Set-Cookie": "%s=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0" % COOKIE})
        # --- personal access tokens for the person's own Claude Code / VS Code (MCP). Shown once.
        if r == "/tokens":
            if method == "GET":
                return self._json({"tokens": [{k: d.get(k) for k in ("device_id", "name", "created", "last_used")} for d in hub.auth.devices()
                                              if d.get("kind") == "token" and (d.get("user") or "").lower() == (user or "").lower()]})
            if method == "POST":
                body = self._body()
                name = body.get("name")
                if not isinstance(name, str) or not name.strip() or len(name) > 60:
                    raise ApiError(400, "bad_request", "name must be 1 to 60 characters")
                mine = [d for d in hub.auth.devices() if d.get("kind") == "token" and (d.get("user") or "").lower() == (user or "").lower()]
                if len(mine) >= 10:
                    raise ApiError(409, "too_many", "You already have 10 tokens. Remove one first.")
                token, did = hub.auth.new_device(name, user=user, kind="token")
                base = c.get("public_url") or "http://%s" % self.headers.get("Host")
                return self._json({"token": token, "device_id": did, "mcp_url": base.rstrip("/") + "/mcp"}, 201)
        m = re.match(r"^/tokens/(dev_[0-9a-f]{8})$", r)
        if m and method == "DELETE":
            if not hub.auth.revoke(m.group(1), user=user):
                raise ApiError(404, "not_found", "unknown token")
            return self._json({"ok": True})
        # --- start view (A/B) and usage events
        if (method, r) == ("POST", "/prefs"):
            body = self._body()
            hub.gh.set_view(user, body.get("view"))
            hub.log_event(user, "view_switch", v=(hub.gh.user_public(user) or {}).get("variant"), view=body.get("view"))
            return self._json({"ok": True, "start_view": body.get("view")})
        if (method, r) == ("POST", "/events"):
            body = self._body()
            ev, view, pid = body.get("event"), body.get("view"), body.get("project")
            if ev not in EVENTS or (view is not None and (not isinstance(view, str) or len(view) > 20)) or \
                    (pid is not None and (not isinstance(pid, str) or not re.match(r"^[a-z0-9-]{1,64}$", pid))):
                raise ApiError(400, "bad_request", "unknown event")
            if hub.allow("ev:" + (user or "?"), 120):
                hub.log_event(user, ev, v=(hub.gh.user_public(user) or {}).get("variant"), view=view, p=pid)
            return self._json({"ok": True})
        if (method, r) == ("GET", "/admin/ab"):
            if not self._is_admin(dev):
                raise ApiError(404, "not_found", "unknown route")
            out = hub.ab_summary()
            out["accounts"] = len(hub.gh.logins())
            return self._json(out)
        # --- Overleaf token (never echoed back)
        if r.startswith("/overleaf") and (pub or not self._is_admin(dev)):
            raise ApiError(404, "not_found", "unknown route")
        if r.startswith("/overleaf") and not hub.mgr.overleaf_on():
            return self._json({"error": "feature_disabled"}, 404)
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
                return self._json({"projects": hub.mgr.list(user)})
            if method == "POST":
                body = self._body()
                if body.get("paper_overleaf") not in (None, "") and not hub.mgr.overleaf_on():
                    return self._json({"error": "feature_disabled"}, 404)
                if not self._is_admin(dev) and not hub.allow("create:" + (user or "?"), 6, per=600):
                    raise ApiError(429, "busy", "You are creating projects very quickly. Wait a few minutes.")
                out = hub.mgr.create(body.get("name"), body.get("code_repo"), body.get("branch"), body.get("paper_overleaf"),
                                     body.get("paper_repo"), body.get("paper_branch"), body.get("paper_subdir"), user=user)
                hub.log_event(user, "project_created", v=(hub.gh.user_public(user) or {}).get("variant"), p=out["id"])
                return self._json(out, 201)
        m = re.match(r"^/projects/([a-z0-9-]{1,64})(/paper|/sync|/paper-source|/digest|/digest/send)?$", r)
        if m:
            pid, sub = m.group(1), m.group(2)
            self._own(pid, dev)  # 404 before any body is read
            if sub == "/digest" and method == "GET":
                return self._json(hub.mgr.digest_settings(pid))
            if sub == "/digest" and method == "POST":
                body = self._body()
                return self._json(hub.mgr.set_digest(pid, body.get("webhook"), body.get("enabled"), body.get("weekday")))
            if sub == "/digest/send" and method == "POST":
                self._body()
                if not hub.allow("digest:" + pid, 5, per=3600):
                    raise ApiError(429, "busy", "A digest was just sent. Try again later.")
                return self._json(hub.mgr.send_digest(pid))
            if sub is None and method == "DELETE":
                return self._json(hub.mgr.delete(pid))
            if sub == "/sync" and method == "POST":
                self._body()
                return self._json(hub.mgr.sync(pid))
            if sub == "/paper-source" and method == "POST":
                body = self._body()
                if body.get("kind") == "overleaf" and not hub.mgr.overleaf_on():
                    return self._json({"error": "feature_disabled"}, 404)
                return self._json(hub.mgr.set_paper_source(pid, body.get("kind"), body.get("project"), body.get("repo"), body.get("branch"), body.get("subdir")))
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
