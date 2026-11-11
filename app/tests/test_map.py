"""Project map (S12): brief, proposal, rule checks, confirmation, and map-driven tracking. Standard library only."""
import json
import os
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
        for f in ("map.json", "claims.json", "experiments.json"):
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
        self.assertTrue(call("propose_map", {"map": "x"})[0])


if __name__ == "__main__":
    unittest.main()
