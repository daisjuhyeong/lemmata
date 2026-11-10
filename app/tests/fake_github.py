"""A local fake GitHub for hub tests: device flow, /user, /user/repos and smart-HTTP git (via `git http-backend`).

Git requests must carry `Authorization: Basic base64(x-access-token:<token>)` or they get 401, so the hub's
per-command auth-header code path is exercised for real. Use one server as both github_api and github_web.
"""
import base64
import json
import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

CLIENT_ID = "fake-client-id"
TOKEN = "gho_FAKETOKENfaketokenFAKETOKENfaketoken1234"
USER = {"login": "alice", "name": "Alice Researcher", "avatar_url": "http://example.invalid/a.png"}
def _find_backend():
    """git-http-backend lives in git's exec path: /usr/lib/git-core on Debian/Ubuntu,
    /Library/Developer/CommandLineTools/usr/libexec/git-core on macOS, elsewhere for Homebrew."""
    import shutil, subprocess
    try:
        exec_path = subprocess.run(["git", "--exec-path"], capture_output=True, text=True, check=True).stdout.strip()
        cand = os.path.join(exec_path, "git-http-backend")
        if os.path.exists(cand):
            return cand
    except Exception:
        pass
    return shutil.which("git-http-backend") or "/usr/lib/git-core/git-http-backend"


BACKEND = _find_backend()
GIT_ENV = {"GIT_AUTHOR_NAME": "Alice", "GIT_AUTHOR_EMAIL": "alice@example.com", "GIT_COMMITTER_NAME": "Alice",
           "GIT_COMMITTER_EMAIL": "alice@example.com"}


def _git(cwd, *args):
    env = dict(os.environ, **GIT_ENV)
    subprocess.run(["git", "-c", "init.defaultBranch=main"] + list(args), cwd=str(cwd), env=env, check=True,
                   capture_output=True, stdin=subprocess.DEVNULL)


class FakeGitHub:
    def __init__(self, user=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.user = dict(user or USER)
        self.token = TOKEN
        self.accounts = {}   # extra token -> user (S07 multi-user tests); self.token / self.user stay the default account
        self.issue = None    # token handed out by the next approved device flow (default: self.token)
        self.fail = None     # None | "rate" | "forbidden" | "revoked": how /user and /user/repos answer
        self.api_calls = 0
        self.repos = []  # /user/repos entries
        self.state = "pending"  # pending | approved | denied | expired
        self.device_requests = []
        self.git_requests = []  # (path, auth ok)
        self.unauth_git = 0
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.srv.daemon_threads = True
        self.url = "http://127.0.0.1:%d" % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    # --- repos
    def add_repo(self, full_name, files, private=True, pushed_at="2026-11-01T00:00:00Z", description=""):
        owner, name = full_name.split("/")
        bare = self.root / "git" / owner / (name + ".git")
        work = self.root / "work" / owner / name
        bare.mkdir(parents=True)
        work.mkdir(parents=True)
        _git(bare, "init", "--bare", "-q")
        _git(work, "init", "-q")
        _git(work, "remote", "add", "origin", str(bare))
        self.repos.append({"full_name": full_name, "private": private, "default_branch": "main", "pushed_at": pushed_at,
                           "description": description})
        self.commit(full_name, files, "initial")

    def commit(self, full_name, files, msg):
        owner, name = full_name.split("/")
        work = self.root / "work" / owner / name
        for rel, text in files.items():
            p = work / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        _git(work, "add", "-A")
        _git(work, "commit", "-q", "-m", msg)
        _git(work, "push", "-q", "origin", "HEAD:refs/heads/main")

    def approve(self):
        self.state = "approved"

    # --- http
    def _handler(self):
        fake = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *a):
                pass

            def _reply(self, status, obj, headers=None):
                body = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _form(self):
                n = int(self.headers.get("Content-Length") or 0)
                return {k: v[-1] for k, v in parse_qs(self.rfile.read(n).decode()).items()}

            def _who(self):
                a = self.headers.get("Authorization") or ""
                tok = a[7:] if a.startswith("Bearer ") else None
                if tok == fake.token:
                    return fake.user
                return fake.accounts.get(tok)

            def _bearer_ok(self):
                return self._who() is not None

            def _failing(self):
                fake.api_calls += 1
                if fake.fail == "rate":
                    self._reply(403, {"message": "API rate limit exceeded for user"}, {"X-RateLimit-Remaining": "0", "Retry-After": "120"})
                elif fake.fail == "forbidden":
                    self._reply(403, {"message": "Resource protected by organization SAML enforcement"})
                elif fake.fail == "revoked":
                    self._reply(401, {"message": "Bad credentials"})
                else:
                    return False
                return True

            def do_POST(self):
                u = urlsplit(self.path)
                if u.path == "/login/device/code":
                    f = self._form()
                    fake.device_requests.append(f)
                    if f.get("client_id") != CLIENT_ID:
                        return self._reply(200, {"error": "incorrect_client_credentials"})
                    return self._reply(200, {"device_code": "devcode123", "user_code": "WDJB-MJHT",
                                             "verification_uri": fake.url + "/login/device", "expires_in": 900, "interval": 1})
                if u.path == "/login/oauth/access_token":
                    self._form()
                    if fake.state == "approved":
                        return self._reply(200, {"access_token": fake.issue or fake.token, "token_type": "bearer", "scope": "repo,read:user"})
                    if fake.state == "denied":
                        return self._reply(200, {"error": "access_denied"})
                    if fake.state == "expired":
                        return self._reply(200, {"error": "expired_token"})
                    return self._reply(200, {"error": "authorization_pending"})
                if ".git/" in u.path:
                    return self._git()
                self._reply(404, {"message": "Not Found"})

            def do_GET(self):
                u = urlsplit(self.path)
                if u.path in ("/user", "/user/repos") and self._failing():
                    return
                if u.path == "/user":
                    return self._reply(200, self._who()) if self._bearer_ok() else self._reply(401, {"message": "Bad credentials"})
                if u.path == "/user/repos":
                    if not self._bearer_ok():
                        return self._reply(401, {"message": "Bad credentials"})
                    q = parse_qs(u.query)
                    page, per = int(q.get("page", ["1"])[0]), int(q.get("per_page", ["30"])[0])
                    mine = [r for r in fake.repos if r["full_name"].split("/")[0] == self._who()["login"] or not r["private"]]
                    return self._reply(200, mine[(page - 1) * per: page * per])
                if ".git/" in u.path:
                    return self._git()
                self._reply(404, {"message": "Not Found"})

            def _git(self):
                u = urlsplit(self.path)
                ok = any(self.headers.get("Authorization") == "Basic " + base64.b64encode(("x-access-token:%s" % t).encode()).decode()
                         for t in [fake.token] + list(fake.accounts))
                fake.git_requests.append((u.path, ok))
                if not ok:
                    fake.unauth_git += 1
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", 'Basic realm="fake"')
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                env = {"PATH": os.environ.get("PATH", ""), "GIT_PROJECT_ROOT": str(fake.root / "git"), "GIT_HTTP_EXPORT_ALL": "1",
                       "REQUEST_METHOD": self.command, "PATH_INFO": u.path, "QUERY_STRING": u.query,
                       "CONTENT_TYPE": self.headers.get("Content-Type", ""), "CONTENT_LENGTH": str(len(body)),
                       "REMOTE_USER": "x-access-token", "REMOTE_ADDR": "127.0.0.1"}
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
