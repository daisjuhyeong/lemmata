"""S37 (ADR-013): survey papers. When a sentence changes, every other place that still says the old words.

Units: places of a .tex file (sentences, table rows, forest nodes, headings), the comparison of two versions (term, fact,
number and label changes), the model list against the paper. Engine: rule Y5, the baseline, marks, confirm, edits not yet
committed. Hub: a survey whose paper is an Overleaf project followed through Overleaf's Git, from the Git link Overleaf shows.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lemmata.engine import survey as S  # noqa: E402
from lemmata.engine.api import Engine  # noqa: E402

SEC = r"""\section{Online Deep Anomaly Detection Methodologies}
\label{sec:methodologies}
In this section, we split the stream into blocks. Each block is scored by the base model.
ARCUS~\cite{yoon2022arcus} is an error-based approach that adapts the model pool. We review 87 papers in total.
The anomaly threshold $\eta$ is fixed. See Table~\ref{tab:cmp} and Section~\ref{sec:old}. % a comment that says block
\begin{table}[t]
\caption{Summary of ODAD models}
\label{tab:cmp}
\begin{tabular}{lll}
\toprule
Model & Base Model & Concept Drift Detection \\
\midrule
ARCUS~\cite{yoon2022arcus} & Generative & Error-based \\
METER~\cite{zhu2024meter} & AE & Distribution-based \\
NEWM~\cite{new2025} & AE & Error-based \\
\bottomrule
\end{tabular}
\end{table}

\section{Old}\label{sec:old}
Our corpus has 87 papers drawn from four venues. A block is a contiguous run of points.
METER~\cite{zhu2024meter} is an error-based detector as well.
\begin{forest}
[ODAD [Generative [Error-based [ARCUS]] [Distribution-based [METER]]] [Approximative]]
\end{forest}
"""
MAIN = "\\documentclass{acmart}\n\\begin{document}\n\\begin{abstract}We survey online deep anomaly detection.\\end{abstract}\n\\input{sec}\n\\end{document}\n"
README = """# Awesome list

| Model | Paper Title | Venue | General Type | Base Model | Concept Drift Detection | Resources |
| :--- | :--- | :---: | :---: | :---: | :--- | :---: |
| **ARCUS** | Adaptive model pooling | KDD | ODAD | Generative | Error-based | [Paper](https://x.example) |
| **METER** | Dynamic concept adaptation | VLDB | ODAD | AE | Distribution-based | [Paper](#) |
| **OLDM** | An older model | ICDM | ODAD | AE | Error-based | [Paper](#) |
"""
DATASET = """# Datasets

| Dataset Name | Number of Instances | Description | Models |
|:---|:---|:---|:---|
| NAB | Varies | 58 files cut into blocks | ARCUS, METER |
| SWaT | 946,719 | Water treatment | METERR |
"""


def edit(text):
    return (text.replace("split the stream into blocks. Each block", "split the stream into subsequences. Each subsequence")
                .replace("is an error-based approach", "is a distribution-based approach")
                .replace("We review 87 papers", "We review 92 papers")
                .replace(r"\section{Old}\label{sec:old}", r"\section{Old}\label{sec:older}"))


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false"] + list(args),
                   cwd=str(cwd), check=True, capture_output=True)


def rows_of(changes):
    return [(r["status"], r["path"], r["line"], r["kind"]) for c in changes for r in c["rows"]]


class Places(unittest.TestCase):
    def test_kinds_and_floats(self):
        P = S.places_of("sec.tex", SEC)
        kinds = [p["kind"] for p in P]
        self.assertEqual(kinds.count("heading"), 2)
        self.assertEqual(kinds.count("row"), 4)            # header + three models
        self.assertEqual(kinds.count("node"), 7)
        rows = [p for p in P if p["kind"] == "row"]
        self.assertTrue(rows[0]["is_header"])
        self.assertEqual(rows[1]["cells"], ["ARCUS", "Generative", "Error-based"])
        self.assertEqual(rows[1]["cites"], ["yoon2022arcus"])
        self.assertEqual(rows[1]["float"], "Summary of ODAD models")
        leaf = next(p for p in P if p["kind"] == "node" and p["plain"].endswith("ARCUS"))
        self.assertEqual(leaf["plain"], "ODAD > Generative > Error-based > ARCUS")
        # a comment is not text; the table's [t] is not text either
        self.assertFalse(any("comment" in p["plain"] for p in P))
        self.assertFalse(any(p["plain"].startswith("[t]") for p in P))
        sent = next(p for p in P if p["plain"].startswith("ARCUS is"))
        self.assertEqual((sent["line"], sent["cites"]), (4, ["yoon2022arcus"]))
        self.assertEqual(rows[1]["line"], 13)                      # the row's own line, not the \midrule above it
        self.assertEqual(next(p for p in P if p["plain"].startswith("Our corpus"))["line"], 21)
        th = next(p for p in P if "threshold" in p["plain"])
        self.assertIn("$\\eta$", th["plain"])
        self.assertEqual(th["syms"], ["\\eta"])

    def test_sentences_keep_abbreviations(self):
        P = S.places_of("a.tex", "We follow Smith et al. in this. See Fig. 2 for e.g. the tree. A value of 3.5 is used.\n")
        self.assertEqual([p["plain"] for p in P], ["We follow Smith et al. in this.", "See Fig. 2 for e.g. the tree.", "A value of 3.5 is used."])

    def test_trim_and_spans(self):
        self.assertEqual(S.spans("ARCUS is an error-based approach.", "ARCUS is a distribution-based approach."), [("error-based", "distribution-based")])


class Compare(unittest.TestCase):
    def setUp(self):
        self.models = {"ARCUS": [], "METER": []}
        self.lp = [S.Place(path="README.md", line=5, end=5, kind="list", raw="| ARCUS | Generative | Error-based |", plain="ARCUS | Generative | Error-based",
                           cites=[], labels=[], refs=[], syms=[], model="ARCUS", n="arcus | generative | error-based")]
        self.ch = S.compare({"sec.tex": SEC}, {"sec.tex": edit(SEC)}, self.lp, list(self.models))

    def by_span(self, old):
        return next(c for c in self.ch if any(s["old"] == old for s in c["spans"]))

    def test_term_change_everywhere_in_the_paper(self):
        c = self.by_span("block")
        self.assertEqual(c["spans"][0]["mode"], "term")
        self.assertEqual([(r["status"], r["line"]) for r in c["rows"]], [("differs", 21)])
        self.assertNotIn("README.md", [r["path"] for r in c["rows"]])      # a term is the paper's own wording

    def test_fact_change_only_where_the_same_model_is(self):
        c = self.by_span("error-based")
        self.assertEqual(c["spans"][0]["mode"], "fact")
        got = {(r["path"], r["kind"]) for r in c["rows"]}
        self.assertEqual(got, {("sec.tex", "row"), ("sec.tex", "node"), ("README.md", "list")})
        # METER's own "error-based" sentence and NEWM's row are about other models: not listed
        self.assertFalse(any("METER" in r["quote"] or "NEWM" in r["quote"] for r in c["rows"]))
        self.assertTrue(all("about ARCUS" in r["why"] for r in c["rows"]))

    def test_number_before_the_same_word(self):
        c = self.by_span("87")
        self.assertEqual([(r["status"], r["line"], r["why"]) for r in c["rows"]], [("differs", 21, "Still says 87 papers")])

    def test_removed_label_still_referenced(self):
        c = next(c for c in self.ch if c["what"] == "label")
        self.assertEqual(c["old"], "\\label{sec:old}")
        self.assertEqual([(r["status"], r["line"]) for r in c["rows"]], [("differs", 5)])

    def test_moved_sentence_is_not_a_change(self):
        a = "First sentence here. Second sentence there.\n\n\\section{B}\nThird one.\n"
        b = "Second sentence there.\n\n\\section{B}\nThird one. First sentence here.\n"
        self.assertEqual(S.compare({"a.tex": a}, {"a.tex": b}), [])

    def test_no_change_no_rows(self):
        self.assertEqual(S.compare({"sec.tex": SEC}, {"sec.tex": SEC}), [])


class ListCheck(unittest.TestCase):
    def test_add_update_check(self):
        models, datasets, lp = S.read_list({"README.md": README, "Dataset.md": DATASET})
        self.assertEqual(sorted(models), ["ARCUS", "METER", "OLDM"])
        self.assertEqual(models["ARCUS"][0]["row"]["concept drift detection"], "Error-based")
        self.assertEqual(datasets[0]["models"], ["ARCUS", "METER"])
        head = S.places_of("sec.tex", edit(SEC).replace("ARCUS~\\cite{yoon2022arcus} & Generative & Error-based", "ARCUS~\\cite{yoon2022arcus} & Generative & Distribution-based"))
        rows, mentions = S.list_check(models, datasets, head)
        kinds = sorted((r["kind"], r["model"]) for r in rows)
        self.assertIn(("add", "NEWM"), kinds)
        self.assertIn(("not_in_paper", "OLDM"), kinds)
        self.assertIn(("update", "ARCUS"), kinds)
        self.assertIn(("dataset_model", "METERR"), kinds)
        up = next(r for r in rows if r["kind"] == "update")
        self.assertEqual((up["column"], up["list_value"], up["paper"]["value"]), ("Concept Drift Detection", "Error-based", "Distribution-based"))
        self.assertEqual(mentions["OLDM"], 0)


class EngineSurvey(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".lemmata").mkdir()
        (self.root / ".lemmata" / "project.json").write_text(json.dumps({"schema": "lemmata.project/1", "name": "survey", "repos": [
            {"id": "paper", "role": "paper", "path": "paper"}, {"id": "code", "role": "code", "path": "code"}]}))
        self.paper, self.code = self.root / "paper", self.root / "code"
        self.paper.mkdir()
        self.code.mkdir()
        git(self.code, "init", "-q")
        (self.code / "README.md").write_text(README)
        (self.code / "Dataset.md").write_text(DATASET)
        git(self.code, "add", "-A")
        git(self.code, "commit", "-qm", "list")
        git(self.paper, "init", "-q")
        (self.paper / "main.tex").write_text(MAIN)
        (self.paper / "sec.tex").write_text(SEC)
        git(self.paper, "add", "-A")
        git(self.paper, "commit", "-qm", "v1")

    def tearDown(self):
        self.tmp.cleanup()

    def test_rule_y5_and_a_code_repo_with_code(self):
        e = Engine(self.root)
        e.scan()
        st = e.study()
        self.assertEqual((st["kind"], st["rule"]), ("survey", "Y5"))
        self.assertIn("survey", [k["k"] for k in st["kinds"]])
        (self.code / "run.py").write_text("print(1)\n")
        e.scan()
        self.assertEqual(e.study()["kind"], "method")
        self.assertEqual(e.set_study("survey")["kind"], "survey")      # the researcher's choice wins
        self.assertEqual(e.study()["by"], "you")

    def test_versions_baseline_marks_confirm(self):
        e = Engine(self.root)
        e.scan()
        d = e.survey()
        self.assertEqual((d["state"], d["counts"]["changes"], d["newer"]), ("ok", 0, 0))      # the first look: nothing changed yet
        v1 = d["baseline"]["sha"]
        (self.paper / "sec.tex").write_text(edit(SEC))
        e.scan()
        d = e.survey()
        self.assertTrue(d["dirty"])                                   # a local folder: the working tree is the newest version
        self.assertEqual(d["counts"]["changes"], 5)      # four sentences and the removed \label
        git(self.paper, "commit", "-qam", "v2")
        e.scan()
        d = e.survey()
        self.assertEqual((d["dirty"], d["newer"], d["baseline"]["sha"]), (False, 1, v1))
        n = d["counts"]["differs"]
        self.assertGreaterEqual(n, 5)
        fact = next(c for c in d["changes"] if any(s["old"] == "error-based" for s in c["spans"]))
        lr = next(r for r in fact["rows"] if r["source"] == "list")
        self.assertEqual((lr["repo"], lr["path"]), ("code", "README.md"))
        pr = next(r for r in fact["rows"] if r["source"] == "paper")
        self.assertEqual(pr["repo"], "paper")
        d = e.survey_act("mark", row=lr["key"], state="leave")
        self.assertEqual((d["counts"]["left"], d["counts"]["differs"]), (1, n - 1))
        d = e.survey_act("mark", row=pr["key"], state="fixed")
        row = next(r for c in d["changes"] for r in c["rows"] if r["key"] == pr["key"])
        self.assertEqual(row["shown"], "still")                       # marked fixed, but it still says the old words
        d = e.survey_act("mark", row=pr["key"], state="open")
        self.assertEqual(next(r for c in d["changes"] for r in c["rows"] if r["key"] == pr["key"])["shown"], "differs")
        # list rows can be left as is too
        add = next(r for r in d["list"]["rows"] if r["kind"] == "add")
        d = e.survey_act("mark", row=add["key"], state="leave")
        self.assertEqual(next(r for r in d["list"]["rows"] if r["key"] == add["key"])["shown"], "left")
        # compare with another version, then confirm the newest
        d = e.survey_act("baseline", rev=d["head"]["sha"])
        self.assertEqual(d["counts"]["changes"], 0)
        d = e.survey_act("baseline", rev=v1[:8])
        self.assertEqual(d["counts"]["changes"], 5)
        d = e.survey_act("confirm")
        self.assertEqual((d["counts"]["changes"], d["newer"], len(d["confirmed"])), (0, 0, 1))
        self.assertEqual(d["confirmed"][0]["from"], v1)
        for bad in (("baseline", "nope"), ("baseline", "zzzz"), ("explode", None)):
            with self.assertRaises(Exception):
                e.survey_act(bad[0], rev=bad[1])
        with self.assertRaises(Exception):
            e.survey_act("mark", row="../x", state="fixed")
        with self.assertRaises(Exception):
            e.survey_act("mark", row="0123456789ab", state="maybe")

    def test_paper_in_a_subfolder_of_one_repository(self):
        # paper/ inside a repository that also holds other folders: versions and files come from the paper folder only
        top = self.root / "mono"
        (top / "tex").mkdir(parents=True)
        git(top, "init", "-q")
        (top / "tex" / "sec.tex").write_text(SEC)
        (top / "notes.md").write_text("x")
        git(top, "add", "-A")
        git(top, "commit", "-qm", "one")
        (top / "notes.md").write_text("y")
        git(top, "commit", "-qam", "notes only")
        (top / "tex" / "sec.tex").write_text(edit(SEC))
        git(top, "commit", "-qam", "two")
        src = S.Source(str(top / "tex"))
        vs = src.versions()
        self.assertEqual([v["subject"] for v in vs], ["two", "one"])
        self.assertEqual(sorted(src.tex_files(vs[1]["sha"])), ["sec.tex"])
        self.assertIn("subsequences", src.tex_files(None)["sec.tex"])
        self.assertNotIn("subsequences", src.tex_files(vs[1]["sha"])["sec.tex"])


class HubSurvey(unittest.TestCase):
    """The survey's paper followed through Overleaf's Git, created from the Git link Overleaf shows."""

    @classmethod
    def setUpClass(cls):
        import test_overleaf as TO
        cls.TO = TO

    def test_overleaf_survey_end_to_end(self):
        TO = self.TO

        class T(TO.Base):
            def runTest(inner):
                pass
        T.setUpClass()
        try:
            t = T()
            t.drop_all()
            t.hub.cfg.update(overleaf_enabled=False)
            # the owner switches Overleaf on from the website and saves the token there
            s, r = t.api("GET", "/api/hub/overleaf/enabled")
            self.assertEqual((s, r["enabled"]), (200, False))
            st = json.loads(t.raw("GET", "/api/hub/status", None, {"Authorization": "Bearer " + t.token})[1])
            self.assertIs(st["overleaf_enabled"], False)
            self.assertEqual(t.api("PUT", "/api/hub/overleaf/enabled", {"enabled": "yes"})[0], 400)
            s, r = t.api("PUT", "/api/hub/overleaf/enabled", {"enabled": True})
            self.assertEqual((s, r["enabled"]), (200, True))
            t.set_token()
            pid_ol = "6899e4f135e07e69b32f849b"
            t.ov.add_project(pid_ol, {"main.tex": MAIN, "sec.tex": SEC})
            p = t.new_project(paper_overleaf="https://git@git.overleaf.com/" + pid_ol)
            self.assertEqual(p["paper_source"], {"kind": "overleaf", "project_id": pid_ol})
            base = "/p/%s/api" % p["id"]
            s, r = t.api("POST", base + "/study", {"kind": "survey"})
            self.assertEqual((s, r["kind"]), (200, "survey"))
            s, d = t.api("GET", base + "/survey")
            self.assertEqual((s, d["state"], d["counts"]["changes"]), (200, "ok", 0))
            # a new version in Overleaf, then the hub's sync
            t.ov.commit(pid_ol, {"sec.tex": edit(SEC)}, "Update on Overleaf")
            s, r = t.api("POST", "/api/hub/projects/%s/sync" % p["id"])
            self.assertEqual((s, r["paper"]["changed"]), (200, True), r)
            s, d = t.api("GET", base + "/survey")
            self.assertEqual((d["newer"], d["counts"]["changes"]), (1, 5))
            self.assertEqual(d["head"]["subject"], "Update on Overleaf")
            self.assertGreaterEqual(d["counts"]["differs"], 4)
            self.assertNotIn(TO.TOKEN, json.dumps(d))
            key = d["changes"][0]["rows"][0]["key"]
            s, d = t.api("POST", base + "/survey", {"action": "mark", "row": key, "state": "leave"})
            self.assertEqual((s, d["counts"]["left"]), (200, 1))
            s, d = t.api("POST", base + "/survey", {"action": "confirm"})
            self.assertEqual((s, d["counts"]["changes"]), (200, 0))
            self.assertEqual(t.api("POST", base + "/survey", {"action": "mark", "row": "x", "state": "fixed"})[0], 400)
        finally:
            T.tearDownClass()


if __name__ == "__main__":
    unittest.main()
