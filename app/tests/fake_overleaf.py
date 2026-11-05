"""A local fake Overleaf Git server: `GET/POST /<24hex>/info/refs ...` through `git http-backend`, HTTP Basic auth
with user `git` and the token as password (anything else gets 401). Default branch `master`, like Overleaf.
Set `fake.rate_limit = True` to answer 429; `fake.fetches` counts upload-pack info/refs requests per project."""
import base64
import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from fake_github import BACKEND, GIT_ENV

TOKEN = "olp_FAKEOVERLEAFTOKENfakeoverleaftoken1234"


def _git(cwd, *args):
    subprocess.run(["git", "-c", "init.defaultBranch=master"] + list(args), cwd=str(cwd), env=dict(os.environ, **GIT_ENV), check=True,
                   capture_output=True, stdin=subprocess.DEVNULL)


class FakeOverleaf:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.token = TOKEN
        self.requests = []  # (path, auth ok)
        self.fetches = {}  # project id -> number of ref advertisements served
        self.projects = set()
        self.rate_limit = False
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.srv.daemon_threads = True
        self.url = "http://127.0.0.1:%d" % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def add_project(self, pid, files):
        bare = self.root / "git" / pid
        work = self.root / "work" / pid
        bare.mkdir(parents=True)
        work.mkdir(parents=True)
        _git(bare, "init", "--bare", "-q")
        _git(work, "init", "-q")
        _git(work, "remote", "add", "origin", str(bare))
        self.projects.add(pid)
        self.commit(pid, files, "Initial commit")

    def commit(self, pid, files, msg):
        work = self.root / "work" / pid
        for rel, text in files.items():
            p = work / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        _git(work, "add", "-A")
        _git(work, "commit", "-q", "--allow-empty", "-m", msg)
        _git(work, "push", "-q", "origin", "HEAD:refs/heads/master")

    def _handler(self):
        fake = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *a):
                pass

            def _empty(self, status, extra=None):
                self.send_response(status)
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self):
                self._git()

            def do_POST(self):
                self._git()

            def _git(self):
                u = urlsplit(self.path)
                pid = u.path.strip("/").split("/")[0]
                want = "Basic " + base64.b64encode(("git:%s" % fake.token).encode()).decode()
                ok = self.headers.get("Authorization") == want
                fake.requests.append((u.path, ok))
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                if not ok:
                    return self._empty(401, {"WWW-Authenticate": 'Basic realm="Overleaf"'})
                if fake.rate_limit:
                    return self._empty(429)
                if pid not in fake.projects:
                    return self._empty(404)
                if u.path.endswith("/info/refs") and "upload-pack" in u.query:
                    fake.fetches[pid] = fake.fetches.get(pid, 0) + 1
                env = {"PATH": os.environ.get("PATH", ""), "GIT_PROJECT_ROOT": str(fake.root / "git"), "GIT_HTTP_EXPORT_ALL": "1",
                       "REQUEST_METHOD": self.command, "PATH_INFO": u.path, "QUERY_STRING": u.query,
                       "CONTENT_TYPE": self.headers.get("Content-Type", ""), "CONTENT_LENGTH": str(len(body)),
                       "REMOTE_USER": "git", "REMOTE_ADDR": "127.0.0.1"}
                if self.headers.get("Content-Encoding"):
                    env["HTTP_CONTENT_ENCODING"] = self.headers["Content-Encoding"]
                if self.headers.get("Git-Protocol"):
                    env["GIT_PROTOCOL"] = self.headers["Git-Protocol"]
                p = subprocess.run([BACKEND], input=body, env=env, capture_output=True)
                head, _, payload = p.stdout.partition(b"\r\n\r\n")
                status, headers = 200, []
                for line in head.decode("latin-1").split("\r\n"):
                    k, _, v = line.partition(":")
                    if k.lower() == "status":
                        status = int(v.strip().split()[0])
                    elif k:
                        headers.append((k, v.strip()))
                self.send_response(status)
                for k, v in headers:
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        return H
