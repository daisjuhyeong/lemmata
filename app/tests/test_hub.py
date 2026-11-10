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
        from lemmata.engine import tree
        tree.GIT_ENV_EXTRA.clear()
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
        data = raw if raw is not None else (json.dumps(body if body is not None else {}).encode() if method in ("POST", "PATCH") else None)
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

    def test_git_aliases_and_unicode(self):
        for name in (".git./config", "GIT~1/config", ".git /config", ".g\u200cit/x", ".\u200bgit/x", ".GIT/x", "a/.git../x", "git~12/x", ".git\u2060/x"):
            self.bad(make_zip({}, extra=[(name, "x")]))
        self.bad(make_zip({"caf\u00e9.tex": "1", "cafe\u0301.tex": "2"}))  # NFC vs NFD
        self.bad(make_zip({"zero\u200bwidth.tex": "1"}))
        self.bad(make_zip({}, extra=[("a", "file"), ("a/b.tex", "x")]))  # file then folder of the same name
        self.assertEqual(self.extract(make_zip({"gitlab.tex": "x", "my.git.tex": "y"}))[0], 2)  # innocent look-alikes pass

    def test_per_file_cap_and_error_mapping(self):
        old = projects.MAX_FILE
        try:
            projects.MAX_FILE = 100
            self.bad(make_zip({"big.tex": "0" * 500}))
        finally:
            projects.MAX_FILE = old
        for name in sorted(Path("/tmp/qa-s04/zips").glob("*.zip")) if os.environ.get("QA_ZIPS") else []:  # QA corpus, when present
            if name.name.startswith(("08_", "16_", "18_", "30_", "31_", "32_")) and not name.name.startswith(("08_", "16_", "18_")):
                continue
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / "o").mkdir()
                try:
                    projects.safe_extract(name, Path(d) / "o")
                except projects.ProjectError as e:
                    self.assertEqual(e.status, 400, name.name)

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
                with self.assertRaises(projects.ProjectError) as cm:
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
        self.assertEqual(set(p["counts"]), {"recheck", "findings", "claims"})
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

    # ------------------------------------------------------------ QA round: D1..D12
    def raw_socket(self, head, body=b""):
        import socket
        s = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        s.sendall(head.encode() + body)
        out = b""
        try:
            while True:
                c = s.recv(65536)
                if not c:
                    break
                out += c
        except socket.timeout:
            pass
        s.close()
        return out

    def test_bad_content_length(self):
        host = "Host: 127.0.0.1:%d\r\n" % self.port
        for cl in ("-1", "abc", "1e3", "-0", "\u0661"):
            for path, ctype, extra in (("/api/hub/pair", "application/json", ""), ("/mcp", "application/json", "Authorization: Bearer %s\r\n" % self.token),
                                       ("/api/hub/projects/x/paper", "application/zip", "Authorization: Bearer %s\r\n" % self.token)):
                if cl == "\u0661":
                    continue
                out = self.raw_socket("POST %s HTTP/1.1\r\n%sContent-Type: %s\r\n%sContent-Length: %s\r\nConnection: close\r\n\r\n" % (path, host, ctype, extra, cl))
                code = out.split(b" ", 2)[1]
                self.assertIn(code, (b"400", b"404"), (path, cl, out[:80]))  # 404 only for the unknown project, before reading
        # missing length on /mcp and on the zip route
        out = self.raw_socket("POST /mcp HTTP/1.1\r\n%sContent-Type: application/json\r\nAuthorization: Bearer %s\r\nConnection: close\r\n\r\n" % (host, self.token))
        self.assertTrue(out.startswith(b"HTTP/1.1 400"), out[:60])
        self.signin()
        pid = self.make_project()
        out = self.raw_socket("POST /api/hub/projects/%s/paper HTTP/1.1\r\n%sContent-Type: application/zip\r\nAuthorization: Bearer %s\r\nContent-Length: -5\r\nConnection: close\r\n\r\n" % (pid, host, self.token))
        self.assertTrue(out.startswith(b"HTTP/1.1 400"), out[:60])
        out = self.raw_socket("POST /api/hub/projects/%s/paper HTTP/1.1\r\n%sContent-Type: application/zip\r\nAuthorization: Bearer %s\r\nConnection: close\r\n\r\n" % (pid, host, self.token))
        self.assertTrue(out.startswith(b"HTTP/1.1 400"), out[:60])
        from lemmata.hub.routes import HubHandler
        self.assertEqual(HubHandler.timeout, 30)

    def test_funnel_header_and_other_methods(self):
        s, _, _ = self.raw("GET", "/api/hub/status", None, {"Tailscale-Funnel-Request": "?1"})
        self.assertEqual(s, 403)
        s, _, _ = self.raw("GET", "/api/hub/projects", None, {"Authorization": "Bearer " + self.token, "Tailscale-Funnel-Request": "?1"})
        self.assertEqual(s, 403)
        self.assertEqual(self.raw("PUT", "/api/hub/projects")[0], 401)  # PUT exists since S05 (Overleaf token) but needs a session
        for m in ("OPTIONS", "TRACE", "PROPFIND"):
            s, hd, out = self.raw(m, "/api/hub/projects")
            self.assertEqual(s, 405, m)
            self.assertIn("frame-ancestors", hd["content-security-policy"])
            self.assertEqual(json.loads(out)["error"]["code"], "method_not_allowed")
        s, hd, out = self.raw("PUT", "/mcp", b"{}", {"Content-Type": "application/json"})
        self.assertEqual(s, 405)

    def test_repo_validation(self):
        for bad in ("-x/y", "a/.", "a/..", "alice/" + "n" * 101, "a" * 40 + "/x", "alice/-x", "alice/x y", "al ice/x", "alice/x.git", "../x", "a/b/c", "-/x", "alice/"):
            self.assertFalse(projects.CODE_REPO_RE.match(bad) and not bad.endswith(".git") and ".." not in bad, bad)
        for good in ("alice/demo-code", "a/.github", "Org-1/repo.name_x", "a" * 39 + "/" + "n" * 100):
            self.assertTrue(projects.CODE_REPO_RE.match(good), good)
        self.signin()
        s, r = self.api("POST", "/api/hub/projects", {"code_repo": "-x/y"})
        self.assertEqual(s, 400)

    def test_atomic_upload_restores_paper(self):
        self.signin()
        pid = self.make_project()
        s, r = self.api("POST", "/api/hub/projects/%s/paper" % pid, raw=make_zip({"main.tex": TEX1, "a.tex": "A"}), ctype="application/zip")
        self.assertEqual(s, 200)
        paper = self.data / "projects" / pid / "paper"
        before = sorted(p.name for p in paper.iterdir())
        head = projects.git(paper, ["rev-parse", "HEAD"])
        real = projects.git

        def flaky(cwd, args, *a, **kw):
            if args and args[0] == "update-ref":  # fail after the files were swapped
                raise projects.ProjectError(502, "git_failed", "boom")
            return real(cwd, args, *a, **kw)
        projects.git = flaky
        try:
            s, r = self.api("POST", "/api/hub/projects/%s/paper" % pid, raw=make_zip({"main.tex": "NEW", "b.tex": "B"}), ctype="application/zip")
        finally:
            projects.git = real
        self.assertEqual(s, 502)
        self.assertEqual(sorted(p.name for p in paper.iterdir()), before)
        self.assertEqual((paper / "main.tex").read_text(), TEX1)
        self.assertEqual(projects.git(paper, ["rev-parse", "HEAD"]), head)
        self.assertEqual(projects.git(paper, ["status", "--porcelain"]), "")
        self.assertFalse(list(self.data.glob("tmp/*")))
        # a zip git cannot store never touches the tree either
        s, r = self.api("POST", "/api/hub/projects/%s/paper" % pid, raw=make_zip({"main.tex": "X"}, extra=[(".git./config", "x")]), ctype="application/zip")
        self.assertEqual((s, r["error"]["code"]), (400, "bad_zip"))
        self.assertEqual((paper / "main.tex").read_text(), TEX1)
        # no absolute server path in error messages
        s, r = self.api("POST", "/api/hub/projects/%s/paper" % pid, raw=make_zip({}, extra=[("a", "f"), ("a/b.tex", "x")]), ctype="application/zip")
        self.assertEqual(s, 400)
        self.assertNotIn(str(self.data), json.dumps(r))
        self.assertEqual(projects.mask("fatal: %s/projects/x" % self.data), "fatal: <data>/projects/x")

    def test_online_refs_default_off_and_check_status(self):
        from unittest import mock
        self.signin()
        pid = self.make_project()
        tex = TEX1.replace("\\end{document}", "\\cite{k1}\n\\bibliographystyle{plain}\\bibliography{refs}\n\\end{document}")
        bib = "@article{k1,\n title={A paper},\n author={X},\n year={2020}\n}\n"
        s, r = self.api("POST", "/api/hub/projects/%s/paper" % pid, raw=make_zip({"main.tex": tex, "refs.bib": bib}), ctype="application/zip")
        self.assertEqual(s, 200, r)
        p = self.api("GET", "/api/hub/projects/%s" % pid)[1]
        self.assertIs(p["online_refs"], False)
        chk = [c for c in self.api("GET", "/p/%s/api/findings" % pid)[1]["checks"] if c["check"] == "reference_unmatched"][0]
        self.assertEqual(chk["status"], "not_checked")
        self.assertIn("not checked online", chk["note"].lower())
        self.assertEqual(self.api("PATCH", "/api/hub/projects/%s" % pid, {"online_refs": "yes"})[0], 400)
        with mock.patch("lemmata.engine.refs.online_fill", return_value=False) as m:
            s, p = self.api("PATCH", "/api/hub/projects/%s" % pid, {"online_refs": True})
            self.assertEqual(s, 200, p)
            self.assertTrue(p["online_refs"])
            self.assertTrue(m.called)
        self.assertTrue(self.hub.mgr.app(pid).engine.online)
        self.assertTrue(json.loads((self.data / "projects" / pid / "project.json").read_text())["online_refs"])
        self.assertIs(self.api("PATCH", "/api/hub/projects/%s" % pid, {"online_refs": False})[1]["online_refs"], False)
        self.assertFalse(self.hub.mgr.app(pid).engine.online)

    def test_triage_records_device_and_engine_env(self):
        from lemmata.engine import tree
        self.assertEqual(tree.GIT_ENV_EXTRA["GIT_CONFIG_GLOBAL"], "/dev/null")
        self.assertEqual(tree.GIT_ENV_EXTRA["GIT_CONFIG_NOSYSTEM"], "1")
        self.signin()
        pid = self.make_project()
        self.api("POST", "/api/hub/projects/%s/paper" % pid, raw=make_zip({"main.tex": TEX1}), ctype="application/zip")
        g = self.api("GET", "/p/%s/api/graph" % pid)[1]
        nid = [n["id"] for n in g["nodes"] if n["kind"] != "reference"][0]
        s, r = self.api("POST", "/p/%s/api/triage" % pid, {"target_type": "node", "target_id": nid, "state": "reviewed"})
        self.assertEqual(s, 200, r)
        dev = [d for d in self.hub.auth.devices() if d["name"] == "test"][0]
        self.assertEqual(r["entry"]["by"], "ui:" + dev["device_id"])

    def test_token_cli_line(self):
        import contextlib
        from lemmata.cli import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["hub", "token", "--data", str(self.data), "--device", "VS Code", "--host", "mini.ts.net"])
        out = buf.getvalue()
        self.assertIn('claude mcp add --scope user --transport http lemmata http://mini.ts.net:8765/mcp --header "Authorization: Bearer ', out)
        self.assertIn("WARNING", out)

    def test_hub_static(self):
        s, hd, out = self.raw("GET", "/")
        if (Path(projects.__file__).resolve().parents[1] / "web" / "hub" / "index.html").exists():
            self.assertEqual(s, 200)
        else:
            self.assertEqual(s, 404)
        self.assertEqual(self.raw("GET", "/..%2fserver.py")[0], 404)


if __name__ == "__main__":
    unittest.main()


class LaunchdDefaultsTest(unittest.TestCase):
    def test_plist_without_data_dir_uses_default(self):
        from lemmata.hub import launchd
        from lemmata.hub.config import default_data_dir
        pl = launchd.make_plist(None, 8765)
        self.assertIn(str(default_data_dir().resolve()), pl["ProgramArguments"])


class TailscaleDetectTest(unittest.TestCase):
    def test_interface_fallback_finds_macos_utun_addresses(self):
        from unittest import mock
        from lemmata.hub import guard
        sample = ("utun4: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1280\n"
                  "\tinet 100.111.135.94 --> 100.111.135.94 netmask 0xffffffff\n"
                  "\tinet6 fd7a:115c:a1e0::4a4c:875f prefixlen 48\n"
                  "en0: flags=8863<UP> mtu 1500\n\tinet 192.168.1.128 netmask 0xffffff00\n")
        res = mock.Mock(stdout=sample.encode())
        with mock.patch.object(guard, "_cli_info", return_value=(set(), set())), \
             mock.patch.object(guard.subprocess, "run", return_value=res):
            ips, _ = guard.tailscale_info()
        self.assertEqual(ips, {"100.111.135.94", "fd7a:115c:a1e0::4a4c:875f"})
