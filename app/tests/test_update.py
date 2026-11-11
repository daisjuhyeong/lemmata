"""Self-update (S10): follow a branch, check the new code starts, restart, roll back.  Uses a local repository as 'GitHub'."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lemmata.hub import update
from lemmata.hub.config import Config, DataDir

REPO = Path(__file__).resolve().parents[2]


def git(cwd, *a):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t"] + list(a), cwd=str(cwd), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        # a small "GitHub": just the app source, committed on branch live
        self.work = self.tmp / "work"
        (self.work / "app").mkdir(parents=True)
        shutil.copytree(REPO / "app" / "src", self.work / "app" / "src", ignore=shutil.ignore_patterns("__pycache__", "vendor"))
        git(self.work, "init", "-q", "-b", "live")
        git(self.work, "add", "-A")
        git(self.work, "commit", "-qm", "first")
        self.origin = self.tmp / "origin.git"
        git(self.tmp, "clone", "-q", "--bare", str(self.work), str(self.origin))
        git(self.work, "remote", "add", "origin", "https://user:SECRET@example.invalid/x.git")
        git(self.work, "remote", "set-url", "origin", str(self.origin))
        self.data = DataDir(self.tmp / "L").ensure()
        self.cfg = Config(self.data)
        self.restarts = []
        self.lines = []

    def push(self, path, text, msg):
        p = self.work / path
        p.write_text(text)
        git(self.work, "add", "-A")
        git(self.work, "commit", "-qm", msg)
        git(self.work, "push", "-q", "origin", "live")
        return git(self.work, "rev-parse", "HEAD")

    def run_update(self, healthy=True):
        return update.run(self.data, self.cfg, restart=lambda: self.restarts.append(1) or True, check=lambda port, wait=45: healthy, out=self.lines.append)

    def test_follow_update_fail_and_roll_back(self):
        self.assertEqual(self.run_update(), "not_set_up")
        dep = update.setup(self.data, self.cfg, source=self.work, out=self.lines.append)
        self.assertEqual(self.cfg.load()["update_branch"], "live")
        first = git(dep, "rev-parse", "HEAD")
        self.assertEqual(self.run_update(), "none")                      # nothing new: nothing happens, no restart
        self.assertEqual(self.restarts, [])
        # 1. a good change is deployed
        new = self.push("app/src/lemmata/NOTE.txt", "hello\n", "add a note")
        self.assertEqual(self.run_update(), "updated")
        self.assertEqual((git(dep, "rev-parse", "HEAD"), len(self.restarts)), (new, 1))
        st = update.state(self.data)
        self.assertEqual((st["result"], st["subjects"], st["from"], st["to"]), ("updated", ["add a note"], first, new))
        # 2. a change that does not start is refused; the old version keeps running
        routes = (self.work / "app/src/lemmata/hub/routes.py").read_text()
        self.push("app/src/lemmata/hub/routes.py", "def broken(:\n", "break the hub")
        self.assertEqual(self.run_update(), "failed")
        self.assertEqual((git(dep, "rev-parse", "HEAD"), len(self.restarts)), (new, 1))
        self.assertIn("SyntaxError", update.state(self.data)["detail"])
        # 3. a change that starts in the check but not for real is rolled back
        fixed = self.push("app/src/lemmata/hub/routes.py", routes, "fix the hub")
        self.assertEqual(self.run_update(healthy=False), "rolled_back")
        self.assertEqual(git(dep, "rev-parse", "HEAD"), new)
        self.assertEqual(len(self.restarts), 3)                          # restart, then restart again on the old version
        self.assertEqual(self.run_update(), "updated")                   # next pass tries again
        self.assertEqual(git(dep, "rev-parse", "HEAD"), fixed)
        log = (self.data.hub / "update.log").read_text()
        self.assertEqual([w for w in ("updated", "failed", "rolled_back") if w in log], ["updated", "failed", "rolled_back"])
        self.assertNotIn("SECRET", json.dumps(self.cfg.load()) + log)


if __name__ == "__main__":
    unittest.main()
