"""Hub tests (S04): guard, pairing, GitHub device flow, projects, zip ingest, sync, MCP routing. No network: fake GitHub.

    PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p "test_hub.py"
"""
import http.client
import io
import json
import os
import stat
import sys
import tempfile
import threading
import types
import unittest
import zipfile
from pathlib import Path

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_github import CLIENT_ID, TOKEN, FakeGitHub  # noqa: E402
from lemmata.hub import guard, projects  # noqa: E402
from lemmata.hub.github import scrub  # noqa: E402
from lemmata.hub.routes import Hub, make_hub_server  # noqa: E402

projects.ALLOWED_PROTOCOLS = ["http", "https"]  # tests only: the fake GitHub speaks plain http on loopback

TEX1 = r"""\documentclass{article}
\begin{document}
\section{Results}
We reach accuracy of 91.2 on the benchmark (see \texttt{eval.py}).
\end{document}
"""
CODE = {"README.md": "# demo\n", "eval.py": "print('acc 91.2')\n"}


def make_zip(files, top=None, extra=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            z.writestr((top + "/" if top else "") + name, text)
        for zi, data in (extra or []):
            z.writestr(zi, data)
    return buf.getvalue()


class HubBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeGitHub()
        cls.fake.add_repo("alice/demo-code", CODE, description="demo repo")
        cls.fake.add_repo("alice/other", {"a.txt": "x\n"}, pushed_at="2026-10-01T00:00:00Z")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name) / "Lemmata"
        cls.hub = Hub(cls.data, port=0, detect_tailscale=False)
        cls.hub.cfg.update(github_client_id=CLIENT_ID, github_api=cls.fake.url, github_web=cls.fake.url)
        cls.srv = make_hub_server(cls.hub, host="127.0.0.1", port=0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.origin = "http://127.0.0.1:%d" % cls.port
        cls.token = cls.pair("test")

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.fake.close()
        cls.tmp.cleanup()

    @classmethod
    def pair(cls, device):
        code = cls.hub.auth.new_code()
        s, h, body = cls.raw("POST", "/api/hub/pair", json.dumps({"code": code, "device": device}).encode(), {"Content-Type": "application/json"})
        assert s == 200, body
        return json.loads(body)["token"]

    @classmethod
    def raw(cls, method, path, body=None, headers=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=60)
        h = {"Host": host or "127.0.0.1:%d" % cls.port}
        h.update(headers or {})
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        out = r.read()
        hdrs = dict((k.lower(), v) for k, v in r.getheaders())
        c.close()
        return r.status, hdrs, out

    def api(self, method, path, body=None, token=None, headers=None, ctype="application/json", raw=None):
        h = {"Authorization": "Bearer " + (token or self.token)}
        data = raw if raw is not None else (json.dumps(body if body is not None else {}).encode() if method in ("POST",) else None)
        if data is not None:
            h["Content-Type"] = ctype
        h.update(headers or {})
        s, hd, out = self.raw(method, path, data, h)
        try:
            return s, json.loads(out)
        except ValueError:
            return s, out

    def signin(self):
        if self.hub.gh.stored():
            return
        self.assertEqual(self.api("POST", "/api/hub/github/start")[0], 200)
        self.fake.approve()
        s, r = self.api("GET", "/api/hub/github/poll")
        self.assertEqual(r["state"], "ok", r)


class GuardUnits(unittest.TestCase):
    def test_peer_ok(self):
        for a in ("127.0.0.1", "::1", "100.64.0.1", "100.127.255.254", "fd7a:115c:a1e0::1", "::ffff:127.0.0.1", "::ffff:100.100.1.1"):
            self.assertTrue(guard.peer_ok(a), a)
        for a in ("8.8.8.8", "192.168.1.5", "100.63.255.255", "100.128.0.1", "fd7b::1", "10.0.0.1", "junk"):
            self.assertFalse(guard.peer_ok(a), a)

    def test_host_origin(self):
        g = guard.Guard(["mini.example"], detect=False)
        self.assertTrue(g.host_ok("localhost:8765") and g.host_ok("mini.example") and g.host_ok("[::1]:8765"))
        self.assertFalse(g.host_ok("evil.example:8765") or g.host_ok("") or g.host_ok(None))
        self.assertTrue(g.origin_ok(None) and g.origin_ok("http://localhost:8765", 8765) and g.origin_ok("http://mini.example:8765", 8765))
        self.assertTrue(g.origin_ok("http://[::1]:8765", 8765))
        self.assertFalse(g.origin_ok("http://evil.example") or g.origin_ok("null") or g.origin_ok("http://localhost.evil.example"))
        self.assertFalse(g.origin_ok("http://localhost:9999", 8765) or g.origin_ok("http://localhost", 8765) or g.origin_ok("https://localhost:8765", 8765))
        self.assertEqual(guard.bind_addresses()[0], "127.0.0.1")
        self.assertNotIn("0.0.0.0", guard.bind_addresses())

    def test_scrub(self):
        from lemmata.hub.github import git_auth_header
        t = "gho_" + "A" * 30
        s = scrub("fatal: Authorization: Basic %s and %s and %s" % ("zzzz", t, git_auth_header(t)), t)
        self.assertNotIn(t, s)
        self.assertNotIn(git_auth_header(t).split()[-1], s)
        self.assertNotIn("zzzz", s)


class TreeSafety(unittest.TestCase):
    def test_worktree_refuses_escapes_and_symlinks(self):
        from lemmata.engine.tree import WorkTree
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "secret.txt").write_text("TOPSECRET")
            repo = d / "repo"
            (repo / "sub").mkdir(parents=True)
            (repo / "ok.tex").write_text("hello")
            (repo / "sub" / "b.tex").write_text("b")
            os.symlink(d / "secret.txt", repo / "link.txt")
            os.symlink(d, repo / "dirlink")
            wt = WorkTree(repo, "paper")
            self.assertTrue(wt.has("ok.tex") and wt.has("sub/../ok.tex") and wt.read("sub/b.tex") == b"b")
            for bad in ("../secret.txt", "sub/../../secret.txt", str(d / "secret.txt"), "link.txt", "dirlink/secret.txt", "", "..", "a\x00b"):
                self.assertFalse(wt.has(bad), bad)
                self.assertIsNone(wt.read(bad), bad)
                self.assertEqual(wt.size(bad), 0, bad)


class ZipUnits(unittest.TestCase):
    def extract(self, data):
        with tempfile.TemporaryDirectory() as d:
            zp = Path(d) / "x.zip"
            zp.write_bytes(data)
            out = Path(d) / "out"
            out.mkdir()
            n = projects.safe_extract(zp, out)
            return n, sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())

    def bad(self, data):
        with self.assertRaises(projects.ProjectError) as cm:
            self.extract(data)
        self.assertEqual(cm.exception.code, "bad_zip")

    def test_strip_top_level(self):
        self.assertEqual(self.extract(make_zip({"main.tex": "a", "sec/b.tex": "b"}, top="paper")), (2, ["main.tex", "sec/b.tex"]))
        self.assertEqual(self.extract(make_zip({"main.tex": "a", "x/b.tex": "b"}))[1], ["main.tex", "x/b.tex"])
        self.assertEqual(self.extract(make_zip({"main.tex": "a"}, extra=[("__MACOSX/._main.tex", "junk")]))[1], ["main.tex"])

    def test_names_dupes_nul(self):
        self.bad(make_zip({"a/B.tex": "1", "a/b.tex": "2"}))
        self.bad(make_zip({}, extra=[("a\\b.tex", "x")]))
        self.bad(make_zip({}, extra=[("sub/.GIT/config", "x")]))

    def test_zip_slip_and_absolute(self):
        self.bad(make_zip({}, extra=[("../evil.txt", "x")]))
        self.bad(make_zip({}, extra=[("a/../../evil.txt", "x")]))
        self.bad(make_zip({}, extra=[("/etc/evil", "x")]))
        self.bad(make_zip({}, extra=[("C:/evil", "x")]))
        self.bad(make_zip({}, extra=[("..\\evil", "x")]))
        self.bad(make_zip({}, extra=[(".git/config", "x")]))

    def test_symlink_rejected(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            zi = zipfile.ZipInfo("link")
            zi.create_system = 3
            zi.external_attr = (0o120777 << 16)
            z.writestr(zi, "/etc/passwd")
        self.bad(buf.getvalue())

    def test_limits(self):
        old = (projects.MAX_FILES, projects.MAX_UNPACKED)
        try:
            projects.MAX_FILES = 10
            self.bad(make_zip({"f%d.txt" % i: "x" for i in range(11)}))
            projects.MAX_FILES = 5000
            projects.MAX_UNPACKED = 1000
            self.bad(make_zip({"big.bin": "0" * 5000}))
        finally:
            projects.MAX_FILES, projects.MAX_UNPACKED = old

    def test_lying_header_is_caught_while_writing(self):
        old = projects.MAX_UNPACKED
        data = bytearray(make_zip({"big.bin": "0" * 5000}))
        # shrink the declared sizes (central directory + local header) to 10 bytes; the real stream is 5000 bytes
        import struct
        for sig, off in ((b"PK\x01\x02", 24), (b"PK\x03\x04", 22)):
            i = data.find(sig)
            struct.pack_into("<I", data, i + off, 10)
        try:
            projects.MAX_UNPACKED = 1000
            with tempfile.TemporaryDirectory() as d:
                zp = Path(d) / "x.zip"
                zp.write_bytes(bytes(data))
                (Path(d) / "o").mkdir()
                with self.assertRaises((projects.ProjectError, Exception)):
                    projects.safe_extract(zp, Path(d) / "o")
        finally:
            projects.MAX_UNPACKED = old


class HubTest(HubBase):
    # ------------------------------------------------------------ guard and auth
    def test_a_files_and_modes(self):
        self.assertEqual(stat.S_IMODE(os.stat(self.data).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(self.data / "hub" / "tokens.json").st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.data / "hub" / "config.json").st_mode), 0o600)
        tk = json.loads((self.data / "hub" / "tokens.json").read_text())
        self.assertNotIn(self.token, json.dumps(tk))  # stored hashed
        self.assertEqual(len(self.token), 43)

    def test_host_guard_and_public_routes(self):
        s, _, _ = self.raw("GET", "/api/hub/status", host="evil.example")
        self.assertEqual(s, 403)
        s, _, out = self.raw("GET", "/api/hub/status")
        self.assertEqual(s, 200)
        j = json.loads(out)
        self.assertTrue(j["hub"] and not j["authenticated"])
        self.assertNotIn("token", out.decode())

    def test_everything_else_needs_a_session(self):
        for m, p in (("GET", "/api/hub/projects"), ("GET", "/api/hub/github/repos"), ("GET", "/p/x/api/project"), ("POST", "/mcp"),
                     ("GET", "/p/x/"), ("DELETE", "/api/hub/projects/x")):
            s, _, _ = self.raw(m, p, b"{}" if m == "POST" else None, {"Content-Type": "application/json"} if m == "POST" else None)
            self.assertEqual(s, 401, (m, p))
        s, _, _ = self.raw("GET", "/api/hub/projects", None, {"Authorization": "Bearer nope"})
        self.assertEqual(s, 401)

    def test_pairing_limits_and_cookie_csrf(self):
        hdr = {"Content-Type": "application/json"}
        good = self.hub.auth.new_code()
        for _ in range(5):
            s, _, _ = self.raw("POST", "/api/hub/pair", b'{"code":"AAAAAAAA"}', hdr)
            self.assertEqual(s, 403)
        s, _, _ = self.raw("POST", "/api/hub/pair", json.dumps({"code": good}).encode(), hdr)
        self.assertEqual(s, 403)  # code burned after 5 wrong attempts
        # foreign origin and wrong content type
        code = self.hub.auth.new_code()
        s, _, _ = self.raw("POST", "/api/hub/pair", json.dumps({"code": code}).encode(), dict(hdr, Origin="http://evil.example"))
        self.assertEqual(s, 403)
        s, _, _ = self.raw("POST", "/api/hub/pair", json.dumps({"code": code}).encode(), {"Content-Type": "text/plain"})
        self.assertEqual(s, 400)
        s, h, out = self.raw("POST", "/api/hub/pair", json.dumps({"code": code.lower(), "device": "Browser"}).encode(), dict(hdr, Origin=self.origin))
        self.assertEqual(s, 200)
        cookie = h["set-cookie"]
        for attr in ("HttpOnly", "SameSite=Strict", "Path=/", "lemmata_session="):
            self.assertIn(attr, cookie)
        tok = json.loads(out)["token"]
        # code is single use
        self.assertEqual(self.raw("POST", "/api/hub/pair", json.dumps({"code": code}).encode(), hdr)[0], 403)
        ck = {"Cookie": cookie.split(";")[0]}
        self.assertEqual(self.raw("GET", "/api/hub/projects", None, ck)[0], 200)
        # state change with a cookie needs a matching Origin
        self.assertEqual(self.raw("POST", "/api/hub/github/logout", b"{}", dict(ck, **hdr))[0], 403)
        self.assertEqual(self.raw("POST", "/api/hub/github/logout", b"{}", dict(ck, Origin="http://evil.example", **hdr))[0], 403)
        # revoke
        dev = [d for d in self.hub.auth.devices() if d["name"] == "Browser"][0]
        self.assertTrue(self.hub.auth.revoke(dev["device_id"]))
        self.assertEqual(self.raw("GET", "/api/hub/projects", None, {"Authorization": "Bearer " + tok})[0], 401)
        self.assertEqual(self.raw("GET", "/api/hub/projects", None, ck)[0], 401)

    def test_body_caps(self):
        s, r = self.api("POST", "/api/hub/github/logout", raw=b"{" + b" " * 70000 + b"}")
        self.assertEqual(s, 413)
        s, hd, out = self.raw("POST", "/api/hub/projects/none/paper", None,
                              {"Authorization": "Bearer " + self.token, "Content-Type": "application/zip", "Content-Length": str(100 * 1024 * 1024 + 1)})
        self.assertEqual(s, 404)  # unknown project is rejected before reading
        self.signin()
        pid = self.make_project()
        s, r = self.api("POST", "/api/hub/projects/%s/paper" % pid, raw=b"x", ctype="application/zip", headers={"Content-Length": str(100 * 1024 * 1024 + 1)})
        self.assertEqual(s, 413, r)
        s, r = self.api("POST", "/api/hub/projects/%s/paper" % pid, raw=b"{}", ctype="application/json")
        self.assertEqual(s, 400)

    # ------------------------------------------------------------ MCP routing
    def test_mcp_routing(self):
        calls = []
        mod = types.ModuleType("lemmata.mcp")

        def handle(raw, ctx):
            req = json.loads(raw)
            calls.append((req, ctx))
            if req.get("method") == "notifications/initialized":
                return 202, None
            return 200, json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": {"ok": True}})
        mod.handle = handle
        old = sys.modules.get("lemmata.mcp")
        import lemmata
        had = hasattr(lemmata, "mcp")
        sys.modules["lemmata.mcp"] = mod
        lemmata.mcp = mod
        try:
            s, hd, out = self.raw("GET", "/mcp", None, {"Authorization": "Bearer " + self.token})
            self.assertEqual(s, 405)
            s, r = self.api("POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"})
            self.assertEqual((s, r["result"]), (200, {"ok": True}))
            self.assertEqual(calls[-1][1].device, "test")
            s, hd, out = self.raw("POST", "/mcp", b'{"jsonrpc":"2.0","method":"notifications/initialized"}',
                                  {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
            self.assertEqual((s, out), (202, b""))
            # a session cookie is not accepted on /mcp
            cookie = "lemmata_session=" + self.token
            s, _, _ = self.raw("POST", "/mcp", b"{}", {"Cookie": cookie, "Content-Type": "application/json", "Origin": self.origin})
            self.assertEqual(s, 401)
            s, r = self.api("POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"}, headers={"Origin": "http://evil.example"})
            self.assertEqual(s, 403)
        finally:
            if old is None:
                sys.modules.pop("lemmata.mcp", None)
            else:
                sys.modules["lemmata.mcp"] = old
            if not had:
                del lemmata.mcp

    # ------------------------------------------------------------ GitHub, projects
    def make_project(self):
        s, r = self.api("POST", "/api/hub/projects", {"code_repo": "alice/demo-code"})
        self.assertEqual(s, 201, r)
        return r["id"]

    def test_github_flow_owner_and_repos(self):
        s, r = self.api("GET", "/api/hub/github/repos")
        if not self.hub.gh.stored():
            self.assertEqual((s, r["error"]["code"]), (409, "not_signed_in"))
        s, r = self.api("POST", "/api/hub/github/start")
        self.assertEqual(s, 200)
        self.assertEqual(r["user_code"], "WDJB-MJHT")
        self.assertEqual(self.fake.device_requests[-1]["scope"], "repo read:user")
        self.assertEqual(self.fake.device_requests[-1]["client_id"], CLIENT_ID)
        if not self.hub.gh.stored():
            self.fake.state = "pending"
            self.assertEqual(self.api("GET", "/api/hub/github/poll")[1]["state"], "pending")
        self.fake.approve()
        s, r = self.api("GET", "/api/hub/github/poll")
        self.assertEqual(r["state"], "ok")
        self.assertEqual(r["user"]["login"], "alice")
        self.assertEqual(stat.S_IMODE(os.stat(self.data / "hub" / "github.json").st_mode), 0o600)
        self.assertEqual(self.hub.cfg.load()["owner"], "alice")
        s, r = self.api("GET", "/api/hub/github/repos")
        self.assertEqual([x["full_name"] for x in r["repos"]], ["alice/demo-code", "alice/other"])  # newest push first
        self.assertEqual(set(r["repos"][0]), {"full_name", "private", "default_branch", "pushed_at", "description"})
        self.assertEqual([x["full_name"] for x in self.api("GET", "/api/hub/github/repos?q=OTH")[1]["repos"]], ["alice/other"])
        # a different account is refused and nothing is saved
        self.assertEqual(self.api("POST", "/api/hub/github/logout")[0], 200)
        self.assertFalse((self.data / "hub" / "github.json").exists())
        self.fake.user = {"login": "mallory", "name": "M", "avatar_url": ""}
        self.api("POST", "/api/hub/github/start")
        s, r = self.api("GET", "/api/hub/github/poll")
        self.assertEqual((s, r["error"]["code"]), (403, "not_owner"))
        self.assertFalse((self.data / "hub" / "github.json").exists())
        self.fake.user = {"login": "alice", "name": "Alice Researcher", "avatar_url": ""}
        self.fake.state = "denied"
        self.api("POST", "/api/hub/github/start")
        self.assertEqual(self.api("GET", "/api/hub/github/poll")[1]["state"], "denied")
        self.signin_again()

    def signin_again(self):
        self.api("POST", "/api/hub/github/start")
        self.fake.approve()
        self.assertEqual(self.api("GET", "/api/hub/github/poll")[1]["state"], "ok")

    def test_project_lifecycle_upload_alarm_sync_delete(self):
        self.fake.state = "approved"
        self.signin()
        s, r = self.api("POST", "/api/hub/projects", {"code_repo": "../evil"})
        self.assertEqual(s, 400)
        s, r = self.api("POST", "/api/hub/projects", {"code_repo": "alice/demo-code", "branch": "--upload-pack=x"})
        self.assertEqual(s, 400)
        for other in self.hub.mgr.ids():  # earlier tests may have left projects of the same repo
            self.hub.mgr.delete(other)
        self.fake.unauth_git = 0
        del self.fake.git_requests[:]
        pid = self.make_project()
        root = self.data / "projects" / pid
        # token never lands on disk in the clone, and every fake-git request carried the auth header
        cfgtxt = (root / "code" / ".git" / "config").read_text()
        self.assertNotIn(TOKEN, cfgtxt)
        self.assertNotIn("extraheader", cfgtxt.lower())
        self.assertGreater(len(self.fake.git_requests), 0)
        self.assertEqual(self.fake.unauth_git, 0)
        self.assertTrue(pid.startswith("demo-code-"))
        s, r = self.api("GET", "/api/hub/projects")
        p = [x for x in r["projects"] if x["id"] == pid][0]
        self.assertEqual((p["code_repo"], p["branch"], p["paper_versions"]), ("alice/demo-code", "main", 0))
        self.assertEqual(set(p["counts"]), {"recheck", "findings"})
        # upload 1
        z1 = make_zip({"main.tex": TEX1, "refs.bib": ""}, top="myproject")
        s, r = self.api("POST", "/api/hub/projects/%s/paper" % pid, raw=z1, ctype="application/zip")
        self.assertEqual(s, 200, r)
        self.assertEqual((r["version"], r["files"]), (1, 2))
        self.assertTrue((root / "paper" / "main.tex").is_file())
        # per-project API under /p/<pid>/
        s, proj = self.api("GET", "/p/%s/api/project" % pid)
        self.assertEqual(s, 200)
        self.assertEqual([x["id"] for x in proj["repos"]], ["paper", "code"])
        self.assertEqual(self.api("GET", "/p/%s/api/alarms" % pid)[1]["groups"], [])
        s, cp = self.api("POST", "/p/%s/api/checkpoints" % pid, {"note": "v1 reviewed"})
        self.assertEqual(s, 201, cp)
        # upload 2 changes a number
        z2 = make_zip({"main.tex": TEX1.replace("91.2", "93.4"), "refs.bib": ""}, top="myproject")
        s, r = self.api("POST", "/api/hub/projects/%s/paper" % pid, raw=z2, ctype="application/zip")
        self.assertEqual((s, r["version"]), (200, 2), r)
        s, al = self.api("GET", "/p/%s/api/alarms" % pid)
        self.assertGreaterEqual(len(al["groups"]), 1, al)
        self.assertTrue(any(g["cause"].get("repo") == "paper" for g in al["groups"]), al["groups"])
        # static UI + redirect + 404
        self.assertEqual(self.raw("GET", "/p/%s/" % pid, None, {"Authorization": "Bearer " + self.token})[0], 200)
        s, hd, _ = self.raw("GET", "/p/%s" % pid, None, {"Authorization": "Bearer " + self.token})
        self.assertEqual((s, hd["location"]), (301, "/p/%s/" % pid))
        self.assertEqual(self.api("GET", "/p/nope-0000/api/project")[0], 404)
        self.assertEqual(self.api("GET", "/p/%s/api/health" % pid)[1]["ok"], True)
        # bad zips leave the paper untouched
        before = (root / "paper" / "main.tex").read_text()
        s, r = self.api("POST", "/api/hub/projects/%s/paper" % pid, raw=make_zip({}, extra=[("../x", "y")]), ctype="application/zip")
        self.assertEqual((s, r["error"]["code"]), (400, "bad_zip"))
        self.assertEqual((root / "paper" / "main.tex").read_text(), before)
        self.assertFalse(list(self.data.glob("tmp/*")))
        # sync: nothing new, then a new commit upstream
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertEqual((s, r["changed"]), (200, False))
        self.fake.commit("alice/demo-code", {"eval.py": "print('acc 93.4')\n"}, "update eval")
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertEqual((s, r["changed"]), (200, True), r)
        self.assertEqual((root / "code" / "eval.py").read_text(), "print('acc 93.4')\n")
        self.assertEqual(self.fake.unauth_git, 0, [r for r in self.fake.git_requests if not r[1]])
        # MCP context
        self.assertIn(pid, [x["id"] for x in self.hub.ctx.list_projects()])
        for ref in (pid, "demo-code", "alice/demo-code", "DEMO-CODE"):
            rpid, eng = self.hub.ctx.resolve(ref)
            self.assertEqual(rpid, pid)
        ids = [g["id"] for g in eng.alarms()["groups"]]
        self.assertIn(al["groups"][0]["id"], ids)
        self.assertTrue(any(i.startswith("ev:commit:code:") for i in ids), ids)  # the synced upstream commit
        self.hub.mgr.create(None, "alice/demo-code", None)  # a second project of the same repo makes the name ambiguous
        with self.assertRaises(Exception) as cm:
            self.hub.ctx.resolve("demo-code")
        self.assertEqual(type(cm.exception).__name__, "BadRequest")
        self.assertEqual(self.hub.ctx.resolve(pid)[0], pid)
        with self.assertRaises(Exception) as cm:
            self.hub.ctx.resolve("zzz")
        self.assertEqual(type(cm.exception).__name__, "NotFound")
        self.assertIn("changed", self.hub.ctx.sync(pid))
        # delete -> trash, no hard delete
        s, r = self.api("DELETE", "/api/hub/projects/%s" % pid)
        self.assertEqual(s, 200)
        self.assertFalse(root.exists())
        self.assertTrue(any(self.data.glob("trash/%s-*/paper/main.tex" % pid)))
        self.assertEqual(self.api("GET", "/p/%s/api/project" % pid)[0], 404)

    def test_git_flags_present_and_token_not_in_argv(self):
        flags = " ".join(projects.safe_flags())
        for f in ("core.hooksPath=/dev/null", "core.symlinks=false", "protocol.allow=never", "http.followRedirects=false",
                  "credential.helper=", "submodule.recurse=false"):
            self.assertIn(f, flags)
        with self.assertRaises(projects.ProjectError) as cm:
            projects.git(None, ["clone", "--", self.fake.url + "/nobody/none.git", str(self.data / "tmp" / "x")], token="gho_" + "B" * 30, scope_url=self.fake.url)
        self.assertNotIn("gho_" + "B" * 30, cm.exception.message)

    def test_csp_and_headers(self):
        s, hd, _ = self.raw("GET", "/api/hub/status")
        self.assertIn("frame-ancestors 'none'", hd["content-security-policy"])
        self.assertIn("default-src 'self'", hd["content-security-policy"])
        self.assertEqual(hd["x-content-type-options"], "nosniff")

    def test_pid_validation(self):
        for p in ("/api/hub/projects/Bad_Pid", "/api/hub/projects/" + "a" * 65, "/p/../x/api/project", "/p/UP/api/project"):
            self.assertIn(self.api("GET", p)[0], (404, 405), p)

    def test_hub_static(self):
        s, hd, out = self.raw("GET", "/")
        if (Path(projects.__file__).resolve().parents[1] / "web" / "hub" / "index.html").exists():
            self.assertEqual(s, 200)
        else:
            self.assertEqual(s, 404)
        self.assertEqual(self.raw("GET", "/..%2fserver.py")[0], 404)


if __name__ == "__main__":
    unittest.main()
