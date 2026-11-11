"""Public-site tests (S07): GitHub sign-in without pairing, per-user projects, sign-in errors, A/B views, research API.

    PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p "test_public.py"
"""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_github import CLIENT_ID, FakeGitHub  # noqa: E402
from lemmata.hub import projects  # noqa: E402
from lemmata.hub.routes import Hub, make_hub_server  # noqa: E402

projects.ALLOWED_PROTOCOLS = ["http", "https"]
PUBLIC = "lemmata.example.ts.net"
BOB_TOKEN = "gho_BOBTOKENbobtokenBOBTOKENbobtokenBOB12345"
TEX = r"""\documentclass{article}
\newtheorem{theorem}{Theorem}
\begin{document}
\begin{abstract}We show a bound and test it.\end{abstract}
\section{Introduction}
Our contributions:
\begin{itemize}
\item We prove a lower bound (Theorem~\ref{thm:a}).
\item We measure accuracy on the benchmark and report it in a table.
\end{itemize}
\begin{theorem}\label{thm:a}The bound holds.\end{theorem}
\begin{proof}Direct.\end{proof}
\section{Results}
\begin{table}
% source: code:results/acc.csv
\caption{Accuracy on the benchmark.}\label{tab:acc}
\begin{tabular}{lr} ours & 0.91 \\ \end{tabular}
\end{table}
\end{document}
"""


class PublicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeGitHub()
        cls.fake.accounts[BOB_TOKEN] = {"login": "bob", "name": "Bob", "avatar_url": ""}
        cls.fake.add_repo("alice/secret", {"README.md": "# alice\n"})
        cls.fake.add_repo("bob/work", {"paper/main.tex": TEX, "results/acc.csv": "m,acc\nours,0.91\n", "eval.py": "open('results/acc.csv','w')\n"})
        cls.tmp = tempfile.TemporaryDirectory()
        cls.hub = Hub(Path(cls.tmp.name) / "Lemmata", port=0, detect_tailscale=False)
        cls.hub.cfg.update(github_client_id=CLIENT_ID, github_api=cls.fake.url, github_web=cls.fake.url,
                           public_url="https://" + PUBLIC, signup="open")
        cls.hub = Hub(Path(cls.tmp.name) / "Lemmata", port=0, detect_tailscale=False)   # re-read config (public_url is read at start)
        cls.srv = make_hub_server(cls.hub, host="127.0.0.1", port=0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.alice = cls.login(None)      # first sign-in becomes the hub owner
        cls.bob = cls.login(BOB_TOKEN)

    @classmethod
    def tearDownClass(cls):
        from lemmata.engine import tree
        tree.GIT_ENV_EXTRA.clear()
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.fake.close()
        cls.tmp.cleanup()

    @classmethod
    def req(cls, method, path, body=None, cookie=None, headers=None, host=PUBLIC):
        c = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=60)
        h = {"Host": host}
        if cookie:
            h["Cookie"] = cookie
        data = None
        if method in ("POST", "PATCH", "DELETE") or body is not None:
            data = json.dumps(body if body is not None else {}).encode()
            h["Content-Type"] = "application/json"
            h["Origin"] = "https://" + PUBLIC
        h.update(headers or {})
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        out = r.read()
        hd = dict((k.lower(), v) for k, v in r.getheaders())
        c.close()
        try:
            return r.status, json.loads(out), hd
        except ValueError:
            return r.status, out, hd

    @classmethod
    def login(cls, token):
        cls.fake.issue, cls.fake.state = token, "pending"
        s, r, _ = cls.req("POST", "/api/hub/login/start", {})
        assert s == 200, r
        s, p, _ = cls.req("GET", "/api/hub/login/poll?flow=" + r["flow"])
        assert p["state"] == "pending", p
        cls.fake.approve()
        s, p, hd = cls.req("GET", "/api/hub/login/poll?flow=" + r["flow"])
        assert s == 200 and p["state"] == "ok", p
        ck = hd["set-cookie"]
        assert "Secure" in ck and "HttpOnly" in ck and "SameSite=Lax" in ck, ck
        return ck.split(";")[0]

    def test_1_sign_in_without_pairing_and_status(self):
        s, st, _ = self.req("GET", "/api/hub/status")
        self.assertEqual((st["authenticated"], st["mode"]), (False, "public"))
        self.assertIsNone(st["owner"])
        s, st, _ = self.req("GET", "/api/hub/status", cookie=self.bob)
        self.assertEqual((st["user"]["login"], st["is_admin"]), ("bob", False))
        self.assertIn(st["start_view"], ("claims", "inbox", "timeline", "ask"))
        s, sa, _ = self.req("GET", "/api/hub/status", cookie=self.alice)
        self.assertTrue(sa["is_admin"])
        self.assertNotEqual(sa["variant"], st["variant"])   # balanced assignment
        self.assertEqual(self.req("POST", "/api/hub/pair", {"code": "X", "device": "d"})[0], 404)
        self.assertEqual(self.req("GET", "/api/hub/projects")[0], 401)
        # a cross-site POST cannot start a sign-in, and an unknown flow is not found
        self.assertEqual(self.req("POST", "/api/hub/login/start", {}, headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.req("GET", "/api/hub/login/poll?flow=web_nope")[1]["state"], "error")

    def test_2_each_person_sees_only_their_repos_and_projects(self):
        s, r, _ = self.req("GET", "/api/hub/github/repos", cookie=self.bob)
        self.assertEqual([x["full_name"] for x in r["repos"]], ["bob/work"])
        s, p, _ = self.req("POST", "/api/hub/projects", {"code_repo": "bob/work", "paper_repo": "bob/work", "paper_subdir": "paper"}, cookie=self.bob)
        self.assertEqual(s, 201, p)
        pid = p["id"]
        type(self).pid = pid
        self.assertEqual(p["owner"], "bob")
        self.assertEqual([x["id"] for x in self.req("GET", "/api/hub/projects", cookie=self.bob)[1]["projects"]], [pid])
        self.assertEqual(self.req("GET", "/api/hub/projects", cookie=self.alice)[1]["projects"], [])
        for path in ("/api/hub/projects/" + pid, "/p/%s/api/project" % pid, "/p/%s/" % pid):
            self.assertEqual(self.req("GET", path, cookie=self.alice)[0], 404, path)
        self.assertEqual(self.req("DELETE", "/api/hub/projects/" + pid, cookie=self.alice)[0], 404)
        self.assertEqual(self.req("GET", "/p/%s/api/project" % pid, cookie=self.bob)[0], 200)
        self.assertEqual(self.hub.mgr.sync(pid)["changed"], False)   # syncs with bob's own sign-in

    def test_3_claims_and_research_tools(self):
        pid = self.pid
        base = "/p/%s/api" % pid
        s, d, _ = self.req("GET", base + "/claims", cookie=self.bob)
        self.assertEqual(s, 200, d)
        by = {c["id"]: c for c in d["claims"]}
        self.assertEqual(by["stmt:thm:a"]["status"], "supported")
        self.assertEqual(by["contrib:1"]["status"], "supported")
        self.assertEqual(by["contrib:2"]["status"], "unsupported")
        self.assertEqual([x["how"] for x in by["contrib:2"]["support"]], ["suggested"])
        s, d, _ = self.req("POST", base + "/claims/link", {"id": "contrib:2", "target": "tex:tab:acc"}, cookie=self.bob)
        self.assertEqual(s, 200, d)
        s, d, _ = self.req("POST", base + "/claims", {"id": "contrib:2", "state": "confirmed"}, cookie=self.bob)
        c2 = next(c for c in d["claims"] if c["id"] == "contrib:2")
        self.assertEqual((c2["state"], c2["status"]), ("confirmed", "supported"))
        self.assertEqual(d["core"]["status"], "supported")
        self.assertEqual(self.req("POST", base + "/claims", {"id": "nope", "state": "confirmed"}, cookie=self.bob)[0], 404)
        s, md, hd = self.req("GET", base + "/claims.md", cookie=self.bob)
        self.assertIn(b"## Core message", md)
        s, t, _ = self.req("POST", base + "/feedback", {"text": "- Table 1 needs a baseline\n- clarify the proof of Theorem 1", "source": "Advisor"}, cookie=self.bob)
        self.assertEqual((s, t["counts"]["open"]), (201, 2))
        self.assertEqual(t["tasks"][0]["targets"][0]["name"], "Table 1")
        self.assertEqual(t["tasks"][1]["claims"][0]["id"], "stmt:thm:a")
        s, t, _ = self.req("POST", base + "/tasks", {"id": "t1", "state": "done"}, cookie=self.bob)
        self.assertEqual(t["counts"], {"open": 1, "done": 1})
        s, t, _ = self.req("GET", base + "/tree", cookie=self.bob)
        ids = {n["id"]: n for n in t["nodes"]}
        self.assertEqual(ids["core"]["title"], "We show a bound and test it.")
        self.assertEqual((ids["contrib:1"]["parent"], ids["stmt:thm:a"]["parent"]), ("core", "contrib:1"))
        self.assertEqual(ids["tex:tab:acc"]["band"], 1)
        self.assertTrue(any(e["from"] == "contrib:2" and e["to"] == "tex:tab:acc" and e["how"] == "manual" for e in t["edges"]))
        self.assertTrue(any(n["band"] == 2 for n in t["nodes"] if n["layer"] == "root"))
        self.assertFalse(any(n["kind"] == "missing" for n in t["nodes"]))
        for route in ("/timeline", "/ledger", "/digest"):
            self.assertEqual(self.req("GET", base + route, cookie=self.bob)[0], 200, route)
        s, a, _ = self.req("POST", base + "/ask", {"question": "which claims are unsupported?"}, cookie=self.bob)
        self.assertEqual((s, a["intent"], a["ai"]), (200, "gaps", False))
        self.assertEqual(self.req("POST", base + "/claims", {"id": "contrib:1", "state": "confirmed"}, cookie=self.alice)[0], 404)

    def test_4_github_errors_are_told_apart_and_reconnect_keeps_the_session(self):
        self.hub.gh._repos.clear()
        self.fake.fail = "rate"
        s, r, _ = self.req("GET", "/api/hub/github/repos", cookie=self.bob)
        self.assertEqual((s, r["error"]["code"]), (429, "github_rate_limited"))
        self.assertIn("2 minutes", r["error"]["message"])
        self.fake.fail = "forbidden"
        s, r, _ = self.req("GET", "/api/hub/github/repos", cookie=self.bob)
        self.assertEqual((s, r["error"]["code"]), (403, "github_forbidden"))
        self.assertFalse(self.req("GET", "/api/hub/status", cookie=self.bob)[1]["github_needs_reauth"])
        self.fake.fail = "revoked"
        s, r, _ = self.req("GET", "/api/hub/github/repos", cookie=self.bob)
        self.assertEqual((s, r["error"]["code"]), (401, "github_token_invalid"))
        self.fake.fail = None
        st = self.req("GET", "/api/hub/status", cookie=self.bob)[1]
        self.assertTrue(st["authenticated"] and st["github_needs_reauth"])   # still signed in to Lemmata; only GitHub needs renewing
        # reconnect in place: same session, no sign-out; approving as another account is refused
        self.fake.issue, self.fake.state = None, "pending"
        self.assertEqual(self.req("POST", "/api/hub/github/start", {}, cookie=self.bob)[0], 200)
        self.fake.approve()
        s, r, _ = self.req("GET", "/api/hub/github/poll", cookie=self.bob)
        self.assertEqual((s, r["error"]["code"]), (403, "wrong_account"))
        self.fake.issue, self.fake.state = BOB_TOKEN, "pending"
        self.req("POST", "/api/hub/github/start", {}, cookie=self.bob)
        self.fake.approve()
        self.assertEqual(self.req("GET", "/api/hub/github/poll", cookie=self.bob)[1]["state"], "ok")
        self.assertFalse(self.req("GET", "/api/hub/status", cookie=self.bob)[1]["github_needs_reauth"])
        # the repository list is cached: typing in the search box does not call GitHub again
        n = self.fake.api_calls
        for q in ("w", "wo", "wor"):
            self.assertEqual(len(self.req("GET", "/api/hub/github/repos?q=" + q, cookie=self.bob)[1]["repos"]), 1)
        self.assertLessEqual(self.fake.api_calls - n, 1)

    def test_5_views_events_tokens_and_invites(self):
        self.assertEqual(self.req("POST", "/api/hub/prefs", {"view": "timeline"}, cookie=self.bob)[0], 200)
        self.assertEqual(self.req("GET", "/api/hub/status", cookie=self.bob)[1]["start_view"], "timeline")
        self.assertEqual(self.req("POST", "/api/hub/prefs", {"view": "bogus"}, cookie=self.bob)[0], 400)
        self.assertEqual(self.req("POST", "/api/hub/events", {"event": "view_open", "view": "claims"}, cookie=self.bob)[0], 200)
        self.assertEqual(self.req("POST", "/api/hub/events", {"event": "drop table"}, cookie=self.bob)[0], 400)
        self.assertEqual(self.req("GET", "/api/hub/admin/ab", cookie=self.bob)[0], 404)
        s, ab, _ = self.req("GET", "/api/hub/admin/ab", cookie=self.alice)
        self.assertEqual((s, sum(v["users"] for v in ab["variants"])), (200, 2))
        self.assertNotIn("bob", self.hub.data.events_path.read_text())   # people are stored as hashes
        s, t, _ = self.req("POST", "/api/hub/tokens", {"name": "Claude Code"}, cookie=self.bob)
        self.assertEqual(s, 201, t)
        self.assertEqual(t["mcp_url"], "https://%s/mcp" % PUBLIC)
        fake_mcp = sys.modules.pop("lemmata.mcp", None)   # test_hub may have left a stub module there; use the real one
        import lemmata
        if hasattr(lemmata, "mcp"):
            delattr(lemmata, "mcp")
        self.addCleanup(lambda: fake_mcp is not None and sys.modules.__setitem__("lemmata.mcp", fake_mcp))
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_projects", "arguments": {}}}
        s, r, _ = self.req("POST", "/mcp", body, headers={"Authorization": "Bearer " + t["token"]})
        self.assertEqual(s, 200, r)
        self.assertIn(self.pid, json.dumps(r))
        # invite-only: a new person is refused, an invited one gets in
        self.hub.cfg.update(signup="invite")
        self.fake.accounts["gho_carol"] = {"login": "carol", "name": "Carol", "avatar_url": ""}
        self.fake.issue, self.fake.state = "gho_carol", "approved"
        s, r, _ = self.req("POST", "/api/hub/login/start", {})
        s, p, _ = self.req("GET", "/api/hub/login/poll?flow=" + r["flow"])
        self.assertEqual((s, p["error"]["code"]), (403, "not_invited"))
        self.hub.cfg.update(allowed_users=["carol"])
        s, r, _ = self.req("POST", "/api/hub/login/start", {})
        self.assertEqual(self.req("GET", "/api/hub/login/poll?flow=" + r["flow"])[1]["state"], "ok")

    def test_6_delete_account_removes_projects_token_and_sessions(self):
        s, r, _ = self.req("DELETE", "/api/hub/account", cookie=self.bob)
        self.assertEqual((s, r["projects_removed"]), (200, 1))
        self.assertEqual(self.req("GET", "/api/hub/projects", cookie=self.bob)[0], 401)
        self.assertIsNone(self.hub.gh.stored("bob"))
        self.assertEqual(self.hub.mgr.ids("bob"), [])
        self.assertEqual(self.req("DELETE", "/api/hub/account", cookie=self.alice)[0], 400)


if __name__ == "__main__":
    unittest.main()
