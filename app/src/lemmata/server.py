"""Local HTTP server: static UI from web/ plus the JSON API of data-model.md section 12.

Stdlib only. Binds 127.0.0.1. One lock around every mutating engine call.
Additions beyond the contract (read-only, flagged in the handoff): GET /api/file and GET /api/raw
(file text / image bytes from inside the project repos, for previews and evidence context).
"""
from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from lemmata import __version__

WEB = Path(__file__).resolve().parent / "web"
MAX_BODY = 64 * 1024
BINARY_EXT = {".png", ".jpg", ".jpeg", ".pdf", ".svg", ".eps", ".npz", ".npy", ".pkl", ".gz", ".parquet", ".zip", ".pt", ".ckpt", ".bin"}
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}
MAX_FILE = 1024 * 1024
MAX_RAW = 5 * 1024 * 1024
STATIC_TYPES = {".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".html": "text/html; charset=utf-8",
                ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png"}


def parse_length(value, default=None):
    """Content-Length as a non-negative int. Missing -> `default` (None = 400); negative or non-numeric -> 400 before any read."""
    if value is None or not str(value).strip():
        if default is None:
            raise ApiError(400, "bad_request", "Content-Length is required")
        return default
    v = str(value).strip()
    if not (v.isascii() and v.isdigit()):
        raise ApiError(400, "bad_request", "bad Content-Length")
    return int(v)


def _accepts_by(engine):
    import inspect
    try:
        return "by" in inspect.signature(engine.set_triage).parameters
    except (TypeError, ValueError, AttributeError):
        return False


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _map_exc(exc):
    name = type(exc).__name__
    if name == "NotFound":
        return ApiError(404, "not_found", str(exc) or "not found")
    if name == "BadRequest":
        return ApiError(400, "bad_request", str(exc) or "bad request")
    return None


class App:
    """Holds the engine, the lock and repo lookups; handlers stay thin."""

    def __init__(self, engine):
        self.engine = engine
        self.lock = threading.Lock()
        self.port = 0

    def repos(self):
        return {r["id"]: Path(r["abs_path"]) for r in self.engine.project().get("repos", [])}

    def safe_path(self, repo, rel):
        roots = self.repos()
        if repo not in roots:
            raise ApiError(404, "not_found", "unknown repo")
        root = roots[repo].resolve()
        if not rel or rel.startswith("/") or "\x00" in rel:
            raise ApiError(400, "bad_request", "bad path")
        p = (root / rel).resolve()
        # hidden files and folders (.git, .lemmata, .env, ...) are never served; compare case-insensitively for macOS
        if not p.is_relative_to(root) or any(part.startswith(".") for part in p.relative_to(root).parts) or not p.is_file():
            raise ApiError(404, "not_found", "file not found")
        return p

    def read_lines(self, repo, rel, start=1, end=None, cap=400):
        p = self.safe_path(repo, rel)
        if p.suffix.lower() in BINARY_EXT or p.stat().st_size > MAX_FILE:
            return {"repo": repo, "path": rel, "start": 1, "total": None, "binary": True, "lines": []}
        data = p.read_bytes()
        if b"\x00" in data[:4096]:
            return {"repo": repo, "path": rel, "start": 1, "total": None, "binary": True, "lines": []}
        text = data.decode("utf-8", errors="replace").split("\n")
        if text and text[-1] == "":
            text.pop()
        total = len(text)
        start = max(1, start)
        end = min(total, end if end else start + cap - 1, start + cap - 1)
        return {"repo": repo, "path": rel, "start": start, "total": total, "binary": False,
                "lines": [ln.rstrip("\r")[:400] for ln in text[start - 1:end]]}

    # --- export
    def snapshot(self):
        e = self.engine
        from datetime import datetime, timezone
        alarms = e.alarms()
        graph = e.graph()
        nodes = {n["id"]: n for n in graph["nodes"]}
        findings = e.findings()
        snap = {"exported_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "project": e.project(), "graph": graph, "events": e.events(), "findings": findings, "alarms": alarms,
                "checkpoints": e.checkpoints(), "triage": e.triage(), "analyses": {}, "files": {}}
        for name in ("claims", "timeline", "ledger", "tasks", "tree"):   # research views (absent on fixture data)
            fn = getattr(e, name, None)
            if fn is not None:
                try:
                    snap[name] = fn()
                except Exception:
                    pass
        n = 0
        for g in alarms.get("groups", []):
            ids = [c["node_id"] for c in g["changed"]] + [d["node_id"] for d in g["downstream"]]
            for nid in ids:
                if n >= 400:
                    break
                try:
                    snap["analyses"]["%s|%s" % (g["id"], nid)] = e.analyze(g["id"], nid)
                    n += 1
                except Exception:  # an analysis that cannot be built is simply absent from the snapshot
                    pass
        ranges = {}

        def want(repo, path, a, b):
            if path:
                ranges.setdefault((repo, path), []).append((max(1, a), b))

        for nd in nodes.values():
            loc = nd.get("loc") or {}
            if nd["kind"] == "reference":
                continue
            if loc.get("line"):
                want(nd["repo"], loc["path"], loc["line"], min(loc.get("end_line") or loc["line"], loc["line"] + 60))
            elif loc.get("path") and nd["kind"] in ("code", "config", "data", "doc", "result"):
                want(nd["repo"], loc["path"], 1, 30)
        for f in findings.get("findings", []):
            for ev in f.get("evidence", []):
                if ev.get("line"):
                    want(ev["repo"], ev["path"], ev["line"] - 4, ev["line"] + 4)
        for ed in graph["edges"]:
            for ev in (ed.get("evidence") or [])[:2]:
                if ev.get("line"):
                    want(ev["repo"], ev["path"], ev["line"] - 1, ev["line"] + 1)
        for (repo, path), rs in ranges.items():
            rs.sort()
            merged = []
            for a, b in rs:
                if merged and a <= merged[-1][1] + 1:
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b])
            segs = []
            for a, b in merged:
                try:
                    r = self.read_lines(repo, path, a, b, cap=200)
                except ApiError:
                    break
                if r["binary"]:
                    break
                segs.append({"start": r["start"], "lines": r["lines"]})
            if segs:
                snap["files"]["%s|%s" % (repo, path)] = segs
        return snap

    def export_html(self):
        snap = self.snapshot()
        html = (WEB / "index.html").read_text(encoding="utf-8")
        css = (WEB / "app.css").read_text(encoding="utf-8")
        js = (WEB / "app.js").read_text(encoding="utf-8")
        vend = (WEB / "vendor" / "cytoscape.min.js").read_text(encoding="utf-8")

        def esc_script(s):
            return s.replace("</script", "<\\/script")

        data = (json.dumps(snap, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
                .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
        html = html.replace('<link rel="stylesheet" href="app.css">', "<style>\n%s\n</style>" % css.replace("</style", "<\\/style"))
        html = html.replace('<script src="vendor/cytoscape.min.js"></script>', "<script>\n%s\n</script>" % esc_script(vend))
        rjs = (WEB / "research.js").read_text(encoding="utf-8")
        html = html.replace('<script src="research.js"></script>', "<script>\n%s\n</script>" % esc_script(rjs))
        html = html.replace('<script src="app.js"></script>',
                            '<script type="application/json" id="lemmata-snapshot">%s</script>\n<script>\n%s\n</script>' % (data, esc_script(js)))
        return html, snap["project"].get("name", "project")


CSP = ("default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'")


class Handler(BaseHTTPRequestHandler):
    """Request handler; `app` is a class attribute (single-project mode) or set per request by the hub."""
    app: App = None
    web_root = WEB

    protocol_version = "HTTP/1.1"
    server_version = "lemmata"

    def log_message(self, fmt, *args):  # quiet by default
        pass

    # --- output helpers
    def _send(self, status, body, ctype, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if "Content-Security-Policy" not in (extra or {}):
            self.send_header("Content-Security-Policy", CSP)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, status=200):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status, code, message):
        if status >= 400 and self.command == "POST":
            self.close_connection = True
        self._json({"error": {"code": code, "message": message}}, status)

    # --- guards
    def _host_ok(self):
        host = (self.headers.get("Host") or "").lower()
        return host in ("127.0.0.1:%d" % self.app.port, "localhost:%d" % self.app.port)

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        return origin is None or origin.lower() in ("http://127.0.0.1:%d" % self.app.port, "http://localhost:%d" % self.app.port)

    def _dispatch(self, method):
        try:
            if not self._host_ok():
                raise ApiError(403, "forbidden", "host not allowed")
            url = urlsplit(self.path)
            path = unquote(url.path)
            q = {k: v[-1] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
            if path.startswith("/api/"):
                self._api(method, path, q)
            elif method == "GET":
                self._static(path)
            else:
                raise ApiError(405, "method_not_allowed", "method not allowed")
        except ApiError as e:
            self._error(e.status, e.code, e.message)
        except Exception as e:  # engine errors map by class name, everything else is a 500
            m = _map_exc(e)
            if m:
                self._error(m.status, m.code, m.message)
            else:
                self._error(500, "internal", "%s: %s" % (type(e).__name__, e))

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_HEAD(self):
        self._dispatch("GET")

    # --- static
    def _static(self, path, root=None):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        if "\x00" in rel:
            raise ApiError(404, "not_found", "not found")
        root = Path(root or self.web_root).resolve()
        p = (root / rel).resolve()
        if not p.is_relative_to(root) or not p.is_file():
            raise ApiError(404, "not_found", "not found")
        ctype = STATIC_TYPES.get(p.suffix.lower()) or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        self._send(200, p.read_bytes(), ctype)

    # --- body
    def _body(self):
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise ApiError(400, "bad_request", "Content-Type must be application/json")
        if not self._origin_ok():
            raise ApiError(403, "forbidden", "origin not allowed")
        n = parse_length(self.headers.get("Content-Length"), default=0)
        if n > MAX_BODY:
            raise ApiError(413, "too_large", "request body over 64 KB")
        raw = self.rfile.read(n) if n else b""
        try:
            obj = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "bad_request", "body is not valid JSON")
        if not isinstance(obj, dict):
            raise ApiError(400, "bad_request", "body must be a JSON object")
        return obj

    # --- api
    def _api(self, method, path, q):
        eng = self.app.engine
        r = path[len("/api"):]

        def need(name):   # research routes exist only on the real engine (not on fixture data)
            fn = getattr(eng, name, None)
            if fn is None:
                def missing(*a, **k):
                    raise ApiError(501, "not_implemented", "Not available on fixture data.")
                return missing
            return fn
        gets = {"/health": lambda: {"ok": True, "version": __version__},
                "/project": eng.project, "/graph": eng.graph, "/findings": eng.findings, "/alarms": eng.alarms,
                "/checkpoints": eng.checkpoints, "/triage": eng.triage,
                "/claims": need("claims"), "/timeline": need("timeline"), "/ledger": need("ledger"), "/tasks": need("tasks"), "/tree": need("tree")}
        if method == "GET":
            # engine reads wait for a running (re)scan: a half-built scan state must never be served
            if r in gets:
                with self.app.lock:
                    data = gets[r]()
                return self._json(data)
            if r == "/events":
                with self.app.lock:
                    data = eng.events(after_checkpoint=q.get("after_checkpoint") in ("1", "true"))
                return self._json(data)
            if r == "/digest":
                try:
                    days = int(q.get("days", "7"))
                except ValueError:
                    raise ApiError(400, "bad_request", "days must be a number")
                with self.app.lock:
                    data = need("digest")(days)
                return self._json(data)
            if r == "/claims.md":
                with self.app.lock:
                    md = need("claims_markdown")()
                return self._send(200, md.encode("utf-8"), "text/markdown; charset=utf-8", {"Content-Disposition": 'attachment; filename="claims.md"'})
            if r == "/analyze":
                if not q.get("group") or not q.get("node"):
                    raise ApiError(400, "bad_request", "group and node are required")
                with self.app.lock:
                    data = eng.analyze(q["group"], q["node"])
                return self._json(data)
            if r == "/file":
                try:
                    a = int(q.get("start", "1"))
                    b = int(q["end"]) if q.get("end") else None
                except ValueError:
                    raise ApiError(400, "bad_request", "start/end must be integers")
                return self._json(self.app.read_lines(q.get("repo", ""), q.get("path", ""), a, b))
            if r == "/raw":
                p = self.app.safe_path(q.get("repo", ""), q.get("path", ""))
                ct = IMAGE_TYPES.get(p.suffix.lower())
                if not ct or p.stat().st_size > MAX_RAW:
                    raise ApiError(404, "not_found", "not an image")
                return self._send(200, p.read_bytes(), ct)
            if r == "/export":
                with self.app.lock:
                    html, name = self.app.export_html()
                safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in name.lower()).strip("-") or "project"
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="%s-report.html"' % safe})
            if r in ("/scan", "/checkpoints.post", "/ask", "/links/decide"):
                raise ApiError(405, "method_not_allowed", "use POST")
            raise ApiError(404, "not_found", "unknown route")
        # POST
        RESEARCH = ("/claims", "/claims/link", "/claims/add", "/claims/remove", "/feedback", "/tasks")
        if r not in ("/scan", "/checkpoints", "/triage", "/links/decide", "/ask") + RESEARCH:
            if r in gets or r in ("/events", "/analyze", "/export", "/file", "/raw"):
                raise ApiError(405, "method_not_allowed", "use GET")
            raise ApiError(404, "not_found", "unknown route")
        body = self._body()
        if r == "/ask":
            with self.app.lock:
                return self._json(need("ask")(body.get("question")))
        if r in RESEARCH:
            def txt(k, req=False):
                v = body.get(k)
                if v is None and not req:
                    return None
                if not isinstance(v, str):
                    raise ApiError(400, "bad_request", "%s must be text" % k)
                return v
            with self.app.lock:
                if r == "/claims":
                    return self._json(need("set_claim")(txt("id", True), txt("state"), txt("text"), txt("note")))
                if r == "/claims/link":
                    return self._json(need("link_claim")(txt("id", True), txt("target", True), body.get("on", True) is not False))
                if r == "/claims/add":
                    return self._json(need("add_claim")(txt("text", True), txt("kind") or "claim"), 201)
                if r == "/claims/remove":
                    return self._json(need("remove_claim")(txt("id", True)))
                if r == "/feedback":
                    return self._json(need("add_feedback")(txt("text", True), txt("source")), 201)
                return self._json(need("set_task")(txt("id", True), txt("state"), txt("note"), txt("add_target"), txt("remove_target"), txt("text")))
        if r == "/scan":
            if not self.app.lock.acquire(blocking=False):
                raise ApiError(409, "busy", "a scan is running")
            try:
                return self._json(eng.scan())
            finally:
                self.app.lock.release()
        with self.app.lock:
            if r == "/checkpoints":
                note = body.get("note", "")
                at = body.get("at")
                if not isinstance(note, str) or len(note) > 500 or not (at is None or isinstance(at, dict)):
                    raise ApiError(400, "bad_request", "note must be text up to 500 characters; at must be an object or null")
                return self._json(eng.create_checkpoint(note=note, at=at), 201)
            if r == "/triage":
                note = body.get("note", "")
                if not isinstance(note, str) or len(note) > 2000:
                    raise ApiError(400, "bad_request", "note must be text up to 2000 characters")
                for k in ("target_type", "target_id", "state"):
                    if not isinstance(body.get(k), str):
                        raise ApiError(400, "bad_request", "%s is required" % k)
                by = getattr(self, "triage_by", None)
                if by and _accepts_by(eng):
                    return self._json(eng.set_triage(body["target_type"], body["target_id"], body["state"], note, by=by))
                return self._json(eng.set_triage(body["target_type"], body["target_id"], body["state"], note))
            if r == "/links/decide":
                for k in ("edge_id", "decision"):
                    if not isinstance(body.get(k), str):
                        raise ApiError(400, "bad_request", "%s is required" % k)
                return self._json(eng.decide_link(body["edge_id"], body["decision"]))


def make_handler(app: App):
    return type("Handler", (Handler,), {"app": app})


def bind(engine, host="127.0.0.1", port=8765, tries=100):
    """Create the server on the first free port at or after `port`."""
    app = App(engine)
    handler = make_handler(app)
    last = None
    for p in range(port, port + tries):
        try:
            srv = ThreadingHTTPServer((host, p), handler)
        except OSError as e:
            last = e
            continue
        srv.daemon_threads = True
        app.port = srv.server_address[1]
        srv.app = app
        return srv
    raise OSError("no free port in %d-%d: %s" % (port, port + tries - 1, last))
