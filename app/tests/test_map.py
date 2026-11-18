"""Project map (S12): brief, proposal, rule checks, confirmation, and map-driven tracking. Standard library only."""
import json
import os

import pytest
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lemmata import mcp  # noqa: E402
from lemmata.engine import understand as und  # noqa: E402
from lemmata.engine.api import Engine  # noqa: E402
from lemmata.engine.errors import BadRequest, NotFound  # noqa: E402


def make_project(R):
    os.makedirs(R + "/paper"); os.makedirs(R + "/code/results/main"); os.makedirs(R + "/code/results/tuning"); os.makedirs(R + "/code/logs"); os.makedirs(R + "/.lemmata")
    with open(R + "/.lemmata/project.json", "w") as f:
        json.dump({"schema": "lemmata.project/1", "name": "mcd", "repos": [{"id": "paper", "role": "paper", "path": "paper"}, {"id": "code", "role": "code", "path": "code"}]}, f)
    def w(p, s):
        os.makedirs(os.path.dirname(R + "/" + p), exist_ok=True)
        with open(R + "/" + p, "w") as f:
            f.write(s)

    def git(d,*a,date=None):
        env=dict(os.environ,GIT_AUTHOR_NAME='j',GIT_AUTHOR_EMAIL='j@x',GIT_COMMITTER_NAME='j',GIT_COMMITTER_EMAIL='j@x')
        if date: env.update(GIT_AUTHOR_DATE=date,GIT_COMMITTER_DATE=date)
        subprocess.run(['git','-C',R + '/'+d,*a],check=True,env=env,capture_output=True)
    w('paper/main.tex', r'''\documentclass{article}
    \title{Drift-aware detection with Monte Carlo Dropout}
    \begin{document}
    \maketitle
    \begin{abstract}
    Online detectors fail silently when the data distribution moves. We extend Monte Carlo Dropout (MCD) with an uncertainty-triggered update and show that it detects drift earlier at a lower false positive count on three streams.
    \end{abstract}
    \section{Introduction}
    Detectors degrade under drift. Our central question is whether predictive uncertainty is enough to decide when to update the model.
    We further study whether the gain survives without the adaptive threshold, and what the method costs in compute.
    \section{Method}
    MCD keeps dropout active at test time.
    \section{Experiments}
    \begin{table}
    \caption{False positives on three streams (lower is better).}
    \label{tab:main}
    \begin{tabular}{lccc}
    Method & Electricity & Weather & Covtype \\
    ADWIN & 41.0 & 37.5 & 52.0 \\
    DDM & 38.0 & 35.0 & 49.5 \\
    MCD & \textbf{30.0} & \textbf{29.5} & \textbf{44.0} \\
    \end{tabular}
    \end{table}
    \begin{table}
    \caption{Ablation of the adaptive threshold.}
    \label{tab:abl}
    \begin{tabular}{lc}
    Variant & Electricity \\
    MCD & 30.0 \\
    MCD-fixed & 36.0 \\
    \end{tabular}
    \end{table}
    \end{document}
    ''')
    git('paper','init','-q'); git('paper','add','-A'); git('paper','commit','-qm','paper',date='2026-10-01T09:00:00+09:00')
    w('code/train.py','import argparse\np=argparse.ArgumentParser()\np.add_argument("--dataset")\np.add_argument("--lr")\np.add_argument("--dropout")\nopen("results/main/x.csv","w")\n')
    w('code/detect.py','THRESH=0.5\n')
    w('code/config.yaml','lr: 0.01\ndropout: 0.2\n')
    git('code','init','-q')
    def main(vals, date, msg):
        for ds,(a,d,m) in vals.items():
            for meth,v in (('ADWIN',a),('DDM',d),('MCD',m)):
                for seed in (1,2):
                    w('code/results/main/%s,y_%s_seed%d.csv'%(ds,meth,seed),'fp,CPU_Time,delay\n%.1f,%.2f,%d\n'%(v+(0.5 if seed==1 else -0.5), 1.0+seed*0.1, 12))
        git('code','add','-A'); git('code','commit','-qm',msg,date=date)
    main({'Electricity':(41,38,43),'Weather':(37.5,35,36),'Covtype':(52,49.5,50)},'2026-10-02T10:00:00+09:00','first full run')
    for ds in ('Electricity','Weather'):
        for lr in ('0.1','0.01','0.001'):
            for dr in ('0.1','0.2'):
                w('code/results/tuning/hypertuning,%s,lr=%s,drop=%s.csv'%(ds,lr,dr),'fp,CPU_Time\n%.1f,%.2f\n'%(30+(len(ds)+float(lr)*10+float(dr)*10)%10,1.2))
    w('code/logs/debug_run.csv','step,loss\n1,0.5\n2,0.4\n')
    git('code','add','-A'); git('code','commit','-qm','hyperparameter search',date='2026-10-05T10:00:00+09:00')
    w('code/detect.py','THRESH=adaptive()\n'); 
    main({'Electricity':(41,38,30),'Weather':(37.5,35,29.5),'Covtype':(52,49.5,46)},'2026-10-09T10:00:00+09:00','adaptive threshold')
    for v,val in (('MCD',30.0),('MCD-fixed',36.0)):
        w('code/results/ablation_%s.csv'%v,'variant,dataset,fp\n%s,Electricity,%.1f\n'%(v,val))
    git('code','add','-A'); git('code','commit','-qm','ablation',date='2026-10-12T10:00:00+09:00')

agent = {"method":{"name":"MCD","aliases":["Monte Carlo Dropout","McDrop"],"evidence":[{"path":"main.tex","line":6,"quote":"We extend Monte Carlo Dropout (MCD)"}]},
 "questions":[{"id":"q1","kind":"question","text":"Is predictive uncertainty enough to decide when to update the model?","evidence":[{"path":"main.tex","line":9,"quote":"whether predictive uncertainty is enough to decide when to update"}]},
  {"id":"q2","kind":"hypothesis","text":"The gain depends on the adaptive threshold.","evidence":[{"path":"main.tex","line":10,"quote":"whether the gain survives without the adaptive threshold"}]},
  {"id":"q3","kind":"hypothesis","text":"MCD is cheap.","evidence":[{"path":"main.tex","line":10,"quote":"what the method costs in compute"}]},
  {"id":"q4","kind":"hypothesis","text":"Made up.","evidence":[{"path":"main.tex","line":10,"quote":"this sentence is not in the paper"}]}],
 "experiments":[{"id":"main","name":"Main comparison","type":"main","tests":["q1"],"files":["results/main/{dataset},y_{method}_seed{seed}.csv"],"metric":"fp","lower":True,"paper":["tab:main"],"note":"3 streams, 2 seeds"},
  {"id":"abl","name":"Adaptive threshold ablation","type":"ablation","tests":["q2"],"files":["results/ablation_*.csv"],"metric":"fp","lower":True,"method_column":"variant","paper":["tab:abl"]},
  {"id":"tune","name":"Learning rate and dropout search","type":"tuning","tests":["q1"],"files":["results/tuning/hypertuning,{dataset},lr={lr},drop={drop}.csv"],"metric":"fp","lower":True},
  {"id":"cost","name":"Compute cost","type":"efficiency","tests":["q3","q9"],"files":["results/main/{dataset},y_{method}_seed{seed}.csv"],"metric":"CPU_Time","lower":True},
  {"id":"ghost","name":"Ghost","type":"main","tests":["q1"],"files":["results/nothing/*.csv"],"paper":["tab:nope"]}],
 "ignore":["logs/**"]}


class MapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        make_project(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        for f in ("map.json", "claims.json", "experiments.json", "stages.json"):
            p = Path(self.tmp, ".lemmata", f)
            if p.exists():
                p.unlink()
        self.e = Engine(self.tmp)
        self.e.scan()

    def test_pattern(self):
        rx, fields = und.compile_pattern("results/{dataset},y_{method}_seed{seed}.csv")
        self.assertEqual(fields, ["dataset", "method", "seed"])
        self.assertEqual(rx.match("results/Weather,y_MCD_seed2.csv").groupdict(), {"dataset": "Weather", "method": "MCD", "seed": "2"})
        self.assertIsNone(rx.match("results/sub/Weather,y_MCD_seed2.csv"))
        self.assertTrue(und.compile_pattern("logs/**")[0].match("logs/a/b.csv"))
        self.assertFalse(und.compile_pattern("results/*.csv")[0].match("results/main/a.csv"))
        for bad in ("", "x" * 300, "{a}{a}.csv"):
            with self.assertRaises(BadRequest):
                und.compile_pattern(bad)

    def test_brief_groups_files_by_shape(self):
        g = {c["pattern"]: c for c in self.e.brief()["result_files"]["groups"]}
        self.assertEqual(g["results/main/*,y_*_*.csv"]["n"], 18)
        self.assertEqual(g["results/main/*,y_*_*.csv"]["varies"][:2], [["Covtype", "Electricity", "Weather"], ["ADWIN", "DDM", "MCD"]])
        self.assertEqual(g["results/tuning/hypertuning,*,lr=*,drop=*.csv"]["varies"][1], ["0.001", "0.01", "0.1"])
        self.assertEqual(self.e.experiments()["map"], {"state": "none"})
        self.assertGreater(len(self.e.experiments()["unassigned"]), 30)        # the flood this sprint removes

    def test_checker_drops_what_it_cannot_verify(self):
        d = self.e.propose_map(agent)
        self.assertEqual(d["state"], "proposed")
        m = d["proposed"]
        self.assertEqual(m["method"], {"name": "MCD", "aliases": ["Monte Carlo Dropout"], "evidence": [{"repo": "paper", "path": "main.tex", "line": 6, "quote": "We extend Monte Carlo Dropout (MCD)"}]})
        self.assertEqual([q["id"] for q in m["questions"]], ["q1", "q2", "q3"])                      # q4 quotes words that are not in the paper
        self.assertEqual([(x["id"], x["matched"]) for x in m["experiments"]], [("main", 18), ("abl", 2), ("tune", 12), ("cost", 18)])   # ghost matches nothing
        self.assertEqual(m["experiments"][3]["tests"], ["q3"])
        dropped = [r["where"] for r in d["report"] if r["level"] == "dropped"]
        self.assertEqual(sorted(set(dropped)), ["experiment ghost", "method", "question q4"])
        self.assertEqual(self.e.experiments()["map"], {"state": "proposed"})                         # a proposal changes nothing yet
        with self.assertRaises(BadRequest):
            self.e.propose_map("not a map")

    def test_confirm_then_track(self):
        self.e.propose_map(agent)
        d = self.e.confirm_map()
        self.assertEqual((d["state"], d["proposed"]), ("confirmed", None))
        x = self.e.experiments()
        self.assertEqual(x["counts"]["unmapped"], 0)
        self.assertEqual([(s["label"], s["kind"], [q["id"] for q in s["experiments"]]) for s in x["sections"]],
                         [("RQ1", "question", ["map:main", "map:tune"]), ("H1", "hypothesis", ["map:abl"]), ("H2", "hypothesis", ["map:cost"])])
        main = x["sections"][0]["experiments"][0]
        sm = main["summary"]
        self.assertEqual((sm["ours_label"], sm["ours_by"], sm["measure"], sm["metric"], sm["lower"], sm["rank"]), ("MCD", "map", "fp", "Average", True, 1))
        self.assertEqual(main["tally"], {"match": 8, "rounding": 0, "differs": 1, "loose": 0, "untraced": 0})      # the paper says 44.0, the files say 46
        self.assertFalse(any(p["kind"] == "bold" for p in main["problems"]))
        self.assertEqual(x["sections"][0]["experiments"][1]["tuning"]["runs"], 6)
        one = self.e.experiment("map:main")
        self.assertEqual([(h["time"][:10], round(h["ours"], 2), h["rank"]) for h in one["history"]], [("2026-10-02", 43.0, 2), ("2026-10-09", 35.17, 1)])
        self.assertTrue(one["history"][1]["became_best"])
        self.assertEqual(one["history"][1]["cats"], ["method"])
        self.assertEqual(one["design"]["files"][0]["fields"], {"dataset": "Covtype", "method": "ADWIN", "seed": "1"})
        self.assertEqual(self.e.set_experiment("map:main", metric="Electricity")["summary"]["ours"], 30.0)
        self.assertEqual(self.e.set_experiment("map:main", measure="CPU_Time")["summary"]["measure"], "CPU_Time")
        with self.assertRaises(NotFound):
            self.e.experiment("map:nope")
        claims = {c["id"]: c for c in self.e.claims()["claims"]}                                      # questions became claims, linked to their tables
        cid = d["confirmed"]["questions"][0]["claim_id"]
        self.assertEqual([s["name"] for s in claims[cid]["support"]], ["Table 1"])
        self.e.propose_map(agent)
        self.assertEqual([q["claim_id"] for q in self.e.confirm_map()["confirmed"]["questions"]][0], cid)   # confirming again does not duplicate them

    def test_claims_have_stages_and_experiments_have_a_reason(self):
        """S17: one kind of claim moving through stages; every experiment is tied to the claim it was run for."""
        self.e.propose_map(agent)
        self.e.confirm_map()
        d = self.e.claims()
        by = {c["ref"]: c for c in d["claims"]}
        self.assertEqual([c["short"] for c in d["claims"]], ["C1", "C2", "C3"])                       # one numbering, whatever the source called them
        self.assertEqual(by["RQ1"]["stage"], "testing")                                               # ahead, but the paper's table differs from the files
        self.assertIn("needs checking", by["RQ1"]["stage_why"])
        self.assertEqual((by["H1"]["stage"], by["H1"]["stage_by"]), ("finding", "evidence"))
        self.assertEqual([x["name"] for x in by["H1"]["experiments"]], ["Adaptive threshold ablation"])
        self.assertEqual(d["counts"]["stages"], {"hypothesis": 0, "testing": 1, "finding": 2, "refuted": 0, "exploration": 0})
        self.assertEqual(d["core"]["stage"], "testing")
        # the past, read from the stored results: behind before the adaptive threshold, ahead after it
        self.assertEqual([(s["t"][:10], s["stage"], s["by"]) for s in by["RQ1"]["stages"][:2]], [("2026-10-02", "refuted", "history"), ("2026-10-09", "finding", "history")])
        self.assertEqual(by["RQ1"]["stages"][-1]["stage"], "testing")
        log = json.loads(Path(self.tmp, ".lemmata", "stages.json").read_text())["log"]
        self.assertEqual(log[by["H1"]["id"]][-1]["stage"], "finding")
        n = len(log[by["H1"]["id"]])
        self.e.claims()
        self.assertEqual(len(json.loads(Path(self.tmp, ".lemmata", "stages.json").read_text())["log"][by["H1"]["id"]]), n)      # recorded only when it changes
        # the researcher's own call wins and is recorded; "auto" hands it back to the evidence
        c = {c["id"]: c for c in self.e.set_claim(by["H2"]["id"], stage="exploration")["claims"]}[by["H2"]["id"]]
        self.assertEqual((c["stage"], c["stage_by"], c["stage_auto"]), ("exploration", "you", "finding"))
        self.assertEqual(self.e.claims()["counts"]["stages"]["exploration"], 1)
        c = {c["id"]: c for c in self.e.set_claim(by["H2"]["id"], stage="auto")["claims"]}[by["H2"]["id"]]
        self.assertEqual([s["stage"] for s in c["stages"]][-3:], ["finding", "exploration", "finding"])
        with self.assertRaises(BadRequest):
            self.e.set_claim(by["H2"]["id"], stage="proved")
        # the tree: the experiments are the first roots of the claim they were run for
        t = self.e.tree()
        xs = {n["id"]: n for n in t["nodes"] if n["kind"] == "experiment"}
        self.assertEqual(xs["map:abl"]["state"], "ahead")
        self.assertIn({"from": by["H1"]["id"], "to": "map:abl", "kind": "support", "how": "detected", "stale": False}, t["edges"])
        self.assertFalse(any(n["kind"] == "missing" for n in t["nodes"]))
        self.assertEqual({n["id"]: n["stage"] for n in t["nodes"] if n["layer"] == "claim"}[by["H1"]["id"]], "finding")
        # Experiments: each section is a claim with its stage; each experiment says why it was run
        E = self.e.experiments()
        self.assertEqual([(s["short"], s["stage"]) for s in E["sections"]], [("C1", "testing"), ("C2", "finding"), ("C3", "finding")])
        self.assertEqual(E["sections"][1]["experiments"][0]["why"][0]["id"], by["H1"]["id"])
        self.assertEqual(E["counts"]["no_claim"], 0)
        self.e.edit_map({"experiment": {"id": "cost", "tests": []}})
        self.e.confirm_map()
        E = self.e.experiments()
        self.assertEqual((E["sections"][-1]["label"], E["counts"]["no_claim"]), ("No claim yet", 1))
        self.assertIn({"k": "why", "t": "Tests no claim"}, E["sections"][-1]["experiments"][0]["caveats"])
        self.assertEqual({c["ref"]: c["stage"] for c in self.e.claims()["claims"]}["H2"], "hypothesis")     # no experiment left behind it
        self.assertIn("- Stage: **Finding**", self.e.claims_markdown())

    def test_stage_rules(self):
        from lemmata.engine.claims import stage_of
        t = lambda *st: [{"state": s, "connected": s != "planned", "check": False} for s in st]
        emp = {"formal": False, "status": "unsupported"}
        self.assertEqual(stage_of(emp)[0], "hypothesis")
        self.assertEqual(stage_of(emp, t("planned"))[0], "hypothesis")
        self.assertEqual(stage_of(emp, t("none"))[0], "testing")
        self.assertEqual(stage_of(emp, t("ahead", "behind"))[0], "testing")
        self.assertEqual(stage_of(emp, t("ahead", "tie", "none"))[0], "finding")
        self.assertEqual(stage_of(emp, t("behind", "behind"))[0], "refuted")
        self.assertEqual(stage_of(emp, [{"state": "ahead", "connected": True, "check": True}])[0], "testing")
        self.assertEqual(stage_of(dict(emp, status="supported"))[0], "finding")                        # no experiments: the traced evidence decides
        self.assertEqual([stage_of({"formal": True, "status": s})[0] for s in ("unsupported", "partial", "supported")], ["hypothesis", "testing", "finding"])

    def test_edit_discard_and_unmapped(self):
        self.e.propose_map(dict(agent, ignore=[]))
        cov = self.e.project_map()["coverage"]
        self.assertEqual((cov["n_files"], cov["files"][0]["pattern"]), (1, "logs/debug_run.csv"))
        d = self.e.edit_map({"experiment": {"id": "tune", "tests": ["q2"], "type": "sensitivity"}})
        self.assertEqual([(x["type"], x["tests"]) for x in d["proposed"]["experiments"] if x["id"] == "tune"], [("sensitivity", ["q2"])])
        d = self.e.edit_map({"remove": "question:q3"})
        self.assertEqual([x["tests"] for x in d["proposed"]["experiments"] if x["id"] == "cost"], [[]])
        self.assertEqual(self.e.edit_map({"ignore": "logs/**"})["coverage"]["n_files"], 0)
        self.assertEqual(self.e.edit_map({"method": "DDM"})["proposed"]["method"]["name"], "DDM")
        self.e.confirm_map()
        self.assertEqual(self.e.experiments()["sections"][-1]["kind"], "other")
        self.assertEqual(self.e.discard_map()["state"], "confirmed")
        with self.assertRaises(NotFound):
            self.e.confirm_map()

    def test_rule_draft_and_empty_map(self):
        d = self.e.draft_map()
        self.assertEqual((d["proposed_by"], d["proposed"]["method"]["name"]), ("rules", "MCD"))
        self.assertEqual([(x["name"], x["type"], x["matched"]) for x in d["proposed"]["experiments"]][:2], [("main", "main", 18), ("tuning", "tuning", 12)])
        self.e.propose_map({"method": {"name": "Nope"}, "questions": [], "experiments": []})
        with self.assertRaises(BadRequest):
            self.e.confirm_map()

    def test_fixes_from_the_first_real_run(self):
        """Problems seen on mcd_extension, 2026-11-11: names only in table cells, silent caps, questions in notes, 'close to 0'."""
        R = self.tmp
        with open(R + "/code/RESEARCH_QUESTIONS.md", "w") as f:
            f.write("# Questions\n\nE1: Does the extension generalise better than the original detector?\n")
        with open(R + "/code/results/excess.csv", "w") as f:
            f.write("method,dataset,excess\nADWIN,Electricity,-3.0\nMCD_EXT,Electricity,0.4\nDDM,Electricity,1.5\n" + "".join("pad%d,Electricity,9\n" % i for i in range(5)))
        subprocess.run(["git", "-C", R + "/code", "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", R + "/code", "-c", "user.name=j", "-c", "user.email=j@x", "commit", "-qm", "excess"], check=True, capture_output=True)
        e = Engine(R)
        e.scan()
        doc = dict(agent, method={"name": "MCD", "aliases": ["MCD_EXT"]},
                   questions=agent["questions"][:1] + [{"id": "e1", "text": "Does the extension generalise better?", "evidence": [{"path": "RESEARCH_QUESTIONS.md", "line": 3, "quote": "Does the extension generalise better"}]}],
                   experiments=[{"id": "exc", "name": "Calibration", "type": "analysis", "tests": ["e1"], "files": ["results/excess.csv"], "metric": "excess", "target": 0, "ours": "MCD_EXT"},
                                {"id": "many", "name": "Many", "type": "main", "tests": ["q1"], "files": ["results/main/*.csv"] * 25}])
        d = e.propose_map(doc)
        m = d["proposed"]
        self.assertEqual(m["method"]["aliases"], ["MCD_EXT"])                                        # found in a table cell, not in the first rows' sample
        self.assertEqual([(q["id"], q["source"]) for q in m["questions"]], [("q1", "paper"), ("e1", "notes")])
        self.assertIn("only the first 24 file patterns are kept; 1 more were ignored", [r["why"] for r in d["report"]])
        e.confirm_map()
        x = e.experiment("map:exc")
        sm = x["summary"]
        self.assertEqual((sm["ours_label"], sm["rank"], sm["target"], sm["measure"]), ("MCD_EXT", 1, 0, "|excess − 0|"))   # 0.4 beats -3.0
        self.assertEqual(x["table"]["rows"][0]["values"]["Electricity"], -3.0)                                    # the raw values are kept for display
        self.assertEqual(e.experiments()["sections"][1]["source"], "notes")
        os.remove(R + "/code/RESEARCH_QUESTIONS.md")
        os.remove(R + "/code/results/excess.csv")
        subprocess.run(["git", "-C", R + "/code", "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", R + "/code", "-c", "user.name=j", "-c", "user.email=j@x", "commit", "-qm", "undo"], check=True, capture_output=True)

    def test_extension_of_the_paper(self):
        """The linked paper is the original; ours is a variant named in the results; the map says what it extends and why."""
        R = self.tmp
        with open(R + "/code/NOTES.md", "w") as f:
            f.write("Goal: generalise MCD to unseen streams.\nE1: Does the variant beat the original under drift?\n")
        with open(R + "/code/results/ext.csv", "w") as f:
            f.write("method,dataset,fp\nADWIN,Electricity,41\nMCD,Electricity,30\nMCD_EXT,Electricity,27\n")
        subprocess.run(["git", "-C", R + "/code", "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", R + "/code", "-c", "user.name=j", "-c", "user.email=j@x", "commit", "-qm", "ext"], check=True, capture_output=True)
        e = Engine(R)
        e.scan()
        doc = {"method": {"name": "MCD_EXT"}, "base": {"name": "MCD", "aliases": ["Monte Carlo Dropout"]}, "goal": "Generalise MCD to unseen streams.",
               "questions": [agent["questions"][0], {"id": "e1", "text": "Does the variant beat the original under drift?", "evidence": [{"path": "NOTES.md", "line": 2, "quote": "Does the variant beat the original"}]}],
               "experiments": [{"id": "ext", "name": "Extension vs original", "type": "main", "tests": ["e1"], "files": ["results/ext.csv"], "metric": "fp", "lower": True},
                               dict(agent["experiments"][0], ours="MCD")]}
        d = e.propose_map(doc)
        m = d["proposed"]
        self.assertEqual((m["method"]["name"], m["base"]["name"], m["goal"]), ("MCD_EXT", "MCD", "Generalise MCD to unseen streams."))
        self.assertEqual([(q["id"], q["scope"]) for q in m["questions"]], [("q1", "base"), ("e1", "extension")])
        self.assertEqual(e.edit_map({"question": {"id": "q1", "scope": "extension"}})["proposed"]["questions"][0]["scope"], "extension")
        e.edit_map({"question": {"id": "q1", "scope": "base"}})
        e.confirm_map()
        x = e.experiments()
        self.assertEqual(x["extends"]["base"]["name"], "MCD")
        self.assertEqual([(s["id"], s["scope"]) for s in x["sections"]], [("e1", "extension"), ("q1", "base")])           # the extension comes first
        sm = x["sections"][0]["experiments"][0]["summary"]
        self.assertEqual((sm["ours_label"], sm["base"]), ("MCD_EXT", {"label": "MCD", "value": 30.0, "gap": 3.0}))
        self.assertEqual(x["sections"][1]["experiments"][0]["summary"]["ours_label"], "MCD")                            # re-checking the original: ours is MCD there
        self.assertEqual(e.edit_map({"base": ""})["proposed"]["base"], None)
        bad = e.propose_map(dict(doc, base={"name": "MCD_EXT"}))
        self.assertIn("the base method has the same name as ours", [r["why"] for r in bad["report"]])
        e.discard_map()
        for f in ("NOTES.md", "results/ext.csv"):
            os.remove(R + "/code/" + f)
        subprocess.run(["git", "-C", R + "/code", "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", R + "/code", "-c", "user.name=j", "-c", "user.email=j@x", "commit", "-qm", "undo"], check=True, capture_output=True)

    def test_plans(self):
        """S20/S21: the agent plans from a brief; Lemmata keeps grounded, complete specs and renders the prompt from them."""
        from lemmata.engine.errors import NotFound as NF
        from lemmata.engine import plans as P
        self.e.propose_map(agent)
        self.e.confirm_map()
        E = self.e.experiments()
        q = next(s for s in E["sections"] if s["kind"] != "other")
        b = self.e.plan_brief("q:" + q["id"])
        self.assertEqual((b["kind"], b["claims"][0]["id"]), ("claim", q["id"]))
        self.assertTrue(b["experiments"] and "scripts" in b["experiments"][0] and "checklist" in b["claims"][0])
        self.assertIn("propose_experiments", b["how_to_propose"])
        x = q["experiments"][0]
        bx = self.e.plan_brief("x:" + x["id"])
        self.assertEqual((bx["kind"], bx["experiments"][0]["id"]), ("experiment", x["id"]))
        self.assertTrue(any(c["id"] == q["id"] for c in bx["claims"]), "an experiment's brief carries the claim it tests")
        with self.assertRaises(NF):
            self.e.plan_brief("q:nope")
        good = {"kind": "seeds", "title": "Two more seeds", "why": "Only two runs per method.",
                "files": [{"path": "train.py", "quote": 'add_argument("--dataset")'}],
                "goal": "Check the fp gap holds with four seeds.",
                "decision": {"supports": "MCD mean fp below ADWIN on all 3 datasets by more than 1 std", "against": "not below on 2 or more datasets"},
                "context": [{"path": "train.py", "role": "entry point"}, {"path": "config.yaml", "role": "lr and dropout"}],
                "protected": ["detect.py", "results/main/"], "steps": ["Add --seed to train.py."],
                "smoke": "python train.py --dataset Electricity --seed 3", "run": ["python train.py --dataset Electricity --seed 3", "python train.py --dataset Electricity --seed 4"],
                "results_to": "results/main/{dataset},y_{method}_seed{seed}.csv", "budget": "6 runs", "baseline_check": "ADWIN fp 43.5 within 2"}
        r = self.e.propose_plans("q:" + q["id"], [good,
            dict(good, title="Fake quote", files=[{"path": "train.py", "quote": "this text is not in the file"}]),
            dict(good, title="No decision", decision={"supports": "it gets better"}),
            dict(good, title="Fourth")])
        self.assertEqual([p["title"] for p in r["plans"]], ["Two more seeds"])
        n = "\n".join(r["notes"])
        self.assertIn("no file whose quote", n); self.assertIn("missing against", n); self.assertIn("only the first 3", n)
        self.assertIn("kind must be", "\n".join(self.e.propose_plans("q:" + q["id"], [dict(good, kind="party")])["notes"]))
        p = r["plans"][0]
        self.assertEqual((p["state"], p["files"][0]["path"], p["files"][0]["line"]), ("draft", "train.py", 3))
        # the prompt is rendered from the spec with the fixed sections
        pr = p["prompt"]
        for tag in ("goal", "decision_rule", "context", "protected", "steps", "outputs", "verification", "stop_conditions", "report_format"):
            self.assertIn("<%s>" % tag, pr); self.assertIn("</%s>" % tag, pr)
        self.assertIn('train.py:3 (entry point); it contains', pr)
        self.assertIn("- results/main/", pr); self.assertIn("Smoke test: `python train.py --dataset Electricity --seed 3`", pr)
        self.assertIn(".lemmata/exp/%s/manifest.json" % p["id"], pr.replace("under ", "").replace("/:\n- manifest.json", "/manifest.json"))
        self.assertIn("never overwrite or delete", pr); self.assertIn("synthetic, placeholder or estimated numbers", pr)
        self.assertIn("the known value does not reproduce", pr)
        self.assertEqual(p["deny"], ["Edit(./detect.py)", "Edit(./results/main/**)"])
        self.assertEqual(p["lint"], [])
        # the researcher edits fields; the prompt follows; lints point at problems
        v = self.e.set_plan(p["id"], spec={"protected": "detect.py\neval/", "run": ["python train2.py --seed 3"], "supports": "it should improve"})
        p2 = v["plans"][0]
        self.assertTrue(p2["edited"]); self.assertIn("- eval/", p2["prompt"]); self.assertIn("train2.py --seed 3", p2["prompt"])
        self.assertTrue(any("eval/" in w for w in p2["lint"]) and any("train2.py" in w for w in p2["lint"]) and any("not measurable" in w for w in p2["lint"]))
        self.e.set_plan(p["id"], spec={"context": "config.yaml — learning rate"})
        self.assertIn("- config.yaml (learning rate)", self.e.plans()["plans"][0]["prompt"])
        with self.assertRaises(BadRequest):
            self.e.set_plan(p["id"], spec={"prompt": "free text"})
        self.e.set_plan(p["id"], "copied", title="Seeds 3 and 4")
        self.assertEqual([(x["state"], x["title"]) for x in self.e.plans()["plans"]], [("copied", "Seeds 3 and 4")])
        self.e.propose_plans("q:" + q["id"], [dict(good, title="Second round")])      # new drafts replace drafts, copied ones stay
        self.assertEqual(sorted(x["title"] for x in self.e.plans()["plans"]), ["Second round", "Seeds 3 and 4"])
        d = next(x for x in self.e.plans()["plans"] if x["title"] == "Second round")
        self.e.set_plan(d["id"], "dropped")
        self.assertEqual([x["title"] for x in self.e.plans()["plans"]], ["Seeds 3 and 4"])
        with self.assertRaises(NF):
            self.e.set_plan("p_nope", "copied")
        with self.assertRaises(BadRequest):
            self.e.propose_plans("q:" + q["id"], [])
        self.assertIn("<example>", P.GUIDE); self.assertNotIn("EXAMPLE", P.GUIDE)

    def test_review(self):
        """Should I continue: three checks, the five-item checklist, and confounds reported by an agent."""
        from datetime import datetime, timezone
        self.e.propose_map(agent)
        self.e.confirm_map()
        now = datetime(2026, 10, 13, tzinfo=timezone.utc)
        r = self.e.review(30, now)
        self.assertEqual([(c["k"], c["verdict"]) for c in r["checks"]], [("moving", "yes"), ("ahead", "yes"), ("paper", "no")])
        self.assertEqual([(b["name"], b["ahead"], b["tie"], b["behind"], b["verdict"]) for b in r["baselines"]], [("ADWIN", 1, 1, 0, "ahead"), ("DDM", 1, 1, 0, "ahead")])
        self.assertEqual(r["checks"][1]["line"], "Ahead of 2 of 2 baselines")
        for b in r["baselines"]:                    # side-by-side numbers: ours, the baseline, and a gap that agrees with them
            for x in b["experiments"]:
                self.assertIsNotNone(x["ours"]); self.assertIsNotNone(x["value"]); b["base"] or self.assertEqual(x["label"].lower(), b["name"].lower())
                self.assertAlmostEqual(x["gap"], (x["value"] - x["ours"]) if x["lower"] else (x["ours"] - x["value"]))
        self.assertEqual(self.e.review(1, now)["checks"][0]["line"], "1 of 3 claims moved in 1 day")
        q = {x["ref"]: x for x in r["questions"]}
        self.assertEqual((q["H1"]["label"], q["H1"]["stage"]), ("C2", "finding"))      # the Review names claims as the Claims page does
        self.assertEqual([(c["k"], c["state"]) for c in q["H1"]["checklist"]],
                         [("seeds", "todo"), ("baseline", "done"), ("ablation", "done"), ("paper", "done"), ("confounds", "todo")])
        self.assertEqual((q["RQ1"]["done"], q["RQ1"]["of"]), (2, 5))
        with self.assertRaises(BadRequest):
            self.e.review(3)
        notes = self.e.report_confounds([
            {"question": "q1", "verdict": "risk", "confounds": [{"text": "Learning rate was tuned for MCD only.", "evidence": {"path": "train.py", "quote": 'p.add_argument("--lr")'}},
                                                               {"text": "made up", "evidence": {"path": "train.py", "quote": "not there at all"}}]},
            {"question": "q2", "verdict": "clear"}, {"question": "zz", "verdict": "clear"}])["notes"]
        self.assertEqual(notes, ["dropped (q1): a confound whose quote is not in 'train.py'", "kept (q1): risk, 1 confound", "kept (q2): clear, 0 confounds", "dropped: unknown question 'zz'"])
        q = {x["ref"]: x for x in self.e.review(30, now)["questions"]}
        self.assertEqual((q["RQ1"]["checklist"][4]["state"], q["H1"]["checklist"][4]["state"]), ("todo", "done"))
        r = self.e.set_review(hoped="MCD detects drift earlier.", question="q1", resolve=0)
        self.assertEqual(r["hoped"], "MCD detects drift earlier.")
        self.assertEqual({x["ref"]: x for x in r["questions"]}["RQ1"]["checklist"][4]["state"], "done")
        self.assertEqual({x["ref"]: x for x in self.e.set_review(question="q3", mine=True)["questions"]}["H2"]["checklist"][4]["why"], "Checked by you, none found")
        self.assertIn("report_confounds", self.e.confound_brief() and __import__("lemmata.engine.review", fromlist=["GUIDE"]).GUIDE)
        os.remove(self.tmp + "/.lemmata/review.json")

    def test_links_and_thesis(self):
        """S24 step 1 (ADR-008): a status on every claim-experiment link, the thesis as counts, and the two gap buckets."""
        self.e.propose_map(agent)
        self.e.confirm_map()
        before = {c["id"]: c["stage"] for c in self.e.claims()["claims"]}
        E = self.e.experiments()
        words = {"supports", "contradicts", "inconclusive", "not_run"}
        for sec in E["sections"]:
            self.assertEqual(set(sec["links"]), {x["id"] for x in sec["experiments"]})
            for l in sec["links"].values():
                self.assertIn(l["status"], words)
                self.assertIn(l["rule"], ("L1", "L2", "L3", "L4"))
                self.assertTrue(l["why"])
                self.assertEqual(l["criterion_by"], "default")
            self.assertEqual(sum(sec["bar"].values()), len(sec["experiments"]))
        by = {sec["id"]: sec for sec in E["sections"]}
        self.assertEqual({k: (v["status"], v["rule"]) for k, v in by["q1"]["links"].items()},
                         {"map:main": ("supports", "L3"), "map:tune": ("inconclusive", "L2")})
        self.assertEqual(by["q3"]["links"]["map:cost"]["status"], "supports")            # a tie counts as support (default criterion)
        self.assertIn("tie counts", by["q3"]["links"]["map:cost"]["why"])
        T = E["thesis"]
        self.assertEqual((T["rule"], T["claims"], sum(T["stages"].values()), T["links_n"], T["links"]),
                         ("T1", 3, 3, 4, {"supports": 3, "contradicts": 0, "inconclusive": 1, "not_run": 0}))
        self.assertEqual(T["buckets"], {"untested": 0, "no_claim": 0})
        self.assertNotIn("stage", T)                                                     # counts only, never a verdict
        self.assertEqual({c["id"]: c["stage"] for c in self.e.claims()["claims"]}, before)   # the links change no claim's stage
        self.assertEqual(before, {"mine:1": "testing", "mine:2": "finding", "mine:3": "finding"})
        # one experiment testing two claims has a link on each; a claim nothing tests and an experiment testing nothing are counted
        doc = dict(agent, experiments=[dict(x, tests=["q1", "q2"]) if x["id"] == "main" else dict(x, tests=[]) if x["id"] == "cost" else x for x in agent["experiments"]])
        self.e.propose_map(doc)
        self.e.confirm_map()
        E = self.e.experiments()
        by = {sec["id"]: sec for sec in E["sections"]}
        self.assertEqual((by["q1"]["links"]["map:main"]["status"], by["q2"]["links"]["map:main"]["status"]), ("supports", "supports"))
        T = E["thesis"]
        self.assertEqual(T["buckets"], {"untested": 1, "no_claim": 1})
        self.assertEqual([c["id"] for c in T["untested"]], ["mine:3"])
        self.assertEqual(T["links_n"], sum(len(sec["experiments"]) for sec in E["sections"] if sec.get("kind") != "other"))

    def test_board(self):
        """S28: thesis <- claims <- experiments <- what was used, from the Setup document; a gap is kept and counted."""
        B = self.e.setup()["board"]                      # no map yet: one experiment per result file, no claim
        self.assertEqual((B["mode"], B["rough"]), ("paper", True))
        self.assertTrue(B["counts"]["experiments_no_claim"] and B["counts"]["experiments_no_claim"] == B["counts"]["experiments"] - sum(1 for x in B["experiments"] if x["claims"]))
        self.e.propose_map(agent)
        self.e.confirm_map()
        S = self.e.setup()
        B = S["board"]
        self.assertEqual((B["mode"], B["rough"], B["thesis"]["kind"]), ("paper", False, "thesis"))
        self.assertEqual([c["label"] for c in B["claims"]], ["C1", "C2", "C3"])
        X = {x["name"]: x for x in B["experiments"]}
        c1 = B["claims"][0]
        self.assertEqual(sorted(c1["experiments"]), sorted([X["Main comparison"]["id"], X["Learning rate and dropout search"]["id"]]))
        self.assertEqual(c1["links"][X["Main comparison"]["id"]], "supports")
        self.assertEqual(X["Adaptive threshold ablation"]["claims"], [B["claims"][1]["id"]])
        self.assertIn("dataset:electricity", X["Adaptive threshold ablation"]["items"])
        self.assertEqual(X["Main comparison"]["sheets"], [X["Main comparison"]["id"]])
        I = {i["id"]: i for i in B["items"]}
        self.assertEqual(len(I["dataset:electricity"]["experiments"]), 4)
        self.assertEqual({i["id"] for i in B["items"]}, {i["id"] for i in S["items"] if i["experiments"]})
        self.assertEqual((B["counts"]["experiments_no_claim"], B["counts"]["claims_untested"], B["counts"]["items_unreached"]), (0, 0, 0))

    def test_link_rules(self):
        """Rules L1-L4, each from a minimal experiment."""
        L = lambda x: Engine._link(x, False, "the best other method")
        x = {"map": True, "files_n": 3, "summary": {"gap": -2.0, "metric": "F1"}}
        self.assertEqual((L(dict(x, files_n=0))["status"], L(dict(x, files_n=0))["rule"]), ("not_run", "L1"))
        self.assertEqual((L(dict(x, summary=None))["status"], L(dict(x, summary=None))["rule"]), ("inconclusive", "L2"))
        self.assertEqual((L(dict(x, tuning={"runs": 4}))["rule"], L(x)["status"], L(x)["rule"]), ("L2", "contradicts", "L4"))
        self.assertIn("behind the best other method by 2 on F1", L(x)["why"])
        self.assertEqual([L(dict(x, summary={"gap": g}))["status"] for g in (1.5, 0.0)], ["supports", "supports"])
        self.assertEqual(L({"connected": False, "summary": {"gap": 1}})["rule"], "L1")       # rule mode: not linked to a result
        own = Engine._link(dict(x, summary={"gap": 3.0, "base": {"gap": -1.0}}), True, "MCD-DD")   # an extension is judged against its base
        self.assertEqual((own["status"], own["criterion"]["compare"]), ("contradicts", "base"))

    def test_stage_rule_ids(self):
        """S24 step 2: every claim stage names the rule (C1-C9) that produced it."""
        from lemmata.engine import claims as cm
        S = lambda c, t=None: cm.stage_of(c, t)
        plain = {"formal": False, "status": "unsupported"}
        t = lambda state, connected=True, check=False: {"state": state, "connected": connected, "check": check}
        self.assertEqual([S({"formal": True, "status": st})[::2] for st in ("supported", "partial", "unsupported")],
                         [("finding", "C2"), ("testing", "C2"), ("hypothesis", "C2")])
        self.assertEqual([S({"formal": False, "status": st})[::2] for st in ("supported", "partial", "unsupported")],
                         [("finding", "C3"), ("testing", "C3"), ("hypothesis", "C3")])
        self.assertEqual(S(plain, [t("ahead", connected=False)])[::2], ("hypothesis", "C4"))
        self.assertEqual(S(plain, [t("none")])[::2], ("testing", "C5"))
        self.assertEqual(S(plain, [t("behind"), t("behind")])[::2], ("refuted", "C6"))
        self.assertEqual(S(plain, [t("ahead"), t("behind")])[::2], ("testing", "C7"))
        self.assertEqual(S(plain, [t("ahead", check=True), t("tie")])[::2], ("testing", "C8"))
        self.assertEqual(S(plain, [t("ahead"), t("tie"), t("none")])[::2], ("finding", "C9"))
        self.assertEqual(set(cm.STAGE_RULES), {"C%d" % i for i in range(1, 10)})
        self.e.propose_map(agent)
        self.e.confirm_map()
        by = {c["id"]: c for c in self.e.claims()["claims"]}
        self.assertEqual({k: c["stage_rule"] for k, c in by.items()}, {"mine:1": "C8", "mine:2": "C9", "mine:3": "C9"})
        self.e.set_claim("mine:2", stage="exploration")
        c = next(c for c in self.e.claims()["claims"] if c["id"] == "mine:2")
        self.assertEqual((c["stage"], c["stage_rule"], c["stage_rule_auto"]), ("exploration", "C1", "C9"))
        self.assertIn("rule C1", self.e.claims_markdown() if hasattr(self.e, "claims_markdown") else "rule C1")

    def test_criterion(self):
        """S24 step 3: a criterion on one claim-experiment link, from the map or set by the researcher."""
        doc = dict(agent, experiments=[dict(x, tests=["q1", "q3"], criteria={"q3": {"compare": "ADWIN", "over": "all", "strict": True}, "q9": {"over": "all"}, "q1": {"over": "sometimes"}})
                                       if x["id"] == "cost" else x for x in agent["experiments"]])
        d = self.e.propose_map(doc)
        notes = " ".join(n["why"] for n in d["report"])
        self.assertIn("criterion dropped", notes)                                        # an unknown question and a bad value are dropped, with a note
        self.assertEqual([x.get("criteria") for x in d["proposed"]["experiments"] if x["id"] == "cost"], [{"q3": {"compare": "ADWIN", "over": "all", "strict": True}}])
        self.e.confirm_map()
        by = {s_["id"]: s_ for s_ in self.e.experiments()["sections"]}
        l3, l1 = by["q3"]["links"]["map:cost"], by["q1"]["links"]["map:cost"]
        self.assertEqual((l3["criterion_by"], l3["status"], l3["rule"]), ("confirmed", "contradicts", "L4"))     # CPU time is level: strict turns a tie into contradicts
        self.assertEqual((l1["criterion_by"], l1["status"]), ("default", "supports"))                            # the same experiment's other link keeps its own
        stage = {c["id"]: (c["stage"], c["stage_rule"]) for c in self.e.claims()["claims"]}
        self.assertEqual(stage["mine:3"], ("refuted", "C6"))
        # the researcher's own criterion wins over the map's; clearing it goes back
        E = self.e.set_experiment("map:cost", claim="mine:3", criterion={"compare": "ADWIN", "over": "majority", "strict": False})
        l = next(s_ for s_ in E["sections"] if s_["id"] == "q3")["links"]["map:cost"]
        self.assertEqual((l["criterion_by"], l["status"]), ("you", "supports"))
        self.assertIn("of 3 datasets", l["why"])
        E = self.e.set_experiment("map:cost", claim="mine:3", criterion={"compare": "Nobody"})
        self.assertEqual(next(s_ for s_ in E["sections"] if s_["id"] == "q3")["links"]["map:cost"]["status"], "inconclusive")
        E = self.e.set_experiment("map:cost", claim="mine:3", criterion=None)
        self.assertEqual(next(s_ for s_ in E["sections"] if s_["id"] == "q3")["links"]["map:cost"]["criterion_by"], "confirmed")
        with self.assertRaises(Exception):
            self.e.set_experiment("map:cost", claim="mine:3", criterion={"over": "sometimes"})
        with self.assertRaises(Exception):
            self.e.set_experiment("map:cost", claim="nope", criterion={})

    def test_todo_and_trail(self):
        """S24 steps 4-5: a to-do made by rules where each item names what it opens, and the trail with deadlines."""
        self.e.propose_map(agent)
        kinds = lambda: [(i["group"], i["kind"]) for i in self.e.todo("2026-11-16")["items"]]
        self.assertIn(("confirm", "map"), kinds())
        self.e.confirm_map()
        self.assertNotIn(("confirm", "map"), kinds())                                   # the rule stopped firing: the item is gone
        self.e.add_feedback("Check Table 1 against the new results.", "Advisor meeting")
        T = self.e.todo("2026-11-16")
        self.assertEqual([(i["group"], i["kind"]) for i in T["items"]], [("person", "feedback"), ("paper", "differs"), ("gap", "seeds")])   # in the order of who is waiting
        for i in T["items"]:
            self.assertTrue(i["target"].get("view") and i["why"] and i["rule"])
        d = next(i for i in T["items"] if i["kind"] == "differs")
        self.assertEqual((d["target"], d["why"]), ({"view": "experiments", "sel": "x:map:main"}, "MCD, Covtype: the paper says 44.0, the file says 46.0."))
        T = self.e.snooze_todo(d["key"], "2099-01-01")
        self.assertEqual((T["counts"]["snoozed"], [i["kind"] for i in T["items"] if i["kind"] == "differs"]), (1, []))
        self.assertEqual(self.e.snooze_todo(d["key"], None)["counts"]["snoozed"], 0)
        with self.assertRaises(Exception):
            self.e.snooze_todo(d["key"], "next week")
        # a strict criterion that fails becomes a gap item pointing at the experiment
        self.e.set_experiment("map:cost", claim="mine:3", criterion={"strict": True})
        self.assertIn(("gap", "contradicts"), kinds())
        # trail: every kind of record, newest first, deadlines ahead, a deadline on a target orders the to-do
        tr = self.e.set_deadline("2099-12-01", "Camera ready", "x:map:main")
        self.assertEqual([x["title"] for x in tr["ahead"]], ["Camera ready"])
        self.assertEqual(next(i for i in self.e.todo("2026-11-16")["items"] if i["kind"] == "differs")["due"], "2099-12-01")
        self.assertTrue(all(tr["counts"][k] for k in ("paper", "code", "claims", "feedback", "decisions")))
        self.assertEqual([e["t"] for e in tr["entries"]], sorted((e["t"] for e in tr["entries"]), reverse=True))
        self.assertEqual(tr["days"]["2026-10-01"]["paper"], 1)
        self.assertEqual(len(self.e.trail("2026-10-05", "2026-10-09")["entries"]), len([e for e in tr["entries"] if "2026-10-05" <= e["day"] <= "2026-10-09"]))
        self.assertEqual(self.e.set_deadline(remove=tr["deadlines"][0]["id"])["deadlines"], [])
        with self.assertRaises(Exception):
            self.e.set_deadline("soon", "x")

    def test_venues_calendar_and_sheet(self):
        """S25: conference deadlines from the open data (a plain lookup), journal dates by hand, the calendar file,
        the day detail on the trail, and the Setup protocol sheet."""
        from lemmata.engine import venues
        SAMPLE = "- title: ZCONF\n  description: The Z Conference\n  sub: AI\n  confs:\n    - year: 2026\n      id: z26\n      link: https://z.example/2026\n      timeline:\n        - deadline: 'TBD'\n      timezone: UTC-8\n" \
                 "    - year: 2027\n      id: z27\n      link: https://z.example/2027\n      timeline:\n        - abstract_deadline: '2027-01-14 23:59:59'\n          deadline: '2027-01-22 23:59:59'\n      timezone: AoE\n      date: August 2-4, 2027\n      place: Rio\n"
        calls = []

        def fetch(url):
            calls.append(url)
            if url.endswith("/conference/AI/zconf.yml"):
                return SAMPLE
            e = OSError("404")
            e.code = 404
            raise e
        r = venues.lookup("ZConf", 2027, fetch)
        self.assertEqual([(d["kind"], d["date"], d["time"], d["tz"], d["utc"]) for d in r["deadlines"]],
                         [("abstract", "2027-01-14", "23:59", "AoE", "2027-01-15T11:59:00Z"), ("paper", "2027-01-22", "23:59", "AoE", "2027-01-23T11:59:00Z")])
        self.assertEqual((r["venue"], r["link"], r["source"].endswith("conference/AI/zconf.yml")), ("ZCONF", "https://z.example/2027", True))
        self.assertEqual(venues.lookup("zconf", 2026, fetch)["deadlines"][0]["date"], None)             # still to be announced
        for bad in (("nope", 2027), ("zconf", 2031)):
            with self.assertRaises(Exception):
                venues.lookup(*bad, fetch)
        self.assertTrue(all(u.startswith("https://raw.githubusercontent.com/ccfddl/ccf-deadlines/") for u in calls))
        self.e.propose_map(agent)
        self.e.confirm_map()
        with self.assertRaises(Exception):
            self.e.add_venue("zconf", 2026, fetch=fetch)                                                 # nothing dated: nothing stored
        tr = self.e.add_venue("zconf", 2027, fetch=fetch)
        tr = self.e.add_venue("zconf", 2027, fetch=fetch)                                                # adding again replaces, never doubles
        self.assertEqual([(d["title"], d["kind"]) for d in tr["deadlines"]], [("ZCONF 2027: abstract", "abstract"), ("ZCONF 2027: paper", "paper")])
        tr = self.e.set_deadline("2026-12-20", "Submit to TKDE", kind="journal", venue="IEEE TKDE")
        self.assertEqual(tr["deadlines"][0]["kind"], "journal")
        with self.assertRaises(Exception):
            self.e.set_deadline("2026-12-20", "x", kind="paper")
        ics = self.e.calendar_ics()
        self.assertEqual((ics.count("BEGIN:VEVENT"), "DTSTART:20270123T115900Z" in ics, "DTSTART;VALUE=DATE:20261220" in ics, ics.endswith("END:VCALENDAR\r\n")), (3, True, True, True))
        self.assertEqual(self.e.calendar()["token"], None)
        tok = self.e.calendar("create")["token"]
        self.assertEqual((len(tok) >= 24, self.e.calendar()["token"] == tok, self.e.calendar("revoke")["token"]), (True, True, None))
        self.assertEqual(len(self.e.set_deadline(remove="ZCONF 2027")["deadlines"]), 1)                  # a venue is removed as a whole
        # the day detail: what a commit did to each experiment's result
        c = next(x for x in self.e.trail()["entries"] if x["kind"] == "code" and x["title"] == "adaptive threshold")
        m = next(r_ for r_ in c["detail"]["results"] if r_["x"] == "map:main")
        self.assertEqual((m["claims"], m["before"], round(m["after"], 2), c["detail"]["files_n"]), (["C1"], 43.0, 35.17, {"results": 6, "code": 1}))
        # the protocol sheet
        x = next(r_ for r_ in self.e.setup()["experiments"] if r_["id"] == "map:main")
        self.assertEqual((x["protocol"]["metric"], x["protocol"]["datasets"], x["protocol"]["seeds"], [m_["role"] for m_ in x["protocol"]["methods"]]),
                         ("fp", ["Covtype", "Electricity", "Weather"], [2, 2], ["baseline", "baseline", "ours"]))
        self.assertEqual({c_["k"]: c_["a"] for c_ in x["checklist"]}, {"coverage": "yes", "seeds": "yes", "paper": "no", "current": "yes", "details": "you", "compute": "you"})
        ours = next(r_ for r_ in x["grid"]["rows"] if r_["role"] == "ours")
        self.assertEqual((ours["values"]["Covtype"], ours["n"]["Covtype"], ours["best"]), (46.0, 2, ["Covtype", "Electricity", "Weather"]))
        ab = next(r_ for r_ in self.e.setup()["experiments"] if r_["id"] == "map:abl")
        self.assertEqual({c_["k"]: c_["a"] for c_ in ab["checklist"]}["seeds"], "no")

    def test_setup(self):
        """S23: the metrics, datasets and methods the experiments use, connected to the experiments and the claims."""
        self.e.propose_map(agent)
        self.e.confirm_map()
        d = self.e.setup()
        by = {it["id"]: it for it in d["items"]}
        self.assertEqual({k: d["counts"][k] for k in ("metric", "dataset", "method", "baselines", "experiments")},
                         {"metric": 3, "dataset": 3, "method": 4, "baselines": 2, "experiments": 4})
        self.assertEqual([it["kind"] for it in d["items"]][:3], ["metric"] * 3)                       # metrics, then datasets, then methods
        fp = by["metric:fp"]
        self.assertEqual((fp["direction"], fp["main_in"], sorted(fp["experiments"])), ("lower", 3, ["map:abl", "map:cost", "map:main", "map:tune"]))
        self.assertEqual({u["x"]: u["role"] for u in fp["uses"]}["map:cost"], "recorded")              # the cost experiment's number is CPU time
        self.assertEqual([c["k"] for c in by["metric:delay"]["checks"]], ["unused"])
        el = by["dataset:electricity"]
        main = next(u for u in el["uses"] if u["x"] == "map:main")
        self.assertEqual((main["ours"], main["best_other"], main["rank"], main["methods"]), (30.0, {"label": "DDM", "value": 38.0}, 1, 3))
        tune = next(u for u in el["uses"] if u["x"] == "map:tune")
        self.assertEqual((tune["ours"], tune["rank"], tune["runs"]), (None, None, 6))                  # a search has no "ours"
        self.assertEqual((el["ours_best"], el["compared"]), (3, 3))
        self.assertEqual((by["method:mcd"]["role"], by["method:adwin"]["role"], by["method:mcdfixed"]["role"]), ("ours", "baseline", "variant"))
        ad = next(u for u in by["method:adwin"]["uses"] if u["x"] == "map:main")
        self.assertEqual((round(ad["value"], 2), round(ad["gap"], 2), ad["wins"], ad["compared"]), (43.5, 8.33, 0, 3))
        self.assertEqual([c["dataset"] for c in ad["cells"]], ["Covtype", "Electricity", "Weather"])
        self.assertEqual(by["method:adwin"]["paper"]["lines"][0]["line"], 19)                          # where the paper names it
        self.assertIn("cite", [c["k"] for c in by["method:adwin"]["checks"]])
        cid = next(c for c in d["claims"] if "map:abl" in c["experiments"])
        self.assertEqual(sorted(cid["items"]), ["dataset:electricity", "method:mcd", "method:mcdfixed", "metric:fp"])
        x = next(r for r in d["experiments"] if r["id"] == "map:cost")
        self.assertEqual((x["main_metric"], x["claims"]), ("metric:cputime", [cid2 for cid2 in x["claims"]]))
        # a baseline with no result on one dataset is flagged where it is missing
        with open(self.tmp + "/code/results/main/Weather,y_ADWIN_seed1.csv") as f:
            keep = f.read()
        try:
            for seed in (1, 2):
                os.remove(self.tmp + "/code/results/main/Weather,y_ADWIN_seed%d.csv" % seed)
            subprocess.run(["git", "-C", self.tmp + "/code", "add", "-A"], check=True, capture_output=True)
            subprocess.run(["git", "-C", self.tmp + "/code", "-c", "user.name=j", "-c", "user.email=j@x", "commit", "-qm", "drop"], check=True, capture_output=True)
            e = Engine(self.tmp)
            e.scan()
            d2 = {it["id"]: it for it in e.setup()["items"]}
            self.assertIn("No result on Weather", [c["t"] for c in d2["method:adwin"]["checks"]])
            self.assertEqual(next(u for u in d2["dataset:weather"]["uses"] if u["x"] == "map:main")["missing"], ["ADWIN"])
        finally:
            subprocess.run(["git", "-C", self.tmp + "/code", "revert", "--no-edit", "HEAD"], check=True, capture_output=True,
                           env=dict(os.environ, GIT_AUTHOR_NAME="j", GIT_AUTHOR_EMAIL="j@x", GIT_COMMITTER_NAME="j", GIT_COMMITTER_EMAIL="j@x"))
        self.assertTrue(keep)

    def test_mcp_tools(self):
        ctx = mcp.LocalCtx(self.tmp)
        pid = ctx.list_projects()[0]["id"]

        def call(name, args):
            _, out = mcp.handle(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": dict(args, project=pid)}}), ctx)
            r = json.loads(out)["result"]
            return r["isError"], r["content"][0]["text"]
        err, text = call("project_brief", {})
        self.assertFalse(err)
        self.assertIn("propose_map", text)
        self.assertIn("hypertuning", call("project_brief", {"part": "files"})[1])
        err, text = call("propose_map", {"map": agent})
        self.assertFalse(err)
        self.assertIn("DROPPED · question q4", text)
        self.assertIn("Only the researcher can confirm", text)
        self.assertIn("Map state: proposed", call("project_map", {})[1])
        err, text = call("setup", {"kind": "dataset"})                 # S23: before confirming, the setup is read file by file
        self.assertFalse(err)
        self.assertIn("No confirmed project map", text)
        self.assertIn("DATASET Electricity", text)
        self.assertNotIn("METRIC ", text)
        self.assertTrue(call("propose_map", {"map": "x"})[0])
        _, out = mcp.handle(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "project_brief", "arguments": {"project": pid, "part": "files"}}}), ctx)
        self.assertEqual(json.loads(out)["result"]["structuredContent"]["result_files"]["total"], 33)      # clients that read structured content see the data
        _, out = mcp.handle(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "project_brief", "arguments": {"project": pid}}}), ctx)
        self.assertIn("propose_map", json.loads(out)["result"]["structuredContent"]["how_to_write_a_map"])
        rep = self.e.propose_map(dict(agent, method={"name": "MCD", "base": {"name": "DDM"}}, goal={"text": "x"}, extra=1))["report"]
        whys = [r["why"] for r in rep]
        self.assertIn("unknown field 'extra' (the map has: method, base, goal, questions, experiments, ignore)", whys)
        self.assertIn("unknown field 'base' inside method; base and goal go at the top level of the map", whys)
        self.assertIn("the goal must be one sentence of plain text", whys)


if __name__ == "__main__":
    unittest.main()


def test_sessions_and_summaries(tmp_path):
    """S26: a day's records become work sessions that say who, where, what, why, how and with what result; summaries are drafted by an agent and confirmed by the researcher."""
    import datetime
    from lemmata.engine import sessions as S
    from lemmata.engine.errors import BadRequest, NotFound
    # reading one command line, by rules
    r = S.read_command("cd /w/code && DATA_ROOT=/d python scripts/run_main.py --dataset Covtype --seed=3 lr=0.1 --fast")
    assert (r["type"], r["script"], r["cd"], r["env"]) == ("script", "scripts/run_main.py", "/w/code", {"DATA_ROOT": "/d"})
    assert r["args"] == {"dataset": "Covtype", "seed": "3", "lr": "0.1", "fast": True}
    assert S.read_command("python - <<'EOF'\nprint(1)\nEOF")["type"] == "analysis" and S.read_command("python3 -c 'print(1)'")["type"] == "analysis"
    for c in ("pgrep -af train", "ls -la results | head", "git status", "nvidia-smi", "cd x && cat log.txt"):
        assert S.read_command(c)["type"] == "inspection", c
    assert S.read_command("pip install torch")["type"] == "setup" and S.read_command("git commit -m x")["type"] == "git" and S.read_command("latexmk -pdf main.tex")["type"] == "writing"
    assert S.read_command("uv run python -m pkg.train --seed 1")["script"] == "pkg.train" and S.read_command("nohup bash run_all.sh")["script"] == "run_all.sh"
    rx, fixed = S.matcher("results/main/{dataset},y_{method}_seed{seed}.csv")
    assert fixed == "results/main" and rx.search("/abs/code/results/main/Covtype,y_MCD_seed3.csv").groupdict() == {"dataset": "Covtype", "method": "MCD", "seed": "3"}
    assert S.matcher("results/ablation_*.csv")[0].search("results/ablation_a.csv") and not S.matcher("results/ablation_*.csv")[0].search("results/x/ablation_a.csv")

    root = str(tmp_path / "p"); os.makedirs(root); make_project(root)
    e = Engine(root); e.scan(); e.propose_map(agent); e.confirm_map()
    code = os.path.join(root, "code")
    base = datetime.datetime.now().astimezone().replace(hour=12, minute=0, second=0, microsecond=0) - datetime.timedelta(days=1)
    at = lambda m: (base + datetime.timedelta(minutes=m)).isoformat()
    runs = [
        dict(run_id="run-001", source="terminal", command="cd %s && python scripts/run_main.py --dataset Covtype --method MCD --seed 3" % code, cwd=code, host="srv", git_sha="a" * 40, dirty=True,
             artifacts=[{"path": "results/main/Covtype,y_MCD_seed3.csv"}], metrics={"fp": 0.12}, started=at(0), ended=at(6), exit_code=0),
        dict(run_id="run-002", source="terminal", command="python scripts/run_main.py --dataset Weather --method MCD --seed 3", cwd=code, host="srv", started=at(7), ended=at(8), exit_code=1),
        dict(run_id="run-003", source="terminal", command="pgrep -af run_main", cwd=code, host="srv", started=at(9), ended=at(9), exit_code=1),
        dict(run_id="run-004", source="terminal", command="python - <<'EOF'\nimport pandas\nEOF", cwd="/tmp/claude-1011/x/scratchpad", host="srv", started=at(20), ended=at(20), exit_code=0),
        dict(run_id="run-005", source="terminal", command="python scripts/plot.py", cwd=code + "_rq2", host="srv", artifacts=[{"path": "figs/a.png"}], started=at(60), ended=at(61), exit_code=0),
        dict(run_id="run-006", source="terminal", command="nvidia-smi", cwd=code, host="srv", started=at(200), ended=at(200), exit_code=0),
    ]
    e.add_runs(runs, "test")
    T = e.trail()
    day = base.isoformat()[:10]
    ss = [s for s in T["sessions"] if s["day"] == day]
    assert T["gap_minutes"] == 60 and len(ss) == 2                       # 61 minutes of activity with gaps under an hour, then one command 139 minutes later
    late, s = ss
    assert late["rule_title"].startswith("Looked around") and late["hidden_n"] == 1 and not late["why"]["known"]
    assert s["start"][11:16] == "12:00" and s["end"][11:16] == "13:01" and s["minutes"] == 61 and s["commands_n"] == 5
    assert s["who"] == [{"who": "you", "n": 4}, {"who": "agent", "n": 1}]   # a command run from the agent's scratch folder is the agent's
    assert s["where"]["hosts"] == ["srv"] and s["where"]["dirty"] and s["where"]["scratch"] == 1
    assert [p["name"] for p in s["where"]["places"]] == ["code", "code_rq2 (a second copy of code)"]   # a worktree counts as the same project
    assert s["rule_title"].startswith("Ran Main comparison") and "C1" in s["why"]["claims"] and s["why"]["known"]
    x = next(x for x in s["experiments"] if x["id"] == "map:main")
    assert x["how"] == "wrote" and x["fields"] == {"dataset": ["Covtype"], "method": ["MCD"], "seed": ["3"]}
    assert s["how"]["scripts"][0] == {"name": "scripts/run_main.py", "n": 2, "failed": 1} and {"key": "dataset", "values": ["Covtype", "Weather"]} in s["how"]["args"]
    assert s["result"]["failed"] == 1 and s["result"]["metrics"] == [{"key": "fp", "value": 0.12}] and s["result"]["files"][0]["tracked"]   # a failed inspection is not a failure
    assert s["counts"] == {"run": 1, "script": 2, "analysis": 1, "inspection": 1} and [c["hidden"] for c in s["commands"]].count(True) == 1
    assert any("2 runs of scripts/run_main.py, 1 failed" == w for w in s["what"])
    assert all("_run" not in en for en in T["entries"])
    # a commit-only session keeps the commit message as its title and names who committed
    old = next(z for z in T["sessions"] if z["commits"] and not z["commands_n"])
    assert old["authors"] == ["j"] and old["title"] in [en["title"] for en in old["entries"] if en["kind"] in ("paper", "code")]

    # summaries: the agent drafts, the researcher confirms; a confirmed one is never replaced by a draft
    with pytest.raises(NotFound):
        e.session_note("nope", "x")
    with pytest.raises(BadRequest):
        e.session_note(s["id"], " ", None, by="agent")
    T = e.session_note(s["id"], "Third seed for the main comparison (RQ1).", None, by="agent")
    s2 = next(z for z in T["sessions"] if z["id"] == s["id"])
    assert s2["title"] == "Third seed for the main comparison (RQ1)." and s2["note"]["state"] == "proposed" and s2["rule_title"] == s["rule_title"]
    with pytest.raises(BadRequest):
        e.session_note(s["id"], None, "confirm", by="agent")
    T = e.session_note(s["id"], None, "confirm")
    assert next(z for z in T["sessions"] if z["id"] == s["id"])["note"]["state"] == "confirmed"
    with pytest.raises(BadRequest):
        e.session_note(s["id"], "Another draft.", None, by="agent")
    T = e.session_note(s["id"], "My own words.")
    assert next(z for z in T["sessions"] if z["id"] == s["id"])["note"]["by"] == "you"
    T = e.session_note(s["id"], None, "remove")
    assert next(z for z in T["sessions"] if z["id"] == s["id"])["note"] is None
    assert "who:" in S.brief(s) and "why:" in S.brief(s)

    # Setup: each experiment says where, how, when and who
    c = next(x for x in e.setup()["experiments"] if x["id"] == "map:main")["context"]
    assert c["where"]["folder"] == "results/main" and c["where"]["hosts"] == ["srv"] and c["how"]["scripts"] == ["scripts/run_main.py"]
    assert c["who"]["runs"] == 2 and c["who"]["by"] == [{"who": "you", "n": 2}] and c["when"]["first"] and c["when"]["last"]
    assert c["runs"][-1]["fields"]["method"] == ["MCD"] and c["runs"][-1]["dirty"] is True
