"""Mock Lemmata hub for web-eng page tests (stdlib only). Implements the S04 brief routes the hub pages call.

    python3 app/tests/mock_hub.py [--port 18770]       pairing code is ABCD2345

Per-project UI/API: /p/<pid>/ serves web/ and proxies /p/<pid>/api/* to a fixture-engine server.
Test hooks: POST /__mock/gh {"mode": "ok|denied|expired", "pending": n} sets the next device-flow outcome.
Not the real hub (that is app/src/lemmata/hub/); only for UI tests.
"""
import argparse
import http.client
import json
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from lemmata.fixture_engine import FixtureEngine  # noqa: E402
from lemmata.server import bind  # noqa: E402
from lemmata.hub.routes import CSP  # noqa: E402  (same policy as the real hub)

WEB = HERE.parent / "src" / "lemmata" / "web"
TYPES = {".js": "application/javascript", ".css": "text/css", ".html": "text/html", ".svg": "image/svg+xml", ".json": "application/json"}
REPOS = [
    {"full_name": "juhyeong/tad-metrics", "private": True, "default_branch": "main", "pushed_at": "2026-11-05T08:00:00Z", "description": "Alarm-Analyzer evaluation code for time-series anomaly detection"},
    {"full_name": "juhyeong/odad-survey-figs", "private": False, "default_branch": "main", "pushed_at": "2026-11-01T08:00:00Z", "description": "Figures for the ODAD survey"},
    {"full_name": "dais-lab/brats-recon", "private": True, "default_branch": "dev", "pushed_at": "2026-10-20T08:00:00Z", "description": ""},
    {"full_name": "juhyeong/dotfiles", "private": False, "default_branch": "main", "pushed_at": "2026-08-20T08:00:00Z", "description": None},
]


class State:
    def __init__(self):
        self.sessions, self.paired_codes = set(), {"ABCD2345"}
        self.user = None
        self.gh = {"mode": "ok", "pending": 2}
        self.polls = 0
        self.overleaf = False
        self.projects = []
        self.engine_port = None
        self.lock = threading.Lock()


ST = State()


def start_engine():
    srv = bind(FixtureEngine(""), port=18900)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    ST.engine_port = srv.server_address[1]


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send(self, status, obj=None, raw=None, ctype="application/json", headers=None):
        body = raw if raw is not None else json.dumps(obj if obj is not None else {}).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", CSP)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def err(self, status, code, msg):
        self.send(status, {"error": {"code": code, "message": msg}})

    def authed(self):
        c = self.headers.get("Cookie", "")
        return any(p.strip() == "lemmata_session=" + t for t in ST.sessions for p in c.split(";"))

    def body(self):
        if not hasattr(self, "_b"):
            n = int(self.headers.get("Content-Length") or 0)
            self._b = self.rfile.read(n) if n else b""
        return self._b

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_DELETE(self):
        self.route("DELETE")

    def status_obj(self):
        return {"paired": self.authed(), "github": {"signed_in": bool(ST.user), "user": ST.user}, "overleaf_configured": ST.overleaf, "version": "0.1.0"}

    def route(self, m):
        self.__dict__.pop("_b", None)
        self.body()   # always drain the request body so keep-alive connections stay in sync
        u = urlsplit(self.path)
        p, q = u.path, parse_qs(u.query)
        if p == "/__mock/gh" and m == "POST":
            ST.gh.update(json.loads(self.body() or b"{}")); ST.polls = 0
            return self.send(200, ST.gh)
        if p == "/__mock/reset" and m == "POST":
            ST.sessions.clear(); ST.user = None; ST.projects.clear(); ST.polls = 0; ST.overleaf = False; ST.gh.update({"mode": "ok", "pending": 2})
            ST.paired_codes = {"ABCD2345"}
            return self.send(200, {})
        if p == "/api/hub/status":
            return self.send(200, self.status_obj())
        if p == "/api/hub/pair" and m == "POST":
            b = json.loads(self.body() or b"{}")
            if b.get("code") not in ST.paired_codes:
                return self.err(403, "bad_code", "Wrong or expired code.")
            ST.paired_codes.discard(b["code"])
            tok = secrets.token_urlsafe(32)
            ST.sessions.add(tok)
            return self.send(200, {"token": tok, "device_id": "dev_mock"}, headers={"Set-Cookie": "lemmata_session=%s; HttpOnly; SameSite=Strict; Path=/" % tok})
        if p.startswith("/p/") or p.startswith("/api/") or p == "/mcp":
            if not self.authed():
                return self.err(401, "unauthorized", "Pair this device first.")
        if p == "/api/hub/overleaf/token" and m == "PUT":
            ST.overleaf = bool(json.loads(self.body() or b"{}").get("token"))
            return self.send(200, {"configured": ST.overleaf})
        if p == "/api/hub/overleaf/token" and m == "DELETE":
            ST.overleaf = False
            return self.send(200, {"configured": False})
        if p == "/api/hub/github/start" and m == "POST":
            ST.polls = 0
            return self.send(200, {"user_code": "WDJB-MJHT", "verification_uri": "http://localhost:%d/__mock/github-device" % self.server.server_address[1], "expires_in": 900, "interval": 1})
        if p == "/api/hub/github/poll":
            ST.polls += 1
            if ST.polls <= ST.gh["pending"]:
                return self.send(200, {"state": "pending"})
            mode = ST.gh["mode"]
            if mode == "ok":
                ST.user = {"login": "juhyeong", "name": "Juhyeong", "avatar_url": ""}
                return self.send(200, {"state": "ok", "user": ST.user})
            return self.send(200, {"state": mode})
        if p == "/api/hub/github/logout" and m == "POST":
            ST.user = None
            return self.send(200, {"ok": True})
        if p == "/api/hub/github/repos":
            if not ST.user:
                return self.err(403, "not_signed_in", "Sign in with GitHub first.")
            s = (q.get("q") or [""])[0].lower()
            return self.send(200, {"repos": [r for r in REPOS if s in r["full_name"].lower()]})
        if p == "/api/hub/projects" and m == "GET":
            return self.send(200, {"projects": ST.projects})
        if p == "/api/hub/projects" and m == "POST":
            b = json.loads(self.body() or b"{}")
            time.sleep(1.2)
            name = b["code_repo"].split("/")[-1]
            pr = {"id": name + "-" + secrets.token_hex(2), "name": name, "code_repo": b["code_repo"], "branch": b.get("branch") or "main",
                  "paper_versions": 0, "paper_source": {"kind": "zip"}, "last_sync": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "scanned_at": None, "counts": {"recheck": 0, "findings": 0}}
            ST.projects.append(pr)
            return self.send(201, {"project": pr})
        if p.startswith("/api/hub/projects/"):
            parts = p.split("/")
            pr = next((x for x in ST.projects if x["id"] == parts[4]), None)
            if not pr:
                return self.err(404, "not_found", "No such project.")
            if parts[5:] == ["paper"] and m == "POST":
                data = self.body()
                if self.headers.get("Content-Type") != "application/zip" or data[:2] != b"PK":
                    return self.err(400, "bad_zip", "That file is not a zip.")
                pr["paper_versions"] += 1; pr["counts"] = {"recheck": 3, "findings": 2}
                return self.send(200, {"version": pr["paper_versions"], "commit": "abc1234", "files": 12})
            if parts[5:] == ["paper-source"] and m == "POST":
                b = json.loads(self.body() or b"{}")
                if b.get("kind") == "zip":
                    pr["paper_source"] = {"kind": "zip"}
                    return self.send(200, {"kind": "zip"})
                import re
                mm = re.search(r"[0-9a-f]{24}", b.get("project") or "")
                if not ST.overleaf:
                    return self.err(409, "overleaf_token_missing", "Save your Overleaf token first.")
                if not mm:
                    return self.err(400, "bad_request", "That is not an Overleaf project link or id.")
                if mm.group(0).startswith("dead"):
                    return self.err(404, "overleaf_not_found", "Overleaf has no project with that id.")
                time.sleep(0.6)
                pr["paper_source"] = {"kind": "overleaf", "project_id": mm.group(0)}
                pr["paper_versions"] = 4; pr["counts"] = {"recheck": 3, "findings": 2}
                pr["last_sync"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                return self.send(200, {"kind": "overleaf", "project_id": mm.group(0), "head": "abc1234", "versions": 4})
            if parts[5:] == ["sync"] and m == "POST":
                self.body()
                pr["last_sync"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                return self.send(200, {"changed": False, "head": "abc1234", "code": {"changed": False, "head": "abc1234"}, "paper": {"changed": False, "head": "def5678"}})
        if p.startswith("/p/"):
            parts = p.split("/", 3)   # '', 'p', pid, rest
            rest = parts[3] if len(parts) > 3 else ""
            if len(parts) == 3:
                self.send_response(301); self.send_header("Location", p + "/"); self.send_header("Content-Length", "0"); self.end_headers(); return
            if rest.startswith("api/"):
                return self.proxy(m, "/" + rest + ("?" + u.query if u.query else ""))
            return self.static(rest or "index.html")
        if m == "GET":
            return self.static("hub/index.html" if p == "/" else "hub/" + p.lstrip("/"))
        self.err(404, "not_found", "Unknown route")

    def static(self, rel):
        f = (WEB / rel).resolve()
        if not f.is_relative_to(WEB) or not f.is_file():
            return self.err(404, "not_found", "no such file")
        self.send(200, raw=f.read_bytes(), ctype=TYPES.get(f.suffix, "application/octet-stream"))

    def proxy(self, m, path):
        c = http.client.HTTPConnection("127.0.0.1", ST.engine_port, timeout=20)
        data = self.body() if m != "GET" else None
        c.request(m, path, body=data, headers={"Host": "127.0.0.1:%d" % ST.engine_port, "Content-Type": self.headers.get("Content-Type", "application/json")})
        r = c.getresponse(); out = r.read(); c.close()
        self.send(r.status, raw=out, ctype=r.getheader("Content-Type") or "application/json")


def serve(port=18770):
    start_engine()
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=18770)
    a = ap.parse_args()
    s = serve(a.port)
    print("mock hub on http://127.0.0.1:%d  pairing code ABCD2345" % a.port, flush=True)
    threading.Event().wait()
