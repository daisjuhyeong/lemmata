"""S29 tests: the kind of study (method paper or benchmark study) and the key numbers.
Run: PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_study*.py'

A small benchmark repo: a frozen protocol with two hypotheses, a test table, a long table of runs (three detectors on
two datasets with two seeds), a table of synthetic cases and a findings report that quotes numbers. Nothing here calls
a model; the map, the hypotheses and the numbers are proposed the way the researcher's own agent would propose them."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))

from lemmata.engine import numbers as nm  # noqa: E402
from lemmata.engine import study as st  # noqa: E402
from lemmata.engine.api import Engine  # noqa: E402
from lemmata.engine.errors import BadRequest, NotFound  # noqa: E402
from lemmata import mcp  # noqa: E402

PROTOCOL = """# Benchmark protocol

- **Frozen before any detector is run.**

| | Hypothesis |
|---|---|
| H1 | Time-series benchmarks carry more temporal dependence than streaming benchmarks. |
| H2 | The detector gap grows with temporal dependence. |
"""
FINDINGS = """# Findings

Nobody measured the temporal characteristics the gap is attributed to.

- H1 is confirmed: Cliff's delta 0.58 (95 % CI 0.24 to 0.87), Holm p 0.0002.
- H2 is not supported: rho 0.19, Holm p 0.24.
- Step C: 1,010 of 1,012 seed-cells ok. The robustness delta is 0.66.
- The clipped model reaches 0.887.
"""
TESTS = "test,estimate,ci_lo,ci_hi,p_holm\nH1 (D1),0.5841,0.2439,0.8718,0.00024\nH2 (D1 vs Delta),0.194,-0.12,0.45,0.2426\n"
GATES = "case,rate,gate_ok\niid,0.0,True\nar1_0.5,0.4,True\nrandom_walk,0.9,True\n"
SUMMARY = {"gates": {"G1": True, "G2": True}, "qualify": {"sieve": False, "blocks": False}, "level": 0.05}


def cells():
    """A long table: one row per (model, dataset, variant, seed), as a benchmark writes it. 1,012 rows, 2 failed."""
    rows = ["model,group,dataset,variant,seed,status,auc_pr"]
    score = {"LSTM": 0.60, "USAD": 0.50, "MemStream": 0.40}
    n = 0
    for model, base in score.items():
        for ds, shift in (("NAB", 0.10), ("KDD", -0.05)):
            for seed in (0, 1):
                rows.append("%s,%s,%s,original,%d,ok,%.3f" % (model, "TSB" if ds == "NAB" else "G3", ds, seed, base + shift + 0.01 * seed))
                rows.append("%s,%s,%s,global,%d,ok,%.3f" % (model, "TSB" if ds == "NAB" else "G3", ds, seed, base + shift - 0.08))
                n += 2
    rows.append("MemStream,G3,Pima,original,0,error,")
    rows.append("USAD,G3,Pima,original,0,error,")
    for i in range(1012 - n - 2):      # filler runs of one more detector, so the count the report quotes is real
        rows.append("GRU,TSB,NAB,original,%d,ok,0.55" % (i + 10))
    return "\n".join(rows) + "\n"


def git(cwd, *args, date=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    subprocess.run(["git", "-c", "commit.gpgsign=false"] + list(args), cwd=cwd, env=env, check=True, capture_output=True)


def rule(sel):
    return {"file": "results/tests.csv", "select": {"test": sel}, "conditions": [{"column": "p_holm", "op": "<", "value": 0.05}, {"column": "estimate", "op": ">", "value": 0}],
            "report": ["estimate", "p_holm"]}


def draft():
    fz = {"file": "protocol/short.md"}
    return {"hypotheses": [
        {"id": "H1", "statement": "Time-series benchmarks carry more temporal dependence than streaming benchmarks.", "tier": "confirmatory",
         "criterion": {"text": "Cliff's delta, Holm", "frozen": fz, "rule": rule("H1 (D1)")}, "tested_by": ["stepA"],
         "evidence": [{"path": "protocol/short.md", "quote": "carry more temporal dependence"}]},
        {"id": "H2", "statement": "The detector gap grows with temporal dependence.", "tier": "confirmatory",
         "criterion": {"text": "Spearman, Holm", "frozen": fz, "rule": rule("H2 (D1 vs Delta)")}, "tested_by": ["stepC"],
         "evidence": [{"path": "protocol/short.md", "quote": "The detector gap grows"}]}],
        "experiments": [{"id": "stepA", "title": "Dependence", "deliverables": ["results/tests.csv"], "tests_claims": ["H1"]},
                        {"id": "stepC", "title": "Detectors", "deliverables": ["results/cells.csv"], "tests_claims": ["H2"]}]}


def bench_map():
    ev = lambda q: [{"path": "protocol/short.md", "quote": q}]
    return {"study": "benchmark", "method": {"name": "LSTM"}, "goal": "x",
            "roles": {"method": ["model"], "dataset": ["dataset"], "condition": ["variant", "case"], "seed": ["seed"], "group": ["nope"], "what": ["x"]},
            "questions": [{"id": "h1", "kind": "hypothesis", "label": "H1", "claim": "H1", "text": "Time-series benchmarks carry more temporal dependence.", "evidence": ev("carry more temporal dependence")},
                          {"id": "h2", "kind": "hypothesis", "label": "H2", "claim": "h2", "text": "The detector gap grows with temporal dependence.", "evidence": ev("The detector gap grows")},
                          {"id": "q3", "kind": "question", "label": "RQ3", "text": "Do the gates hold?", "evidence": ev("Frozen before any detector is run")}],
            "experiments": [
                {"id": "tests", "name": "Confirmatory tests", "type": "analysis", "tests": ["h1", "h2"], "files": ["results/tests.csv"], "metric": "estimate", "row_column": "test"},
                {"id": "stepC", "name": "Detectors, original order", "type": "main", "tests": ["h2"], "files": ["results/cells.csv"], "metric": "auc_pr", "method_column": "model",
                 "dataset_column": "dataset", "where": {"variant": "original", "status": "ok"}, "criteria": {"h2": {"compare": "best_other"}}},
                {"id": "gates", "name": "Gates on synthetic cases", "type": "other", "tests": ["q3"], "files": ["results/gates.csv"], "metric": "rate"},
                {"id": "stepE", "name": "Not run yet", "type": "analysis", "tests": ["h1"], "files": ["results/stepE_*.csv"], "metric": "x", "planned": True},
                {"id": "ghost", "name": "Invented", "type": "other", "tests": [], "files": ["results/nothing.csv"]}]}


def eq(c, v):
    return {"column": c, "op": "==", "value": v}


def numbers():
    t = lambda name: [eq("test", name)]
    return {"numbers": [
        {"id": "h1-delta", "claim": "H1", "label": "Cliff's delta", "file": "results/tests.csv", "read": {"agg": "value", "column": "estimate", "where": t("H1 (D1)")},
         "quoted": {"text": "0.58", "path": "FINDINGS.md", "quote": "Cliff's delta 0.58"}},
        {"id": "h1-p", "claim": "h1", "label": "Holm p", "file": "results/tests.csv", "read": {"agg": "value", "column": "p_holm", "where": t("H1 (D1)")}, "quoted": "0.0002"},
        {"id": "h2-lo", "claim": "H2", "label": "CI low", "file": "results/tests.csv", "read": {"agg": "value", "column": "ci_lo", "where": t("H2 (D1 vs Delta)")}, "quoted": "−0.12"},
        {"id": "c-ok", "claim": "H2", "label": "Step C: cells ok", "file": "results/cells.csv", "read": {"agg": "count_of", "where": [eq("status", "ok")]},
         "quoted": {"text": "1,010 of 1,012", "path": "FINDINGS.md", "quote": "1,010 of 1,012 seed-cells ok"}},
        {"id": "c-best", "claim": "H2", "label": "best original score", "file": "results/cells.csv", "read": {"agg": "max", "column": "auc_pr", "where": [eq("variant", "original"), {"column": "model", "op": "in", "value": ["LSTM", "USAD"]}]}, "quoted": "0.71"},
        {"id": "c-models", "claim": None, "label": "detectors", "file": "results/cells.csv", "read": {"agg": "distinct", "column": "model", "where": [{"or": [eq("group", "TSB"), {"column": "dataset", "op": "contains", "value": "KD"}]}]}, "quoted": "4"},
        {"id": "g-all", "claim": None, "label": "gates pass", "file": "results/summary.json", "read": {"agg": "all", "keys": ["gates.G1", "gates.G2"]}, "quoted": "True"},
        {"id": "g-any", "claim": None, "label": "a null qualifies", "file": "results/summary.json", "read": {"agg": "any", "keys": ["qualify.sieve", "qualify.blocks"]}, "quoted": "False"},
        {"id": "g-level", "claim": None, "label": "level", "file": "results/summary.json", "read": {"agg": "value", "key": "level"}, "quoted": "5%"},
        {"id": "rob", "claim": "H1", "label": "robustness delta", "read": None, "quoted": {"text": "0.66", "path": "FINDINGS.md", "quote": "robustness delta is 0.66"},
         "gap": "No file stores it; it is recomputed in a notebook."},
        {"id": "clip", "claim": None, "label": "clipped model", "file": "results/clip.csv", "read": {"agg": "value", "column": "auc", "where": [eq("clip", "5")]}, "quoted": "0.887",
         "gap": "The script that made it is not committed."},
        {"id": "later", "claim": "H2", "label": "a file that is not there yet", "file": "results/later.csv", "read": {"agg": "count", "where": []}, "quoted": "3"},
        {"id": "wrong", "claim": "H2", "label": "rho", "file": "results/tests.csv", "read": {"agg": "value", "column": "estimate", "where": t("H2 (D1 vs Delta)")}, "quoted": "0.91"},
        {"id": "bad-col", "claim": "H1", "label": "x", "file": "results/tests.csv", "read": {"agg": "value", "column": "nope", "where": t("H1 (D1)")}, "quoted": "1"},
        {"id": "bad-row", "claim": "H1", "label": "x", "file": "results/tests.csv", "read": {"agg": "value", "column": "estimate", "where": t("H9")}, "quoted": "1"},
        {"id": "bad agg", "label": "x", "file": "results/tests.csv", "read": {"agg": "value", "column": "estimate"}},
    ]}


class StudyBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lemmata-study-")
        root = Path(self.tmp)
        code = root / "code"
        (code / "protocol").mkdir(parents=True)
        (code / "results").mkdir()
        git(code, "init", "-q", "-b", "main")
        (code / "protocol" / "short.md").write_text(PROTOCOL)
        (code / "FINDINGS.md").write_text(FINDINGS)
        git(code, "add", "-A")
        git(code, "commit", "-q", "-m", "protocol", date="2026-11-12T10:00:00+0900")
        (code / "results" / "tests.csv").write_text(TESTS)
        (code / "results" / "cells.csv").write_text(cells())
        (code / "results" / "gates.csv").write_text(GATES)
        (code / "results" / "summary.json").write_text(json.dumps(SUMMARY))
        git(code, "add", "-A")
        git(code, "commit", "-q", "-m", "results", date="2026-11-16T10:00:00+0900")
        (root / ".lemmata").mkdir()
        (root / ".lemmata" / "project.json").write_text(json.dumps({"schema": "lemmata.project/1", "name": "bench", "repos": [{"id": "code", "role": "code", "path": "code"}]}))
        self.root, self.code = root, code
        self.e = Engine(root)
        self.e.scan()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def hypotheses(self):
        e = self.e
        j = e.hypothesis()["jobs"][0]
        e.submit_hypothesis_job(j["id"], {"problem": {"gap": {"text": "Nobody measured it.", "evidence": [{"path": "FINDINGS.md", "quote": "Nobody measured the temporal characteristics"}]}}})
        d = e.hypothesis_act("confirm", "problem")
        j = next(j for j in d["jobs"] if j["type"] == "draft_hypotheses")
        e.submit_hypothesis_job(j["id"], draft())
        for h in ("H1", "H2"):
            e.hypothesis_act("confirm", h)

    def mapped(self):
        self.hypotheses()
        self.e.propose_map(bench_map(), "agent")
        return self.e.confirm_map()


class StudyKindTest(StudyBase):
    def test_kind_by_rule_by_you_and_back(self):
        s = self.e.study()
        self.assertEqual((s["kind"], s["by"], s["rule"]), ("benchmark", "rule", "Y3"), "no paper, a protocol and a report: read as a benchmark study")
        self.assertEqual(self.e.project()["study"], {"kind": "benchmark", "by": "rule", "word": "Benchmark study"})
        s = self.e.set_study("method")
        self.assertEqual((s["kind"], s["by"], s["chosen"]), ("method", "you", "method"))
        self.assertEqual(self.e.experiments()["study"], "method")
        s = self.e.set_study("auto")
        self.assertEqual((s["kind"], s["by"], s["chosen"]), ("benchmark", "rule", None))
        with self.assertRaises(BadRequest):
            self.e.set_study("survey")

    def test_no_ours_without_a_map(self):
        """The case that started this: with no map, every label column was a list of methods and one of them was "ours"."""
        S = self.e.setup()
        ms = {i["name"]: i for i in S["items"] if i["kind"] == "method"}
        self.assertEqual(sorted(ms), ["GRU", "LSTM", "MemStream", "USAD"], "tests and synthetic cases are rows, not methods")
        self.assertEqual({m["role"] for m in ms.values()}, {"compared"})
        self.assertEqual((S["study"], S["method"], S["counts"]["compared"], S["counts"]["baselines"]), ("benchmark", None, 4, 0))
        for x in self.e.experiments()["unassigned"]:
            sm = x.get("summary") or {}
            self.assertIsNone(sm.get("ours_label"), x["name"])
            self.assertNotIn("guess", [c["k"] for c in x["caveats"]], x["name"])
        kinds = {x["name"]: (x["summary"]["row_kind"], x["summary"]["row_column"]) for x in self.e.experiments()["unassigned"] if x.get("summary")}
        self.assertEqual(kinds["cells.csv"], ("method", "model"))
        self.assertEqual(kinds["gates.csv"], ("condition", "case"))
        self.assertEqual(kinds["tests.csv"], ("row", "test"))
        # the same files read as a method paper: the old guess is back, and marked as a guess
        self.e.set_study("method")
        roles = {i["role"] for i in self.e.setup()["items"] if i["kind"] == "method"}
        self.assertIn("ours", roles)

    def test_roles(self):
        r = st.roles_of({"roles": {"dataset": ["series"], "condition": ["model"]}})
        self.assertEqual(st.role_of("Series", r), "dataset")
        self.assertEqual(st.role_of("model", r), "condition", "a column the map gives a role loses its default one")
        self.assertEqual(st.role_of("detector", r), "method")
        self.assertEqual(st.role_of("test", r), "row")
        self.assertEqual(st.first(["seed", "Detector", "model"], st.roles_of(None), "method"), "model", "the role's own order of preference")

    def test_map_of_a_benchmark_study(self):
        self.hypotheses()
        d = self.e.propose_map(bench_map(), "agent")
        m = d["proposed"]
        why = {(r["level"], r["where"]): r["why"] for r in d["report"]}
        self.assertEqual((m["study"], m["method"], m["base"], m["goal"]), ("benchmark", None, None, None))
        self.assertIn("a benchmark study has no method of its own", why[("dropped", "method")])
        self.assertEqual(m["roles"], {"method": ["model"], "condition": ["variant", "case"], "dataset": ["dataset"], "seed": ["seed"]})
        self.assertIn(("dropped", "roles"), why)
        hy = {c["hypothesis"]: c["id"] for c in self.e.claims()["claims"] if c.get("hypothesis")}
        self.assertEqual([(q["label"], q["claim"]) for q in m["questions"]], [("H1", hy["H1"]), ("H2", hy["H2"]), ("RQ3", None)], "a question names a hypothesis by its label")
        X = {x["id"]: x for x in m["experiments"]}
        self.assertEqual(sorted(X), ["gates", "stepC", "stepE", "tests"], "ghost matches nothing and is not planned: dropped")
        self.assertTrue(X["stepE"]["waiting"] and X["stepE"]["matched"] == 0)
        self.assertIn(("waiting", "experiment stepE"), why)
        self.assertEqual(X["stepC"]["where"], {"variant": ["original"], "status": ["ok"]})
        self.assertEqual(X["stepC"]["criteria"], {}, "a benchmark study has no ours to compare")
        self.assertEqual(X["tests"]["row_column"], "test")
        m = self.e.confirm_map()
        s = self.e.study()
        self.assertEqual((s["kind"], s["by"], s["roles"]["method"]), ("benchmark", "map", ["model"]))
        # the map can be turned into a method paper's and back while it is reviewed
        d = self.e.edit_map({"study": "method"})
        self.assertEqual(d["proposed"]["study"], "method")
        self.assertIn(("warning", "method"), {(r["level"], r["where"]) for r in d["report"]})
        self.e.discard_map()

    def test_experiments_links_setup_and_review(self):
        self.mapped()
        E = self.e.experiments()
        self.assertEqual((E["study"], E["map"]["waiting"]), ("benchmark", 1))
        S = {s["label"]: s for s in E["sections"]}
        X = {x["id"]: x for s in E["sections"] for x in s["experiments"]}
        c = X["map:stepC"]
        self.assertEqual((c["summary"]["ours_label"], c["summary"]["gap"], c["summary"]["row_kind"], c["summary"]["of"]), (None, None, "method", 4))
        self.assertEqual(c["summary"]["best"]["label"], "LSTM")
        self.assertAlmostEqual(c["grid"]["rows"][0]["values"]["NAB"], 0.705, msg="only the rows of its filter: original order, two seeds averaged")
        self.assertEqual(c["grid"]["rows"][0]["n"]["NAB"], 2)
        self.assertEqual(c["caveats"], [])
        self.assertEqual((X["map:tests"]["summary"]["row_kind"], X["map:gates"]["summary"]["row_kind"]), ("row", "condition"))
        self.assertEqual([cv["t"] for cv in X["map:stepE"]["caveats"]], ["Waiting for its result files"])
        # links: the claim's own test decides, and every experiment that feeds it carries that verdict (rule L5)
        self.assertEqual({k: (v["status"], v["rule"]) for k, v in S["H1"]["links"].items()}, {"map:tests": ("supports", "L5"), "map:stepE": ("not_run", "L1")})
        self.assertEqual({k: (v["status"], v["rule"]) for k, v in S["H2"]["links"].items()}, {"map:tests": ("contradicts", "L5"), "map:stepC": ("contradicts", "L5")})
        self.assertEqual({k: (v["status"], v["rule"]) for k, v in S["RQ3"]["links"].items()}, {"map:gates": ("inconclusive", "L5")})
        self.assertIn("no method of its own to rank", S["RQ3"]["links"]["map:gates"]["why"])
        cl = {c.get("hypothesis") or c["ref"]: c for c in self.e.claims()["claims"]}
        self.assertEqual((cl["H1"]["stage"], cl["H2"]["stage"]), ("finding", "refuted"))
        self.assertEqual((cl["RQ3"]["stage"], cl["RQ3"]["stage_rule"]), ("testing", "C10"))
        self.assertIn("decided by its own test", cl["RQ3"]["stage_why"])
        # Setup
        D = self.e.setup()
        ms = {i["name"]: i for i in D["items"] if i["kind"] == "method"}
        self.assertEqual(sorted(ms), ["GRU", "LSTM", "MemStream", "USAD"])
        self.assertEqual((ms["LSTM"]["role"], ms["LSTM"]["best_in"], ms["LSTM"]["ranked"], ms["LSTM"]["wins"]), ("compared", 2, 2, 0))
        sheets = {x["id"]: x for x in D["experiments"]}
        p = sheets["map:stepC"]["protocol"]
        self.assertEqual((p["ours"], p["study"], [m["role"] for m in p["methods"]], p["rows"]), (None, "benchmark", ["compared"] * 4, None))
        self.assertEqual((sheets["map:tests"]["protocol"]["methods"], sheets["map:tests"]["protocol"]["rows"]["kind"], sheets["map:tests"]["protocol"]["rows"]["n"]), ([], "row", 2))
        self.assertEqual({r["role"] for r in sheets["map:gates"]["grid"]["rows"]}, {"row"})
        # Review: not "are we ahead of the baselines" but "have the tests spoken"
        R = self.e.review()
        self.assertEqual([c["k"] for c in R["checks"]], ["moving", "decided", "paper"])
        self.assertEqual((R["checks"][1]["verdict"], R["checks"][1]["line"]), ("partly", "2 of 3 claims decided: 1 finding, 1 not supported"))
        self.assertEqual((R["baselines"], R["ours"], R["study"]), ([], None, "benchmark"))
        Q = {q["ref"]: {c["k"]: c["state"] for c in q["checklist"]} for q in R["questions"]}
        self.assertEqual(Q["H2"], {"seeds": "done", "coverage": "todo", "test": "done", "numbers": "todo", "confounds": "todo"})
        self.assertEqual((Q["H1"]["seeds"], Q["H1"]["coverage"], Q["H1"]["test"]), ("na", "na", "done"))
        self.assertEqual(Q["RQ3"]["test"], "todo")
        # To-do: a claim its test does not support is a result, not a task
        kinds = [i["kind"] for i in self.e.todo()["items"]]
        self.assertNotIn("contradicts", kinds)
        self.assertIn("not_run", kinds)
        self.e.trail()

    def test_a_method_paper_can_be_read_as_a_benchmark(self):
        """Switching the kind on a project that has a paper and an "ours" must not break any page."""
        from lemmata.samples.make_sample import build
        d = Path(self.tmp) / "sample"
        build(d)
        e = Engine(d)
        e.scan()
        self.assertEqual((e.study()["kind"], e.study()["rule"]), ("method", "Y4"))
        before = e.setup()["counts"]
        e.set_study("benchmark")
        S = e.setup()
        self.assertEqual((S["study"], S["counts"]["baselines"]), ("benchmark", 0))
        self.assertNotIn("ours", {i.get("role") for i in S["items"]})
        for fn in (e.experiments, e.review, e.todo, e.claims, e.numbers, e.trail):
            fn()
        e.set_study("auto")
        self.assertEqual(e.setup()["counts"], before)


class NumbersTest(StudyBase):
    def test_agrees_with_the_rounding_of_the_text(self):
        for q, v, want in (("0.58", 0.5841, True), ("0.58", 0.5751, True), ("0.58", 0.5749, False), ("0.0002", 0.00024, True), ("0.0002", 0.00026, False), ("−0.12", -0.1212, True),
                           ("2.4e-4", 0.00024127, True), ("115.5", 115.5, True), ("12%", 0.1204, True), ("12%", 12.04, True), ("12%", 0.13, False),
                           ("1,010 of 1,012", "1010 of 1012", True), ("3,294", 3294, True), ("True", True, True), ("true", "True", True), ("True", False, False),
                           ("17/4/2/0", "17/4/2/0", True), ("0.9", "n/a", False), ("about 115", 115, False)):
            self.assertIs(nm.agrees(q, v), want, (q, v))
        self.assertIsNone(nm.agrees(None, 1.0))

    def test_propose_check_confirm(self):
        self.hypotheses()
        N = self.e.numbers()
        self.assertEqual((N["state"], N["counts"]["from_tests"], N["counts"]["unquoted"]), ("tests", 4, 4), "a hypothesis's test already names its numbers")
        self.assertEqual([n["found"] for n in N["groups"][0]["numbers"]], ["0.5841", "0.00024"])
        N = self.e.propose_numbers(numbers(), "agent")
        rep = {r["where"]: (r["level"], r["why"]) for r in N["report"]}
        for bad in ("number bad-col", "number bad-row", "number bad agg"):
            self.assertEqual(rep[bad][0], "dropped", bad)
        self.assertEqual((rep["number clip"][0], rep["number later"][0], rep["number wrong"][0]), ("gap", "waiting", "warning"))
        self.assertEqual((N["state"], N["counts"]["proposed"], N["counts"]["confirmed"]), ("proposed", 13, 0))
        self.assertIn("numbers", [i["kind"] for i in self.e.todo()["items"]], "a proposal waits for the researcher")
        with self.assertRaises(NotFound):
            self.e.decide_numbers("remove", "nope")
        N = self.e.decide_numbers("confirm")
        self.assertEqual((N["state"], N["counts"]["proposed"], N["counts"]["confirmed"]), ("confirmed", 0, 13))
        ns = {n["id"]: n for g in N["groups"] for n in g["numbers"]}
        self.assertEqual({k: v["status"] for k, v in ns.items() if not k.startswith("test:")},
                         {"h1-delta": "ok", "h1-p": "ok", "h2-lo": "ok", "c-ok": "ok", "c-best": "ok", "c-models": "ok", "g-all": "ok", "g-any": "ok", "g-level": "ok",
                          "rob": "gap", "clip": "gap", "later": "missing", "wrong": "mismatch"})
        self.assertEqual((ns["c-ok"]["found"], ns["c-best"]["found"], ns["c-models"]["found"], ns["g-all"]["found"], ns["g-any"]["found"]), ("1010 of 1012", "0.71", "4", "True", "False"))
        self.assertEqual((ns["h1-delta"]["quoted"]["path"], ns["h1-delta"]["quoted"]["line"]), ("FINDINGS.md", 5), "the quote is found and its line kept")
        self.assertEqual((ns["h1-delta"]["commit"]["subject"], ns["rob"]["found"], ns["rob"]["read"]), ("results", None, None))
        self.assertEqual(ns["wrong"]["why"], "The report says 0.91; the file holds 0.194.")
        self.assertEqual([g["label"] for g in N["groups"]], ["H1", "H2", "No claim"])
        self.assertEqual(N["groups"][0]["counts"], {"ok": 2, "mismatch": 0, "missing": 0, "gap": 1, "unquoted": 0})
        self.assertNotIn("test:H1:estimate", ns, "the test's own number is not listed twice once it is confirmed with its quote")
        gaps = {(g["k"], g.get("number")) for g in N["gaps"]}
        self.assertTrue({("gap", "rob"), ("gap", "clip"), ("missing", "later"), ("mismatch", "wrong")} <= gaps)
        self.assertIn("no_run", {g["k"] for g in N["gaps"]}, "no logged run wrote these files: the commit is the only record")
        todo = {i["kind"] for i in self.e.todo()["items"]}
        self.assertTrue({"number", "number_missing", "number_gap"} <= todo)
        # the file changes: the number is read again, with no model
        (self.code / "results" / "tests.csv").write_text(TESTS.replace("0.5841", "0.61"))
        ns = {n["id"]: n for g in self.e.numbers()["groups"] for n in g["numbers"]}
        self.assertEqual((ns["h1-delta"]["status"], ns["h1-delta"]["found"]), ("mismatch", "0.61"))
        # a later proposal adds to the list; the same id is replaced
        N = self.e.propose_numbers({"numbers": [dict(numbers()["numbers"][12], quoted="0.19")]}, "agent")
        self.assertEqual((N["counts"]["proposed"], N["replaces"]), (1, ["wrong"]))
        N = self.e.decide_numbers("confirm")
        self.assertEqual({n["id"]: n["status"] for g in N["groups"] for n in g["numbers"]}["wrong"], "ok")
        N = self.e.decide_numbers("remove", "later")
        self.assertEqual(N["counts"]["confirmed"], 12)
        with self.assertRaises(BadRequest):
            self.e.propose_numbers({"numbers": [{"id": "x", "file": "results/tests.csv", "read": {"agg": "sum"}}]})

    def test_runs_behind_a_number_and_what_is_not_an_experiment(self):
        self.hypotheses()
        self.e.propose_numbers(numbers(), "agent")
        self.e.decide_numbers("confirm")
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.code, capture_output=True, text=True).stdout.strip()
        run = lambda rid, cmd, arts, **kw: dict({"run_id": rid, "source": "agent", "command": cmd, "git_sha": sha, "dirty": False, "exit_code": 0, "artifacts": [{"path": a} for a in arts],
                                                 "started": "2026-11-16T09:00:00+09:00", "ended": "2026-11-16T09:30:00+09:00"}, **kw)
        self.e.add_runs([run("stepC-20261116-0900", "python src/run_cells.py", ["results/cells.csv"], sha_basis="results_commit", backfilled=True),
                         run("check-20261116-1000", "python src/check.py --ref HEAD", []),
                         run("crash-20261116-1100", "python src/run_cells.py --seed 9", [], exit_code=1),
                         run("other-20261116-1200", "python src/x.py", ["results/x.csv"], git_sha="0123456789abcdef0123", sha_basis="bogus")])
        R = self.e.runs()
        by = {r["run_id"]: r for r in R["runs"]}
        self.assertEqual({k: v["kind"] for k, v in by.items()}, {"stepC-20261116-0900": "experiment", "check-20261116-1000": "command", "crash-20261116-1100": "experiment", "other-20261116-1200": "experiment"})
        self.assertEqual((R["counts"]["experiments"], R["counts"]["commands"], R["counts"]["unsure"], R["behind"]), (3, 1, 0, None))
        self.assertEqual((by["stepC-20261116-0900"]["sha_basis"], by["stepC-20261116-0900"]["backfilled"], by["other-20261116-1200"].get("sha_basis")), ("results_commit", True, None))
        N = self.e.numbers()
        ns = {n["id"]: n for g in N["groups"] for n in g["numbers"]}
        self.assertEqual([r["run_id"] for r in ns["c-ok"]["runs"]], ["stepC-20261116-0900"])
        h2 = next(g for g in N["groups"] if g["label"] == "H2")
        self.assertEqual([r["run_id"] for r in h2["runs"]], ["stepC-20261116-0900"])
        self.assertIn(("start_commit", "h:H2"), {(g["k"], g["claim"]) for g in N["gaps"]})
        self.assertNotIn("results/cells.csv", [f for g in N["gaps"] if g["k"] == "no_run" for f in g["files"]])
        # while the hub cannot sync, a commit Lemmata has not seen is not known to be missing from GitHub
        self.assertEqual(by["other-20261116-1200"]["state"], "not in github")
        (self.root / ".lemmata" / "sync.json").write_text(json.dumps({"failing": True, "since": "2026-11-18T18:41:00+09:00", "message": "GitHub no longer accepts the saved sign-in.", "head": sha}))
        R = self.e.runs()
        self.assertTrue(R["behind"] and {r["run_id"]: r["unsure"] for r in R["runs"]}["other-20261116-1200"])
        N = self.e.numbers()
        later = next(n for g in N["groups"] for n in g["numbers"] if n["id"] == "later")
        self.assertIn("may only be missing here", later["why"])
        self.assertTrue(N["behind"])
        self.assertIn("sync", [i["kind"] for i in self.e.todo()["items"]])
        self.assertTrue(self.e.project()["sync"]["failing"])

    def test_mcp_tools(self):
        self.hypotheses()
        ctx = mcp.LocalCtx(self.root)
        ctx.engine = self.e
        pid = ctx.list_projects()[0]["id"]

        def call(name, **args):
            _, out = mcp.handle(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": dict(args, project=pid)}}), ctx)
            return json.loads(out)["result"]

        t = call("study")["content"][0]["text"]
        self.assertIn("Benchmark study", t)
        self.assertIn("Nothing is called 'ours'", t)
        self.assertIn("study: benchmark study", call("project_status")["content"][0]["text"])
        t = call("key_numbers", brief=True)["content"][0]["text"]
        self.assertIn("propose_numbers", t)
        self.assertIn("results/tests.csv", t)
        r = call("propose_numbers", numbers=numbers()["numbers"])
        self.assertFalse(r.get("isError"), r)
        t = r["content"][0]["text"]
        self.assertIn("MISMATCH rho: report 0.91, file 0.194", t)
        self.assertIn("Only the researcher can confirm it", t)
        self.assertEqual(self.e.numbers()["counts"]["confirmed"], 0, "an agent proposes; it cannot confirm")
        self.assertTrue(call("propose_numbers", numbers="x")["isError"])
        self.e.decide_numbers("confirm")
        t = call("key_numbers", claim="H1")["content"][0]["text"]
        self.assertIn("OK Cliff's delta: report 0.58, file 0.5841", t)
        self.assertNotIn("Step C: cells ok", t)
        self.assertIn("Open provenance gaps", t)
        # an empty answer says what it rests on
        self.assertIn("not evidence that nothing changed", call("alarms")["content"][0]["text"])
        self.assertIn("is not evidence about a paper", call("findings")["content"][0]["text"])
        self.e.add_runs([{"run_id": "check-20261116-1000", "source": "agent", "command": "python src/check.py", "exit_code": 0}], by="t")
        t = call("runs")["content"][0]["text"]
        self.assertIn("0 experiment runs", t)
        self.assertIn("plus 1 commands that wrote no file and no number", t)
        self.assertNotIn("check-20261116-1000", t)
        self.assertIn("check-20261116-1000", call("runs", commands=True)["content"][0]["text"])
        t = call("setup")["content"][0]["text"]
        self.assertIn("Benchmark study: nothing is 'ours'", t)


if __name__ == "__main__":
    unittest.main()
