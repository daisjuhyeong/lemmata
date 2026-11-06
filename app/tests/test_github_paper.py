"""Paper from a GitHub repo (S06): own repo and a subfolder of a repo, create / switch / sync / validation, Overleaf switched off.
No network: fake GitHub on loopback."""
import json
import secrets
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_overleaf as TO  # noqa: E402
from lemmata.hub import projects  # noqa: E402
from lemmata.hub.projects import valid_subdir  # noqa: E402
from test_hub import CODE, TEX1, make_zip  # noqa: E402

TEX2 = TEX1.replace("91.2", "93.4")
MONO = dict(CODE, **{"paper/main.tex": TEX1, "paper/refs.bib": ""})


class Units(unittest.TestCase):
    def test_subdir_ok(self):
        for v, want in (("paper", "paper"), ("docs/paper/", "docs/paper"), ("a.b/c_d", "a.b/c_d")):
            self.assertEqual(valid_subdir(v), want)

    def test_subdir_rejects(self):
        for v in (None, 5, "", " ", "..", "../x", "a/../b", "a/./b", "/abs", "-x", "a//b", "a\\b", "x" * 201, ".git", "a/.GIT/b",
                  "~/x", "C:/x", "a\x00b", "a\nb", " paper", "./", "."):
            with self.assertRaises(projects.ProjectError, msg=repr(v)) as cm:
                valid_subdir(v)
            self.assertEqual((cm.exception.status, cm.exception.code), (400, "bad_request"))
        valid_subdir("x" * 200)


class GithubPaper(TO.Base):
    def setUp(self):
        self.drop_all()
        tag = secrets.token_hex(3)  # fresh repos per test: commit counts must not depend on test order
        self.paper_repo, self.mono = "alice/paper-" + tag, "alice/mono-" + tag
        self.gh.add_repo(self.paper_repo, {"main.tex": TEX1, "refs.bib": ""})
        self.gh.add_repo(self.mono, MONO)
        self.hub.cfg.update(overleaf_enabled=True)
        self.api("DELETE", "/api/hub/overleaf/token")

    def cause_repos(self, pid):
        s, al = self.api("GET", "/p/%s/api/alarms" % pid)
        self.assertEqual(s, 200)
        return al, [g["cause"] for g in al["groups"]]

    def cp(self, pid):
        s, r = self.api("POST", "/p/%s/api/checkpoints" % pid, {"note": "reviewed"})
        self.assertEqual(s, 201, r)

    def test_own_repo_create_sync_alarm(self):
        p = self.new_project(paper_repo=self.paper_repo)
        pid, root = p["id"], self.data / "projects" / p["id"]
        self.assertEqual(p["paper_source"], {"kind": "github", "repo": self.paper_repo, "branch": "main"})
        self.assertEqual(p["paper_versions"], 1)
        self.assertEqual((root / "paper" / "main.tex").read_text(), TEX1)
        self.assertEqual(projects.git(root / "paper", ["remote", "get-url", "origin"]), "%s/%s.git" % (self.gh.url, self.paper_repo))
        man = json.loads((root / ".lemmata" / "project.json").read_text())
        self.assertEqual(man["repos"][0], {"id": "paper", "role": "paper", "path": "paper"})
        self.assertNotIn(TO.GH_TOKEN, (root / "paper" / ".git" / "config").read_text())
        self.assertEqual(self.api("GET", "/api/hub/projects")[1]["projects"][0]["paper_source"], p["paper_source"])
        self.cp(pid)
        self.assertEqual(self.cause_repos(pid)[1], [])
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertEqual((s, r["paper"]["changed"], r["paper"]["source"]), (200, False, "github"), r)
        self.gh.commit(self.paper_repo, {"main.tex": TEX2}, "Update the accuracy")
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertEqual((s, r["changed"], r["paper"]["changed"]), (200, False, True), r)
        self.assertEqual(r["paper"]["head"], projects.git(root / "paper", ["rev-parse", "HEAD"]))
        al, causes = self.cause_repos(pid)
        self.assertTrue(any(c.get("repo") == "paper" for c in causes), causes)
        self.assertTrue(any("commit" in json.dumps(c) for c in causes), causes)
        self.assertEqual(self.api("GET", "/api/hub/projects/%s" % pid)[1]["paper_versions"], 2)
        # zip upload refused while GitHub is the source
        s, out = self.raw("POST", "/api/hub/projects/%s/paper" % pid, make_zip({"a.tex": "x"}), {"Authorization": "Bearer " + self.token, "Content-Type": "application/zip"})
        self.assertEqual((s, json.loads(out)["error"]["code"]), (409, "paper_is_github"))

    def test_subdir_of_code_repo(self):
        p = self.new_project(code_repo=self.mono, paper_repo=self.mono, paper_subdir="paper")
        pid, root = p["id"], self.data / "projects" / p["id"]
        self.assertEqual(p["paper_source"], {"kind": "github", "repo": self.mono, "branch": "main", "subdir": "paper"})
        self.assertEqual(p["paper_versions"], 1)
        self.assertTrue((root / "paper" / "paper" / "main.tex").is_file())
        self.assertTrue((root / "code" / "eval.py").is_file())  # separate clone of the same repo
        self.assertNotEqual((root / "paper" / ".git").resolve(), (root / "code" / ".git").resolve())
        man = json.loads((root / ".lemmata" / "project.json").read_text())
        self.assertEqual(man["repos"][0], {"id": "paper", "role": "paper", "path": "paper/paper", "git_subdir": True})
        s, st = self.api("GET", "/p/%s/api/project" % pid)
        self.assertEqual(s, 200, st)
        paper = [r for r in st["repos"] if r["id"] == "paper"][0]
        self.assertEqual((paper["vcs"], paper["path"]), ("git", "paper/paper"))
        self.cp(pid)
        self.assertEqual(self.cause_repos(pid)[1], [])
        # a commit outside paper/ moves the paper clone's head but is not a paper change
        self.gh.commit(self.mono, {"eval.py": "print('acc 50')\n"}, "code only")
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertEqual((s, r["changed"], r["paper"]["changed"]), (200, True, True), r)
        self.assertFalse([c for c in self.cause_repos(pid)[1] if c.get("repo") == "paper"])
        self.assertEqual(self.api("GET", "/api/hub/projects/%s" % pid)[1]["paper_versions"], 1)  # history filtered to paper/
        # a commit inside paper/ is a paper cause
        self.gh.commit(self.mono, {"paper/main.tex": TEX2}, "paper: new accuracy")
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertTrue(r["paper"]["changed"], r)
        self.assertEqual((root / "paper" / "paper" / "main.tex").read_text(), TEX2)
        causes = self.cause_repos(pid)[1]
        self.assertTrue(any(c.get("repo") == "paper" and "commit" in json.dumps(c) for c in causes), causes)
        self.assertEqual(self.api("GET", "/api/hub/projects/%s" % pid)[1]["paper_versions"], 2)
        s, hist = self.api("GET", "/p/%s/api/history" % pid)
        if s == 200:
            paper_commits = [e for e in json.dumps(hist).split('"subject"') if "code only" in e[:40]]
            self.assertEqual(paper_commits, [])

    def test_switch_from_zip_and_back(self):
        p = self.new_project()
        pid, root = p["id"], self.data / "projects" / p["id"]
        s, out = self.raw("POST", "/api/hub/projects/%s/paper" % pid, make_zip({"zipfile.tex": "zip\n"}), {"Authorization": "Bearer " + self.token, "Content-Type": "application/zip"})
        self.assertEqual(s, 200, out)
        zip_head = projects.git(root / "paper", ["rev-parse", "HEAD"])
        url = "/api/hub/projects/%s/paper-source" % pid
        s, r = self.api("POST", url, {"kind": "github", "repo": self.mono, "subdir": "paper"})
        self.assertEqual(s, 200, r)
        self.assertEqual((r["kind"], r["repo"], r["branch"], r["subdir"], r["versions"]), ("github", self.mono, "main", "paper", 1))
        self.assertEqual(r["head"], projects.git(root / "paper", ["rev-parse", "HEAD"]))
        prev = list(root.glob("paper.prev-*"))
        self.assertEqual(len(prev), 1)
        self.assertEqual(projects.git(prev[0], ["rev-parse", "HEAD"]), zip_head)
        self.assertEqual(self.api("GET", "/api/hub/projects/%s" % pid)[1]["paper_source"]["subdir"], "paper")
        # to another (own) repo: manifest path goes back to paper
        s, r = self.api("POST", url, {"kind": "github", "repo": self.paper_repo, "branch": "main"})
        self.assertEqual((s, r["kind"], "subdir" in r), (200, "github", False), r)
        man = json.loads((root / ".lemmata" / "project.json").read_text())
        self.assertEqual(man["repos"][0], {"id": "paper", "role": "paper", "path": "paper"})
        self.assertEqual(len(list(root.glob("paper.prev-*"))), 2)
        self.assertEqual(self.api("GET", "/p/%s/api/project" % pid)[0], 200)
        # back to zip from a subfolder source: its files become a fresh zip-style repo
        self.api("POST", url, {"kind": "github", "repo": self.mono, "subdir": "paper"})
        s, r = self.api("POST", url, {"kind": "zip"})
        self.assertEqual((s, r["kind"], r["versions"]), (200, "zip", 1), r)
        self.assertEqual((root / "paper" / "main.tex").read_text(), TEX1)
        self.assertFalse((root / "paper" / "eval.py").exists())
        man = json.loads((root / ".lemmata" / "project.json").read_text())
        self.assertEqual(man["repos"][0], {"id": "paper", "role": "paper", "path": "paper"})
        s, out = self.raw("POST", "/api/hub/projects/%s/paper" % pid, make_zip({"a.tex": "x"}), {"Authorization": "Bearer " + self.token, "Content-Type": "application/zip"})
        self.assertEqual(s, 200, out)
        # own repo -> zip keeps the tree, drops origin
        self.api("POST", url, {"kind": "github", "repo": self.paper_repo})
        s, r = self.api("POST", url, {"kind": "zip"})
        self.assertEqual((s, r["kind"]), (200, "zip"))
        self.assertEqual(projects.git(root / "paper", ["remote"]), "")

    def test_validation_errors(self):
        n = len(self.hub.mgr.ids())
        for kw, code in (({"paper_repo": "nope"}, "bad_request"), ({"paper_repo": "a/b.git"}, "bad_request"),
                         ({"paper_repo": self.mono, "paper_branch": "--x"}, "bad_request"),
                         ({"paper_repo": self.mono, "paper_branch": "a..b"}, "bad_request"),
                         ({"paper_repo": self.mono, "paper_subdir": "../x"}, "bad_request"),
                         ({"paper_repo": self.mono, "paper_subdir": "-x"}, "bad_request"),
                         ({"paper_repo": self.mono, "paper_subdir": "/etc"}, "bad_request"),
                         ({"paper_repo": self.mono, "paper_subdir": "x" * 201}, "bad_request"),
                         ({"paper_subdir": "paper"}, "bad_request"), ({"paper_branch": "main"}, "bad_request"),
                         ({"paper_repo": self.mono, "paper_overleaf": TO.PID1}, "bad_request")):
            s, r = self.api("POST", "/api/hub/projects", dict({"code_repo": "alice/demo-code"}, **kw))
            self.assertEqual((s, r["error"]["code"]), (400, code), kw)
        s, r = self.api("POST", "/api/hub/projects", {"code_repo": "alice/demo-code", "paper_repo": self.mono, "paper_subdir": "nothere"})
        self.assertEqual((s, r["error"]["code"]), (400, "paper_subdir_missing"), r)
        s, r = self.api("POST", "/api/hub/projects", {"code_repo": "alice/demo-code", "paper_repo": self.mono, "paper_subdir": "eval.py"})
        self.assertEqual((s, r["error"]["code"]), (400, "paper_subdir_missing"), r)  # a file is not a folder
        s, r = self.api("POST", "/api/hub/projects", {"code_repo": "alice/demo-code", "paper_repo": "alice/missing-repo"})
        self.assertEqual((s, r["error"]["code"]), (404, "paper_repo_not_found"), r)
        s, r = self.api("POST", "/api/hub/projects", {"code_repo": "alice/demo-code", "paper_repo": self.mono, "paper_branch": "nobranch"})
        self.assertEqual((s, r["error"]["code"]), (404, "paper_branch_not_found"), r)
        self.assertEqual(len(self.hub.mgr.ids()), n)  # nothing half-created
        self.assertEqual(list((self.data / "tmp").iterdir()), [])
        pid = self.new_project()["id"]
        root = self.data / "projects" / pid
        url = "/api/hub/projects/%s/paper-source" % pid
        before = sorted(p.name for p in (root / "paper").iterdir())
        for body, st, code in (({"kind": "github"}, 400, "bad_request"), ({"kind": "github", "repo": self.mono, "subdir": "../.."}, 400, "bad_request"),
                               ({"kind": "github", "repo": self.mono, "subdir": "nothere"}, 400, "paper_subdir_missing"),
                               ({"kind": "github", "repo": "alice/missing-repo"}, 404, "paper_repo_not_found"),
                               ({"kind": "github", "repo": self.mono, "branch": "-x"}, 400, "bad_request"), ({"kind": "bogus"}, 400, "bad_request")):
            s, r = self.api("POST", url, body)
            self.assertEqual((s, r["error"]["code"]), (st, code), body)
        self.assertEqual(self.api("GET", "/api/hub/projects/%s" % pid)[1]["paper_source"], {"kind": "zip"})  # untouched
        self.assertEqual(sorted(p.name for p in (root / "paper").iterdir()), before)
        self.assertEqual(list(root.glob("paper.prev-*")), [])
        self.assertEqual(list((self.data / "tmp").iterdir()), [])

    def test_subdir_removed_upstream_is_not_merged(self):
        name = "tmp-mono-" + secrets.token_hex(2)
        self.gh.add_repo("alice/" + name, MONO)
        pid = self.new_project(paper_repo="alice/" + name, paper_subdir="paper")["id"]
        work = self.gh.root / "work" / "alice" / name
        projects.subprocess.run(["git", "rm", "-rq", "paper"], cwd=str(work), check=True)
        self.gh.commit("alice/" + name, {"other.txt": "x"}, "remove the paper folder")
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertEqual((s, r["paper"]["changed"], r["paper"]["error"]["code"]), (200, False, "paper_subdir_missing"), r)
        self.assertEqual(self.api("GET", "/p/%s/api/project" % pid)[0], 200)  # engine still healthy

    def test_loop_syncs_github_paper(self):
        pid = self.new_project(paper_repo=self.paper_repo)["id"]
        self.gh.commit(self.paper_repo, {"main.tex": TEX2 + "% loop\n"}, "from the loop")
        self.hub.mgr.sync_all()
        self.assertIn("% loop", (self.data / "projects" / pid / "paper" / "main.tex").read_text())

    def test_token_only_in_env(self):
        argvs = []
        real = projects.subprocess.run
        projects.subprocess.run = lambda a, *x, **k: (argvs.append(list(a)), real(a, *x, **k))[1]
        try:
            pid = self.new_project(paper_repo=self.paper_repo)["id"]
            self.api("POST", "/api/hub/projects/%s/sync" % pid)
        finally:
            projects.subprocess.run = real
        paper_calls = [a for a in argvs if any(self.paper_repo in x for x in a)]
        self.assertTrue(paper_calls)
        for a in argvs:
            self.assertNotIn(TO.GH_TOKEN, " ".join(a))
        for a in paper_calls:
            for f in ("core.hooksPath=/dev/null", "protocol.allow=never", "http.followRedirects=false", "credential.helper=", "core.symlinks=false"):
                self.assertIn(f, a)


class OverleafOff(TO.Base):
    def setUp(self):
        self.drop_all()
        self.hub.cfg.update(overleaf_enabled=True)
        self.api("DELETE", "/api/hub/overleaf/token")

    def tearDown(self):
        self.hub.cfg.update(overleaf_enabled=True)

    def test_default_is_off(self):
        from lemmata.hub.config import DEFAULTS
        self.assertIs(DEFAULTS["overleaf_enabled"], False)

    def test_disabled_routes_status_and_loop(self):
        self.set_token()
        pid = self.new_project(paper_overleaf=TO.PID1)["id"]
        self.hub.cfg.update(overleaf_enabled=False)
        self.assertNotIn("overleaf_configured", json.loads(self.raw("GET", "/api/hub/status")[1]))
        off = {"error": "feature_disabled"}
        self.assertEqual(self.api("PUT", "/api/hub/overleaf/token", {"token": "abc"}), (404, off))
        self.assertEqual(self.api("DELETE", "/api/hub/overleaf/token"), (404, off))
        self.assertEqual(self.api("GET", "/api/hub/overleaf/token"), (404, off))
        self.assertEqual(self.api("POST", "/api/hub/projects/%s/paper-source" % pid, {"kind": "overleaf", "project": TO.PID1}), (404, off))
        self.assertEqual(self.api("POST", "/api/hub/projects", {"code_repo": "alice/demo-code", "paper_overleaf": TO.PID1}), (404, off))
        self.assertEqual(len(self.hub.mgr.ids()), 1)
        self.assertEqual(self.raw("PUT", "/api/hub/overleaf/token", b"{}", {"Content-Type": "application/json"})[0], 401)  # still behind the session
        # an existing Overleaf project is never contacted by sync or the loop
        n = len(self.ov.requests)
        s, r = self.api("POST", "/api/hub/projects/%s/sync" % pid)
        self.assertEqual((s, r["paper"].get("skipped"), r["paper"]["changed"]), (200, "feature_disabled", False), r)
        self.hub.mgr.sync_all()
        self.assertEqual(len(self.ov.requests), n)
        # switching to zip / github still works, and the flag back on restores everything
        s, r = self.api("POST", "/api/hub/projects/%s/paper-source" % pid, {"kind": "zip"})
        self.assertEqual((s, r["kind"]), (200, "zip"), r)
        self.hub.cfg.update(overleaf_enabled=True)
        self.assertIn("overleaf_configured", json.loads(self.raw("GET", "/api/hub/status")[1]))
        self.assertEqual(self.api("PUT", "/api/hub/overleaf/token", {"token": "abc"})[0], 200)


if __name__ == "__main__":
    unittest.main()
