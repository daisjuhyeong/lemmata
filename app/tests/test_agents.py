"""S30 tests: the paper agents for Claude Code (adapted from PaperOrchestra) and their installer.
Run: PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_agents*.py'"""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))

from lemmata import agents, cli, mcp  # noqa: E402

KIT = agents.ROOT / "paper"
NAMES = ["paper-figures", "paper-literature", "paper-outline", "paper-review", "paper-revise", "paper-sections"]


def front(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, "%s has no frontmatter" % path
    return dict(ln.split(": ", 1) for ln in m.group(1).splitlines()), m.group(2)


class AgentsTest(unittest.TestCase):
    def test_agent_files(self):
        files = sorted((KIT / "agents").glob("*.md"))
        self.assertEqual([p.stem for p in files], NAMES)
        tools = {t["name"] for t in mcp.TOOLS}
        for p in files:
            fm, body = front(p)
            self.assertEqual(fm["name"], p.stem)                                   # Claude Code names an agent by this field
            self.assertGreater(len(fm["description"]), 60)
            self.assertIn("mcp__lemmata__*", fm["tools"])
            self.assertNotIn("model", fm)                                          # the researcher's own model, on their own plan
            self.assertIn("PaperOrchestra (Google LLC, Apache-2.0)", " ".join(body.split()))         # every adapted file says where it comes from
            self.assertIn(".lemmata/writing/", body)                               # every stage leaves a record
            for called in re.findall(r"`([a-z_]+)`", body):                        # a Lemmata tool an agent is told to call must exist
                if called in ("add_feedback", "propose_baselines", "key_numbers", "baselines", "hypotheses", "claims", "experiments", "setup", "study", "notation", "findings"):
                    self.assertIn(called, tools, "%s names a tool Lemmata does not have: %s" % (p.name, called))
        # only the agents that must run something get a shell; the reviewer cannot edit the paper
        self.assertNotIn("Bash", front(KIT / "agents" / "paper-outline.md")[0]["tools"])
        self.assertNotIn("Edit", front(KIT / "agents" / "paper-review.md")[0]["tools"])
        self.assertNotIn("WebSearch", front(KIT / "agents" / "paper-sections.md")[0]["tools"])

    def test_what_was_changed_holds(self):
        body = {p.stem: front(p)[1] for p in (KIT / "agents").glob("*.md")}
        body = {k: " ".join(v.split()) for k, v in body.items()}
        allb = "\n".join(body.values()).lower()
        self.assertNotIn("never explicitly state a limitation", allb)              # the original's instruction is gone
        self.assertNotIn("90%", allb)                                              # so is the citation quota
        self.assertIn("never delete or weaken a stated limitation", body["paper-revise"].lower())
        self.assertIn("the reviewer's score does not decide", body["paper-revise"].lower())
        self.assertIn("needs_experiment", body["paper-revise"])
        self.assertIn("if `approved` is null, stop", body["paper-literature"].lower())
        self.assertIn("never type a result into a script by hand", body["paper-figures"].lower())
        fm, skill = front(KIT / "skills" / "lemmata-paper" / "SKILL.md")
        self.assertEqual(fm["name"], "lemmata-paper")
        for n in NAMES:
            self.assertIn("`%s`" % n, skill)
        self.assertIn("Do not commit, push, merge or submit anything unless the researcher asks", skill)
        notice = (KIT / "NOTICE.md").read_text(encoding="utf-8")
        self.assertIn("Apache License", notice)
        self.assertIn("github.com/google-research/paper-orchestra", notice)
        self.assertIn("What was changed", notice)
        self.assertIn("Apache License", (KIT / "LICENSE-APACHE-2.0").read_text(encoding="utf-8")[:200])

    def test_install(self):
        tmp = tempfile.mkdtemp()
        try:
            written, kept = agents.install("paper", tmp)
            self.assertEqual((len(written), kept), (10, []))
            self.assertTrue(Path(tmp, ".claude/agents/paper-outline.md").is_file())
            self.assertTrue(Path(tmp, ".claude/skills/lemmata-paper/SKILL.md").is_file())
            self.assertTrue(Path(tmp, ".claude/lemmata-paper-agents/LICENSE-APACHE-2.0").is_file())   # the licence travels with the files
            mine = Path(tmp, ".claude/agents/paper-outline.md")
            mine.write_text("my own version\n", encoding="utf-8")
            written, kept = agents.install("paper", tmp)                           # a file the researcher changed is left alone
            self.assertEqual((len(written), kept), (9, [mine]))
            self.assertEqual(mine.read_text(encoding="utf-8"), "my own version\n")
            written, kept = agents.install("paper", tmp, force=True)
            self.assertEqual((len(written), kept), (10, []))
            with self.assertRaises(ValueError):
                agents.install("nope", tmp)
            with self.assertRaises(ValueError):
                agents.install("paper", tmp + "/missing")
            self.assertEqual(cli.main(["agents", "install", tmp]), 0)
            self.assertEqual(cli.main(["agents", "list"]), 0)
            self.assertEqual(cli.main(["agents", "install", tmp + "/missing"]), 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
