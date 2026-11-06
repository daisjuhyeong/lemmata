"""Overleaf paper source (S05): token store, id parsing, switch zip<->Overleaf, sync of both repos, token hygiene.
No network: fake GitHub and fake Overleaf on loopback."""
import http.client
import json
import os
import secrets
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_github import CLIENT_ID, TOKEN as GH_TOKEN, FakeGitHub  # noqa: E402
from fake_overleaf import TOKEN, FakeOverleaf  # noqa: E402
from lemmata.hub import projects  # noqa: E402
from lemmata.hub.overleaf import OverleafError, parse_project  # noqa: E402
from lemmata.hub.routes import Hub, make_hub_server  # noqa: E402
from test_hub import CODE, TEX1, make_zip  # noqa: E402

projects.ALLOWED_PROTOCOLS = ["http", "https"]  # tests only: both fakes speak plain http on loopback
PID1 = "5f1e2d3c4b5a69788796a5b4"
PID2 = "0123456789abcdef01234567"
PID_NONE = "aaaaaaaaaaaaaaaaaaaaaaaa"
TEX2 = TEX1.replace("91.2", "93.4")


class Units(unittest.TestCase):
    def test_parse_ok(self):
        for v in (PID1, PID1.upper(), "https://www.overleaf.com/project/" + PID1, " https://www.overleaf.com/project/%s/ " % PID1,
                  "https://overleaf.com/project/%s?x=1#y" % PID1, "www.overleaf.com/project/" + PID1):
            self.assertEqual(parse_project(v), PID1, v)

    def test_parse_rejects(self):
        for v in (None, 5, "", "  ", "abc", PID1[:-1], PID1 + "0", "zz" + PID1[2:], "https://www.overleaf.com/project/abc",
                  "https://www.overleaf.com/", "http://www.overleaf.com/project/" + PID1, "https://evil.example/project/" + PID1,
                  "https://www.overleaf.com.evil.example/project/" + PID1, "https://u:p@www.overleaf.com/project/" + PID1,
                  "https://git.overleaf.com/" + PID1, "file:///etc/passwd", "https://www.overleaf.com/project/" + PID1 + "x"):
            with self.assertRaises(OverleafError, msg=repr(v)) as cm:
                parse_project(v)
            self.assertEqual((cm.exception.status, cm.exception.code), (400, "bad_request"))

    def test_share_link_message(self):
        for v in ("https://www.overleaf.com/read/abcdefabcdef", "https://www.overleaf.com/read/" + PID1 + "?x=1"):
            with self.assertRaises(OverleafError) as cm:
                parse_project(v)
            self.assertEqual(cm.exception.message, "Use the project link from your Overleaf dashboard, not a share link.")


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gh = FakeGitHub()
        cls.gh.add_repo("alice/demo-code", CODE)
        cls.ov = FakeOverleaf()
        cls.ov.add_project(PID1, {"main.tex": TEX1, "refs.bib": ""})
        cls.ov.add_project(PID2, {"main.tex": TEX1 + "% second\n"})
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name) / "Lemmata"
        cls.hub = Hub(cls.data, port=0, detect_tailscale=False)
        cls.hub.cfg.update(github_client_id=CLIENT_ID, github_api=cls.gh.url, github_web=cls.gh.url, overleaf_git=cls.ov.url, overleaf_enabled=True,
                           overleaf_min_interval=0)
        cls.srv = make_hub_server(cls.hub, host="127.0.0.1", port=0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        code = cls.hub.auth.new_code()
        s, b = cls.raw("POST", "/api/hub/pair", json.dumps({"code": code, "device": "t"}).encode(), {"Content-Type": "application/json"})
        cls.token = json.loads(b)["token"]
        cls.gh.approve()
        assert cls.api("POST", "/api/hub/github/start")[0] == 200
        assert cls.api("GET", "/api/hub/github/poll")[1]["state"] == "ok"

    @classmethod
    def tearDownClass(cls):
        from lemmata.engine import tree
        tree.GIT_ENV_EXTRA.clear()
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.gh.close()
        cls.ov.close()
        cls.tmp.cleanup()

    @classmethod
    def raw(cls, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=60)
        c.request(method, path, body=body, headers=dict({"Host": "127.0.0.1:%d" % cls.port}, **(headers or {})))
        r = c.getresponse()
        out = r.read()
        c.close()
        return r.status, out

    @classmethod
    def api(cls, method, path, body=None, token=None):
        h = {"Authorization": "Bearer " + (token or cls.token)}
        data = None
        if body is None and method in ("POST", "PUT"):
            body = {}
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        s, out = cls.raw(method, path, data, h)
        try:
            return s, json.loads(out)
        except ValueError:
            return s, out

    def set_token(self, t=TOKEN):
        s, r = self.api("PUT", "/api/hub/overleaf/token", {"token": t})
        self.assertEqual((s, r), (200, {"configured": True}))

    def new_project(self, **kw):
        s, r = self.api("POST", "/api/hub/projects", dict({"code_repo": "alice/demo-code"}, **kw))
        self.assertEqual(s, 201, r)
        return r

    def drop_all(self):
        for p in self.hub.mgr.ids():
            self.hub.mgr.delete(p)


class OverleafTest(Base):
    def setUp(self):
        self.p1, self.p2 = secrets.token_hex(12), secrets.token_hex(12)  # fresh Overleaf projects per test
        self.ov.add_project(self.p1, {"main.tex": TEX1, "refs.bib": ""})
        self.ov.add_project(self.p2, {"main.tex": TEX1 + "% second\n"})
        self.drop_all()
        self.api("DELETE", "/api/hub/overleaf/token")
        self.hub.cfg.update(overleaf_min_interval=0)
        self.ov.rate_limit = False
        del self.ov.requests[:]

    def test_token_store_modes_and_status(self):
        path = self.data / "hub" / "overleaf.json"
        s, r = self.raw("GET", "/api/hub/status")
        self.assertFalse(json.loads(r)["overleaf_configured"])
        old = os.umask(0)  # even with umask 0 the file is 0600 from creation
        try:
            self.set_token()
        finally:
            os.umask(old)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.data / "hub").stat().st_mode), 0o700)
        self.assertEqual(json.loads(path.read_text())["token"], TOKEN)
        self.assertEqual(json.loads(self.raw("GET", "/api/hub/status")[1])["overleaf_configured"], True)
        self.assertNotIn(TOKEN, json.dumps(self.api("GET", "/api/hub/status")[1]))
        self.set_token(TOKEN + "x")  # replace stays private
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual([p.name for p in path.parent.iterdir() if "overleaf" in p.name], ["overleaf.json"])  # no temp leftovers
        for bad in (None, "", "   ", "a b", "x" * 400, 5, ["a"], "tab\there"):
            s, r = self.api("PUT", "/api/hub/overleaf/token", {"token": bad})
            self.assertEqual((s, r["error"]["code"]), (400, "bad_request"), bad)
        self.assertEqual(json.loads(path.read_text())["token"], TOKEN + "x")
        s, r = self.api("DELETE", "/api/hub/overleaf/token")
        self.assertEqual((s, r), (200, {"configured": False}))
        self.assertFalse(path.exists())
        self.assertEqual(self.api("DELETE", "/api/hub/overleaf/token")[0], 200)  # idempotent
        self.assertFalse(json.loads(self.raw("GET", "/api/hub/status")[1])["overleaf_configured"])
        s, _ = self.raw("PUT", "/api/hub/overleaf/token", b'{"token":"abc"}', {"Content-Type": "application/json"})
        self.assertEqual(s, 401)  # needs a session
        s, r = self.api("GET", "/api/hub/overleaf/token")
        self.assertEqual(s, 405)

    def test_bad_ids_and_missing_token(self):
        p = self.new_project()
        pid = p["id"]
        self.assertEqual(p["paper_source"], {"kind": "zip"})
        url = "/api/hub/projects/%s/paper-source" % pid
        s, r = self.api("POST", url, {"kind": "overleaf", "project": self.p1})
        self.assertEqual((s, r["error"]["code"]), (409, "overleaf_token_missing"))
        self.set_token()
        for v in ("nope", "https://www.overleaf.com/read/abcdefabcdef", None, "https://example.com/project/" + self.p1):
            s, r = self.api("POST", url, {"kind": "overleaf", "project": v})
            self.assertEqual((s, r["error"]["code"]), (400, "bad_request"), v)
        self.assertIn("share link", self.api("POST", url, {"kind": "overleaf", "project": "https://www.overleaf.com/read/abc"})[1]["error"]["message"])
        s, r = self.api("POST", url, {"kind": "bogus"})
        self.assertEqual(s, 400)
        s, r = self.api("POST", "/api/hub/projects/nope-0000/paper-source", {"kind": "zip"})
        self.assertEqual(s, 404)
        self.assertEqual(self.ov.requests, [])  # nothing reached Overleaf
        s, r = self.api("POST", "/api/hub/projects", {"code_repo": "alice/demo-code", "paper_overleaf": "garbage"})
        self.assertEqual((s, r["error"]["code"]), (400, "bad_request"))
        self.assertEqual(self.hub.mgr.ids(), [pid])  # nothing half-created

    def test_not_found_and_auth_failure_leave_paper_alone(self):
        pid = self.new_project()["id"]
        url = "/api/hub/projects/%s/paper-source" % pid
        paper = self.data / "projects" / pid / "paper"
        self.set_token("olp_WRONGTOKENwrongtokenWRONGTOKEN")
        s, r = self.api("POST", url, {"kind": "overleaf", "project": self.p1})
        self.assertEqual((s, r["error"]["code"]), (502, "overleaf_auth_failed"), r)
        self.assertIn("token missing or expired", r["error"]["message"])
        self.assertNotIn("WRONGTOKEN", json.dumps(r))
        self.set_token()
        s, r = self.api("POST", url, {"kind": "overleaf", "project": PID_NONE})
        self.assertEqual((s, r["error"]["code"]), (404, "overleaf_not_found"), r)
        self.assertEqual(self.api("GET", "/api/hub/projects/%s" % pid)[1]["paper_source"], {"kind": "zip"})
        self.assertTrue((paper / ".git").is_dir())
        self.assertEqual(list((self.data / "projects" / pid).glob("paper.prev-*")), [])
        self.assertEqual(list((self.data / "tmp").iterdir()), [])
        s, r = self.api("POST", "/api/hub/projects", {"code_repo": "alice/demo-code", "paper_overleaf": self.p1})
        self.assertEqual(s, 201)
        self.set_token("olp_WRONGTOKENwrongtokenWRONGTOKEN")
        s, r = self.api("POST", "/api/hub/projects", {"code_repo": "alice/demo-code", "paper_overleaf": self.p1})
        self.assertEqual((s, r["error"]["code"]), (502, "overleaf_auth_failed"))
        self.assertEqual(len(self.hub.mgr.ids()), 2)  # failed creation removed its folder

    def test_create_with_overleaf(self):
        self.set_token()
        p = self.new_project(paper_overleaf="https://www.overleaf.com/project/" + self.p1)
        self.assertEqual(p["paper_source"], {"kind": "overleaf", "project_id": self.p1})
        self.assertEqual(p["paper_versions"], 1)
        root = self.data / "projects" / p["id"]
        self.assertEqual((root / "paper" / "main.tex").read_text(), TEX1)
        s, r = self.api("GET", "/api/hub/projects")
        self.assertEqual([x["paper_source"] for x in r["projects"]], [{"kind": "overleaf", "project_id": self.p1}])
        self.assertNotIn(TOKEN, (root / "paper" / ".git" / "config").read_text())

    def test_switch_from_zip_sync_alarm_and_back(self):
        self.set_token()
        pid = self.new_project()["id"]
        root = self.data / "projects" / pid
        s, out = self.raw("POST", "/api/hub/projects/%s/paper" % pid, make_zip({"zipfile.tex": "zip\n"}), {"Authorization": "Bearer " + self.token, "Content-Type": "application/zip"})
        self.assertEqual(s, 200, out)
        zip_head = projects.git(root / "paper", ["rev-parse", "HEAD"])
        s, r = self.api("POST", "/api/hub/projects/%s/paper-source" % pid, {"kind": "overleaf", "project": "https://www.overleaf.com/project/" + self.p1})
        self.assertEqual(s, 200, r)
        self.assertEqual((r["kind"], r["project_id"], r["versions"]), ("overleaf", self.p1, 1))
        self.assertEqual(r["head"], projects.git(root / "paper", ["rev-parse", "HEAD"]))
        self.assertEqual((root / "paper" / "main.tex").read_text(), TEX1)
        self.assertFalse((root / "paper" / "zipfile.tex").exists())
        prev = list(root.glob("paper.prev-*"))
        self.assertEqual(len(prev), 1)
        self.assertEqual(projects.git(prev[0], ["rev-parse", "HEAD"]), zip_head)  # old repo kept intact
        self.assertEqual(self.api("GET", "/api/hub/projects/%s" % pid)[1]["paper_source"], {"kind": "overleaf", "project_id": self.p1})
        # the remote URL has no credentials; no token anywhere under the project
        self.assertEqual(projects.git(root / "paper", ["remote", "get-url", "origin"]), "%s/%s" % (self.ov.url, self.p1))
        for f in root.rglob("*"):
            if f.is_file() and ".git/objects" not in str(f):
                self.assertNotIn(TOKEN.encode(), f.read_bytes(), str(f))
        # checkpoint, then a new Overleaf commit changes a number -> sync -> alarm
        s, cp = self.api("POST", "/p/%s/api/checkpoints" % pid, {"note": "reviewed"})
        self.assertEqual(s, 201, cp)
        self.assertEqual(self.api("GET", "/p/%s/api/alarms" % pid)[1]["groups"], [])
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertEqual(s, 200, r)
        self.assertEqual((r["changed"], r["code"]["changed"], r["paper"]["changed"]), (False, False, False))
        self.assertEqual(set(r), {"changed", "head", "code", "paper"})
        self.assertEqual(r["head"], r["code"]["head"])
        self.ov.commit(self.p1, {"main.tex": TEX2}, "Update via Overleaf")
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertEqual(s, 200, r)
        self.assertEqual((r["changed"], r["paper"]["changed"]), (False, True), r)
        self.assertEqual(r["paper"]["head"], projects.git(root / "paper", ["rev-parse", "HEAD"]))
        self.assertEqual((root / "paper" / "main.tex").read_text(), TEX2)
        s, al = self.api("GET", "/p/%s/api/alarms" % pid)
        self.assertTrue(any(g["cause"].get("repo") == "paper" for g in al["groups"]), al["groups"])
        self.assertEqual(self.api("GET", "/api/hub/projects/%s" % pid)[1]["paper_versions"], 2)
        # a zip upload is refused while Overleaf is the source
        s, out = self.raw("POST", "/api/hub/projects/%s/paper" % pid, make_zip({"a.tex": "x"}), {"Authorization": "Bearer " + self.token, "Content-Type": "application/zip"})
        self.assertEqual((s, json.loads(out)["error"]["code"]), (409, "paper_is_overleaf"))
        # never pushed
        self.assertFalse([p for p, ok in self.ov.requests if "receive-pack" in p])
        # back to zip: the tree stays, no more Overleaf fetches
        s, r = self.api("POST", "/api/hub/projects/%s/paper-source" % pid, {"kind": "zip"})
        self.assertEqual((s, r["kind"], r["versions"]), (200, "zip", 2), r)
        self.assertNotIn("project_id", r)
        self.assertEqual((root / "paper" / "main.tex").read_text(), TEX2)
        self.assertEqual(self.api("GET", "/api/hub/projects")[1]["projects"][0]["paper_source"], {"kind": "zip"})
        n = self.ov.fetches[self.p1]
        self.ov.commit(self.p1, {"main.tex": TEX2 + "% more\n"}, "again")
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertEqual((s, r["paper"]["changed"]), (200, False))
        self.assertEqual(self.ov.fetches[self.p1], n)
        s, out = self.raw("POST", "/api/hub/projects/%s/paper" % pid, make_zip({"a.tex": "x"}), {"Authorization": "Bearer " + self.token, "Content-Type": "application/zip"})
        self.assertEqual(s, 200, out)  # uploads work again
        # switching to another Overleaf project works and keeps a second prev folder
        s, r = self.api("POST", "/api/hub/projects/%s/paper-source" % pid, {"kind": "overleaf", "project": self.p2})
        self.assertEqual((s, r["project_id"]), (200, self.p2), r)
        self.assertEqual(len(list(root.glob("paper.prev-*"))), 2)

    def test_two_minute_spacing_and_errors_do_not_break_code_sync(self):
        self.set_token()
        pid = self.new_project(paper_overleaf=self.p1)["id"]
        url = "/api/hub/projects/%s/sync" % pid
        self.hub.cfg.update(overleaf_min_interval=120)
        n = self.ov.fetches[self.p1]
        self.ov.commit(self.p1, {"main.tex": TEX2}, "x")
        s, r = self.api("POST", url)  # created just now: too early
        self.assertEqual((s, r["paper"]["changed"], r["paper"].get("skipped")), (200, False, "rate_limited"), r)
        self.assertEqual(self.ov.fetches[self.p1], n)
        m = self.hub.mgr.meta(pid)
        m["overleaf_last_fetch"] -= 121
        self.hub.mgr._save_meta(pid, m)
        s, r = self.api("POST", url)
        self.assertEqual((r["paper"]["changed"], self.ov.fetches[self.p1]), (True, n + 1), r)
        s, r = self.api("POST", url)  # a second call right after is throttled again
        self.assertEqual(r["paper"].get("skipped"), "rate_limited")
        self.assertEqual(self.ov.fetches[self.p1], n + 1)
        # expired token: the error is reported, the code sync still answers 200
        self.hub.cfg.update(overleaf_min_interval=0)
        self.set_token("olp_WRONGTOKENwrongtokenWRONGTOKEN")
        s, r = self.api("POST", url)
        self.assertEqual((s, r["paper"]["error"]["code"]), (200, "overleaf_auth_failed"), r)
        self.api("DELETE", "/api/hub/overleaf/token")
        s, r = self.api("POST", url)
        self.assertEqual(r["paper"]["error"]["code"], "overleaf_token_missing")
        self.set_token()
        self.ov.rate_limit = True  # Overleaf answering 429
        s, r = self.api("POST", url)
        self.assertEqual(s, 200)
        self.assertIn("error", r["paper"])
        self.ov.rate_limit = False
        self.assertEqual(self.hub.mgr.sync_all(), None)  # loop path

    def test_concurrent_syncs_fetch_once_in_window(self):
        self.set_token()
        pid = self.new_project(paper_overleaf=self.p1)["id"]
        self.hub.cfg.update(overleaf_min_interval=120)
        m = self.hub.mgr.meta(pid)
        m["overleaf_last_fetch"] -= 500
        self.hub.mgr._save_meta(pid, m)
        n = self.ov.fetches[self.p1]
        res = []
        ts = [threading.Thread(target=lambda: res.append(self.api("POST", "/api/hub/projects/%s/sync" % pid))) for _ in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(self.ov.fetches[self.p1], n + 1)
        self.assertEqual(sorted(bool(r["paper"].get("skipped")) for _, r in res), [False, True, True, True])

    def test_overleaf_errors_are_short_and_mapped(self):
        self.set_token()
        pid = self.new_project(paper_overleaf=self.p1)["id"]
        self.ov.rate_limit = True
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertEqual(r["paper"]["error"], {"code": "overleaf_rate_limited", "message": "Overleaf is rate-limiting; will retry at the next sync."})
        s, r = self.api("POST", "/api/hub/projects/%s/paper-source" % pid, {"kind": "overleaf", "project": self.p2})
        self.assertEqual((s, r["error"]["code"]), (429, "overleaf_rate_limited"))
        self.assertNotIn("git ", r["error"]["message"])
        self.ov.rate_limit = False

    def test_size_cap_and_stall_flags(self):
        self.set_token()
        pid = self.new_project()["id"]
        old = projects.MAX_UNPACKED
        projects.MAX_UNPACKED = 10
        try:
            s, r = self.api("POST", "/api/hub/projects/%s/paper-source" % pid, {"kind": "overleaf", "project": self.p1})
        finally:
            projects.MAX_UNPACKED = old
        self.assertEqual((s, r["error"]["code"]), (413, "overleaf_too_large"))
        self.assertEqual(self.api("GET", "/api/hub/projects/%s" % pid)[1]["paper_source"], {"kind": "zip"})
        self.assertEqual(list((self.data / "tmp").iterdir()), [])
        argvs = []
        real = projects.subprocess.run
        projects.subprocess.run = lambda a, *x, **k: (argvs.append(list(a)), real(a, *x, **k))[1]
        try:
            self.api("POST", "/api/hub/projects/%s/paper-source" % pid, {"kind": "overleaf", "project": self.p1})
        finally:
            projects.subprocess.run = real
        self.assertTrue(any("http.lowSpeedLimit=1000" in a and "clone" in a for a in argvs))

    def test_loop_syncs_paper(self):
        self.set_token()
        pid = self.new_project(paper_overleaf=self.p1)["id"]
        self.ov.commit(self.p1, {"main.tex": TEX2}, "from the loop")
        self.hub.mgr.sync_all()
        self.assertEqual((self.data / "projects" / pid / "paper" / "main.tex").read_text(), TEX2)

    def test_token_never_in_argv_config_or_errors(self):
        argvs, envs = [], []
        real = projects.subprocess.run

        def spy(args, *a, **kw):
            argvs.append(list(args))
            envs.append(dict(kw.get("env") or {}))
            return real(args, *a, **kw)
        import base64
        b64 = base64.b64encode(("git:%s" % TOKEN).encode()).decode()
        projects.subprocess.run = spy
        try:
            self.set_token()
            pid = self.new_project(paper_overleaf=self.p1)["id"]
            self.ov.commit(self.p1, {"main.tex": TEX2}, "y")
            self.api("POST", "/api/hub/projects/%s/sync" % pid)
            self.api("POST", "/api/hub/projects/%s/paper-source" % pid, {"kind": "overleaf", "project": PID_NONE})
            self.set_token("olp_WRONGTOKENwrongtokenWRONGTOKEN")
            s, r = self.api("POST", "/api/hub/projects/%s/paper-source" % pid, {"kind": "overleaf", "project": self.p1})
            self.set_token()
        finally:
            projects.subprocess.run = real
        ol_calls = [(a, e) for a, e in zip(argvs, envs) if any(self.ov.url in x for x in a) or "GIT_CONFIG_VALUE_0" in e and e["GIT_CONFIG_KEY_0"].startswith("http." + self.ov.url)]
        self.assertGreaterEqual(len(ol_calls), 3)
        for a, e in zip(argvs, envs):
            line = " ".join(a)
            self.assertNotIn(TOKEN, line)
            self.assertNotIn(b64, line)
            self.assertNotIn("WRONGTOKEN", line)
            self.assertNotIn("extraheader", line.lower())
            self.assertNotIn("Authorization", line)
        for a, e in ol_calls:
            self.assertEqual(e["GIT_CONFIG_KEY_0"], "http.%s/.extraHeader" % self.ov.url)
            self.assertIn(e["GIT_CONFIG_VALUE_0"], ("Authorization: Basic " + b64, "Authorization: Basic " + base64.b64encode(b"git:olp_WRONGTOKENwrongtokenWRONGTOKEN").decode()))
            self.assertEqual(e["GIT_CONFIG_GLOBAL"], "/dev/null")
            for f in ("core.hooksPath=/dev/null", "protocol.allow=never", "http.followRedirects=false", "credential.helper="):
                self.assertIn(f, a)
        for f in (self.data / "projects").rglob("config"):
            self.assertNotIn(TOKEN, f.read_text())
        log = (self.data / "hub" / "hub.log")
        if log.exists():
            self.assertNotIn(TOKEN, log.read_text())

    def test_scrub_overleaf_forms(self):
        from lemmata.hub.github import scrub
        import base64
        t = "olp_SECRETSECRETSECRET1234"
        self.assertEqual(scrub("x " + base64.b64encode(("git:" + t).encode()).decode(), t), "x ***")
        self.assertNotIn(t, scrub("fatal: bad " + t, t))

    def test_non_overleaf_host_is_ignored(self):
        from lemmata.hub.overleaf import Overleaf
        o = Overleaf(self.hub.data, self.hub.cfg)
        self.hub.cfg.update(overleaf_git="https://evil.example")
        try:
            self.assertEqual(o.base(), "https://git.overleaf.com")
            self.hub.cfg.update(overleaf_git="http://git.overleaf.com")
            self.assertEqual(o.base(), "https://git.overleaf.com")
        finally:
            self.hub.cfg.update(overleaf_git=self.ov.url)
        self.assertEqual(o.base(), self.ov.url)


if __name__ == "__main__":
    unittest.main()
