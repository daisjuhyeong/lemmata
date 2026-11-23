"""S36 phase 2, Home (stdlib unittest): the to-do items say which wait on the researcher (needs_you, act), and the
"Since you last looked" record and API (per person, per project; local server and hub).
Run: PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_s36_home.py'"""
import http.client
import importlib.util
import json
import shutil
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lemmata.engine import since as sincemod  # noqa: E402
from lemmata.engine import todo as todomod  # noqa: E402
from lemmata.engine import trail as trailmod  # noqa: E402
from lemmata.engine.api import Engine  # noqa: E402
from lemmata.server import bind  # noqa: E402

_spec = importlib.util.spec_from_file_location("make_sample", str(APP / "samples" / "make_sample.py"))
make_sample = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_sample)

NOW = "2026-11-22T12:00:00+09:00"


def entry(t, kind="code", title="x", by=None):
    return {"t": t, "day": t[:10], "kind": kind, "title": title, "why": None, "target": {"view": "claims"}, "at": None, "ref": None, "by": by}


class SinceUnit(unittest.TestCase):
    TRAIL = {"entries": [
        entry("2026-11-22T10:00:00+09:00", "runs", "python a.py", {"kind": "run", "name": "gpu1"}),
        entry("2026-11-21T09:00:00+09:00", "code", "fix loader", {"kind": "person", "name": "Ada"}),
        entry("2026-11-20T09:00:00+09:00", "claims", "C1: Finding", {"kind": "lemmata", "name": None}),
        entry("2026-11-19T09:00:00+09:00", "feedback", "Feedback: advisor", None),
        entry("2026-11-10T09:00:00+09:00", "paper", "old", None)]}

    def test_first_visit_covers_seven_days_and_says_so(self):
        d = sincemod.build(self.TRAIL, None, NOW)
        self.assertTrue(d["first_visit"])
        self.assertEqual(d["days"], 7)
        self.assertEqual([r["text"] for r in d["items"]], ["python a.py", "fix loader", "C1: Finding", "Feedback: advisor"])      # newest first; the 12th is outside the 7 days

    def test_after_a_visit_only_what_is_newer(self):
        d = sincemod.build(self.TRAIL, "2026-11-21T00:00:00+09:00", NOW)
        self.assertFalse(d["first_visit"])
        self.assertIsNone(d["days"])
        self.assertEqual([r["text"] for r in d["items"]], ["python a.py", "fix loader"])
        self.assertEqual(sincemod.build(self.TRAIL, NOW, NOW)["items"], [])

    def test_time_zones_are_compared_as_times(self):
        d = sincemod.build(self.TRAIL, "2026-11-21T23:30:00Z", NOW)      # 23:30 UTC on the 21st is 08:30 on the 22nd in Seoul
        self.assertEqual([r["text"] for r in d["items"]], ["python a.py"])

    def test_who_is_only_what_the_record_says(self):
        rows = {r["text"]: r["who"] for r in sincemod.build(self.TRAIL, None, NOW)["items"]}
        self.assertEqual(rows["python a.py"]["label"], "A run (gpu1)")
        self.assertEqual(rows["fix loader"]["label"], "Ada")
        self.assertEqual(rows["C1: Finding"]["label"], "Lemmata")
        self.assertEqual(rows["Feedback: advisor"], {"kind": None, "name": None, "label": None})      # no record: the kind only, no guess
        self.assertEqual(next(r["kind_word"] for r in sincemod.build(self.TRAIL, None, NOW)["items"] if r["text"] == "Feedback: advisor"), "Feedback")

    def test_the_person_is_stored_as_a_hash(self):
        st = sincemod.mark({"users": {}}, "Alice", NOW)
        self.assertEqual(list(st["users"].values()), [NOW])
        self.assertNotIn("alice", json.dumps(st).lower())
        self.assertEqual(sincemod.key_of("ALICE"), sincemod.key_of("alice"))
        self.assertNotEqual(sincemod.key_of("alice"), sincemod.key_of(None))
        for i in range(sincemod.MAX_USERS + 5):
            sincemod.mark(st, "u%d" % i, NOW)
        self.assertLessEqual(len(st["users"]), sincemod.MAX_USERS)


class TodoNeedsYou(unittest.TestCase):
    def build(self, **kw):
        E = {"sections": [], "thesis": {}, "study": None}
        C = {"claims": [{"id": "c1", "label": "C1", "short": "C1", "text": "It is better.", "state": "proposed"},
                        {"id": "c2", "label": "C2", "short": "C2", "text": "Done.", "state": "confirmed"}]}
        tasks = {"tasks": [{"id": "t1", "state": "open", "text": "Fix Table 2", "claims": [{"id": "c2", "label": "C2"}], "targets": [], "source": "advisor"},
                           {"id": "t2", "state": "open", "text": "Something vague", "claims": [], "targets": [], "source": "advisor"},
                           {"id": "t3", "state": "open", "text": "Rerun the loader", "claims": [], "targets": [{"node_id": "file:code/load.py", "name": "load.py"}], "source": "advisor"}]}
        return todomod.build(E, C, {"items": []}, tasks, {"findings": []}, {"summary": {}}, {"plans": []}, {"proposed": None}, [], {"snoozed": {}}, "2026-11-22", **kw)

    def test_every_item_says_whether_it_waits_on_you(self):
        items = self.build(hypo={"problem": {"proposed": {"gap": {}}, "validity": "unreviewed"}, "hypotheses": [
            {"id": "H1", "statement": "A beats B", "validity": "unreviewed"}, {"id": "H2", "statement": "x", "validity": "valid"}, {"id": "H3", "statement": "y", "validity": "unreviewed", "archived": True}]},
            baselines={"rows": [{"name": "ADWIN", "proposal": {"by": "claude"}}, {"name": "DDM", "proposal": None}]})["items"]
        self.assertTrue(all(isinstance(i["needs_you"], bool) and "act" in i for i in items))
        mine = {(i["kind"], i["key"].split(":", 1)[1]): i for i in items if i["needs_you"]}
        self.assertEqual(sorted(mine), [("baseline", "ADWIN"), ("claim", "c1"), ("feedback", "t1"), ("feedback", "t2"), ("hypothesis", "H1"), ("problem", "problem")])
        self.assertEqual(mine[("claim", "c1")]["act"], {"do": "confirm_claim", "id": "c1"})
        self.assertEqual(mine[("hypothesis", "H1")]["act"], {"do": "confirm_hypothesis", "target": "H1"})
        self.assertEqual(mine[("problem", "problem")]["act"], {"do": "confirm_hypothesis", "target": "problem"})
        self.assertEqual(mine[("baseline", "ADWIN")]["act"], {"do": "confirm_baseline", "name": "ADWIN"})
        # feedback: with no target or at a claim it waits on the researcher (done is the one existing task action); at a file only, it is work to do
        self.assertEqual(mine[("feedback", "t1")]["act"], {"do": "task_done", "id": "t1"})
        self.assertEqual((mine[("feedback", "t1")]["text"], mine[("feedback", "t1")]["target"]["sel"]), ("C2: Fix Table 2", "c2"))
        self.assertEqual(mine[("feedback", "t2")]["act"], {"do": "task_done", "id": "t2"})
        work = next(i for i in items if i["kind"] == "feedback" and i["key"].endswith("t3"))
        self.assertFalse(work["needs_you"])
        self.assertIsNone(work["act"])

    def test_a_drafted_core_message_is_a_needs_you_item(self):
        E = {"sections": [], "thesis": {}, "study": None}
        C = {"core": {"id": "core", "state": "proposed", "text": "Drift-aware detection with Monte Carlo Dropout is cheaper and earlier than the baselines on three streams."}, "claims": []}
        its = todomod.build(E, C, {"items": []}, {"tasks": []}, {"findings": []}, {"summary": {}}, {"plans": []}, {"proposed": None}, [], {"snoozed": {}}, "2026-11-23")["items"]
        (it,) = [i for i in its if i["key"] == "claim:core"]
        self.assertTrue(it["needs_you"])
        self.assertEqual(it["act"], {"do": "confirm_claim", "id": "core"})
        self.assertLessEqual(len(it["text"]), 80)      # one line
        C["core"]["state"] = "confirmed"
        self.assertEqual([i for i in todomod.build(E, C, {"items": []}, {"tasks": []}, {"findings": []}, {"summary": {}}, {"plans": []}, {"proposed": None}, [], {"snoozed": {}}, "2026-11-23")["items"] if i["key"] == "claim:core"], [])

    def test_needs_you_sentences_are_short_and_keep_the_full_text_in_why(self):
        long = "Monte Carlo Dropout detects drift earlier and with fewer false positives than every baseline we compared against in this study"
        E = {"sections": [], "thesis": {}, "study": None}
        C = {"claims": [{"id": "c1", "label": "C1", "short": "C1", "text": long, "state": "proposed"}]}
        its = todomod.build(E, C, {"items": []}, {"tasks": [{"id": "t1", "state": "open", "text": long * 2, "claims": [], "targets": [], "source": "advisor"}]}, {"findings": []}, {"summary": {}}, {"plans": []}, {"proposed": None}, [], {"snoozed": {}}, "2026-11-23")["items"]
        it = next(i for i in its if i["kind"] == "claim")
        fb = next(i for i in its if i["kind"] == "feedback")
        self.assertLessEqual(len(fb["text"]), 80)
        self.assertIn(long * 2, fb["why"])
        self.assertLessEqual(len(it["text"]), 75)
        self.assertTrue(it["text"].startswith("Confirm C1: "))
        self.assertIn(long, it["why"])


class TodoSentences(unittest.TestCase):
    def test_every_mismatch_gives_both_sides_in_one_sentence(self):
        probs = [{"kind": "differs", "row": "MCD", "col": "Covtype", "paper": "44.0", "file": 46.0},
                 {"kind": "bold", "col": "Electricity", "paper": "30.0", "best": 28.5}]
        x = {"id": "x1", "name": "Main", "tally": {"differs": 1, "untraced": 1}, "problems": probs, "untraced_cells": [{"row": "DDM", "col": "Weather", "paper": "35.5"}]}
        sec = {"id": "s1", "claim_id": "c1", "label": "C1", "kind": "question", "text": "Every dataset.", "experiments": [x], "links": {"x1": {"status": "contradicts", "why": "Ours is behind on 2 of 3.", "rule": "L3"}}}
        E = {"sections": [sec], "thesis": {}, "study": None}
        C = {"claims": [{"id": "c1", "label": "C1", "short": "C1", "text": "Every dataset.", "state": "confirmed"}]}
        items = {i["kind"]: i for i in todomod.build(E, C, {"items": []}, {"tasks": []}, {"findings": []}, {"summary": {}}, {"plans": []}, {"proposed": None}, [], {"snoozed": {}}, "2026-11-22")["items"]}
        self.assertEqual(items["differs"]["sentence"], "MCD, Covtype: the paper says 44.0, the file says 46.0.")
        self.assertEqual([(c["side"], c["v"]) for c in items["differs"]["cells"]], [("paper", "44.0"), ("file", 46.0)])
        self.assertIn("no result file holds it", items["untraced"]["sentence"])
        self.assertIn("35.5", items["untraced"]["sentence"])
        self.assertIn("bolds 30.0", items["bold"]["sentence"])
        self.assertIn("28.5", items["bold"]["sentence"])
        self.assertTrue(items["contradicts"]["sentence"].startswith("C1 says “Every dataset.”"))
        self.assertIn("Ours is behind on 2 of 3.", items["contradicts"]["sentence"])

    def test_findings_and_key_numbers_carry_a_pair(self):
        f = {"id": "main_appendix_mismatch/lr", "check": "main_appendix_mismatch", "title": "Main text and appendix differ", "message": "m", "details": {"main_value": "3e-4", "appendix_value": "1e-3"}}
        E = {"sections": [], "thesis": {}, "study": None}
        it = todomod.build(E, {"claims": []}, {"items": []}, {"tasks": []}, {"findings": [f]}, {"summary": {}}, {"plans": []}, {"proposed": None}, [], {"snoozed": {}}, "2026-11-22")["items"][0]
        self.assertEqual(it["sentence"], "The main text says 3e-4; the appendix says 1e-3.")
        self.assertEqual((it["pair"]["left"], it["pair"]["right"]), (["Main text", "3e-4"], ["Appendix", "1e-3"]))
        nums = {"counts": {}, "groups": [{"label": "H1", "numbers": [{"id": "n1", "state": "confirmed", "status": "mismatch", "label": "AUC", "why": "The report says 0.91; the file holds 0.88.", "file": "results/a.csv", "quoted": {"text": "0.91"}, "found": "0.88"}]}]}
        it = todomod.build(E, {"claims": []}, {"items": []}, {"tasks": []}, {"findings": []}, {"summary": {}}, {"plans": []}, {"proposed": None}, [], {"snoozed": {}}, "2026-11-22", numbers=nums)["items"][0]
        self.assertEqual(it["pair"], {"left": ["The report says", "0.91"], "right": ["The file holds", "0.88"], "file": "results/a.csv"})
        self.assertIn("0.91", it["sentence"])


class Coverage(unittest.TestCase):
    CLAIM = "MCD wins on every dataset."

    def exp(self, xid, ours, datasets, others=None, **kw):
        rows = [{"label": "ADWIN", "values": {d: 40.0 for d in datasets}}, {"label": "MCD", "values": dict(ours)}]
        return dict({"id": xid, "name": xid, "tally": {}, "problems": [], "grid": {"datasets": list(datasets), "rows": rows, "cols": list(datasets), "tuning": False},
                     "summary": {"ours_label": "MCD", "study": "method"}}, **kw)

    def run_rule(self, text, xs, study=None, state="confirmed"):
        E = {"sections": [{"id": "s1", "claim_id": "c3", "label": "C3", "kind": "claim", "text": text, "experiments": xs, "links": {}}] if xs is not None else [], "thesis": {}, "study": study}
        C = {"claims": [{"id": "c3", "label": "C3", "short": "C3", "text": text, "state": state}]}
        return [i for i in todomod.build(E, C, {"items": []}, {"tasks": []}, {"findings": []}, {"summary": {}}, {"plans": []}, {"proposed": None}, [], {"snoozed": {}}, "2026-11-22")["items"] if i["kind"] == "coverage"]

    def test_phrases_that_count(self):
        for text, phrase in (("Wins on every dataset.", "every dataset"), ("It wins on all 6 datasets we tried", "all 6 datasets"), ("on all six datasets", "all six datasets"),
                             ("on all of the 6 datasets", "all of the 6 datasets"), ("Consistently across the benchmarks.", "Consistently across the benchmarks"),
                             ("Consistently across the evaluated benchmarks.", "Consistently across the evaluated benchmarks"), ("Better than all evaluated benchmarks", "all evaluated benchmarks"),
                             ("on EACH benchmark", "EACH benchmark"), ("across all the datasets", "all the datasets"), ("across all data sets", "all data sets"), ("each task", "each task"),
                             ("on each of the datasets", "each of the datasets"), ("on every one of the datasets", "every one of the datasets"),
                             ("consistently outperforms baselines across datasets", "consistently outperforms baselines across datasets"),
                             ("모든 데이터셋에서 우수하다", "모든 데이터셋"), ("모든 데이터 세트에서", "모든 데이터 세트"), ("각 데이터셋에서", "각 데이터셋"), ("모든 dataset에서", "모든 dataset")):
            self.assertEqual(todomod.coverage_phrase(text), phrase, text)

    def test_phrases_that_do_not(self):
        for text in ("Wins on most datasets.", "Better on all metrics.", "Wins on some datasets", "Improves every metric", "all of the baselines", "every seed", "all baselines", "across datasets", "", None, "datasets differ",
                     "on all but one dataset",
                     # a negation just before: not a universal claim
                     "Ours does not win on every dataset", "Ours is not better on every dataset", "Ours isn't best on all datasets", "not best on all datasets", "never wins on every dataset",
                     # an exception just after: the exception is the dataset a rule would report
                     "Best on all datasets except Weather", "On all datasets but Weather, ours leads", "on all datasets other than Weather", "all datasets, apart from Weather", "every dataset excluding Weather",
                     "on all datasets save for Weather", "모든 데이터셋에서 우월하지 않다", "모든 데이터셋 제외", "Weather를 제외한 모든 데이터셋에서 우수하다", "Weather 빼고 모든 데이터셋에서 우수하다", "Weather 말고 각 데이터셋에서", "전체 데이터셋", "생각 데이터셋", "생각각 데이터셋",
                     # a qualifier names a subset that cannot be resolved here
                     "on all synthetic datasets", "all the UCI datasets", "all three image datasets", "all real-world datasets", "every public benchmark",
                     # a possessive is not a universal over tasks as datasets
                     "Each task's model is tuned", "each task’s budget"):
            self.assertIsNone(todomod.coverage_phrase(text), text)

    def test_fires_with_both_sides_and_counts_only(self):
        ds = ["A", "B", "C", "D", "E", "F"]
        x = self.exp("x1", {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0, "E": None, "F": None}, ds)
        (it,) = self.run_rule(self.CLAIM, [x])
        self.assertEqual((it["group"], it["needs_you"]), ("paper", False))
        self.assertEqual(it["sentence"], "C3 says “every dataset”; 2 of 6 have no run.")
        self.assertEqual(it["why"], "No run of the project's own method on: E, F.")
        self.assertEqual([c["col"] for c in it["cells"]], ["E", "F"])
        self.assertEqual(it["pair"]["right"], ["Datasets with a run", "4 of 6"])
        self.assertEqual(it["xs"], ["x1"])
        for w in ("wrong", "fail", "bad", "error"):
            self.assertNotIn(w, it["sentence"].lower())

    def test_count_runs_across_two_experiments_by_dataset_name(self):
        x1 = self.exp("x1", {"A": 1.0, "B": None, "C": None}, ["A", "B", "C"])
        x2 = self.exp("x2", {"b": 2.0, "D": None}, ["b", "D"])      # "b" is the same dataset as "B"
        (it,) = self.run_rule(self.CLAIM, [x1, x2])
        self.assertEqual(it["sentence"], "C3 says “every dataset”; 2 of 4 have no run.")
        self.assertEqual(it["why"], "No run of the project's own method on: C, D.")
        self.assertEqual(it["xs"], ["x1", "x2"])

    def test_silent_cases(self):
        full = self.exp("x1", {"A": 1.0, "B": 2.0}, ["A", "B"])
        gap = self.exp("x1", {"A": 1.0, "B": None}, ["A", "B"])
        self.assertEqual(self.run_rule(self.CLAIM, [full]), [])      # full coverage
        self.assertEqual(self.run_rule(self.CLAIM, []), [])      # no linked experiment
        self.assertEqual(self.run_rule(self.CLAIM, None), [])
        self.assertEqual(self.run_rule("It wins on most datasets.", [gap]), [])
        self.assertEqual(self.run_rule("It is better on all metrics.", [gap]), [])
        self.assertEqual(self.run_rule(self.CLAIM, [gap], state="rejected"), [])
        self.assertEqual(self.run_rule(self.CLAIM, [gap], study="benchmark"), [])      # a benchmark study has no "ours"
        tuned = self.exp("x1", {"A": 1.0, "B": None}, ["A", "B"])
        tuned["grid"]["tuning"] = True
        self.assertEqual(self.run_rule(self.CLAIM, [tuned]), [])      # a search over settings has no datasets to cover


class TrailByField(unittest.TestCase):
    def build(self, ev=None, mapdoc=None, cps=None):
        base = {"id": "e1", "kind": "commit", "repo": "code", "rev": "a" * 40, "short": "aaaaaaa", "time": "2026-11-20T10:00:00+09:00", "subject": "s", "files": [], "author": "Claude Smith", "coauthors": [], "agent_coauthor": False}
        base.update(ev or {})
        return trailmod.build([base], [], {}, {"claims": []}, {}, {}, mapdoc or {}, {"checkpoints": cps or []}, {}, [], {}, today="2026-11-22", exps=[], repos=[])["entries"]

    def test_agent_means_an_anthropic_address_not_a_name(self):
        self.assertEqual(self.build({"coauthors": ["Claude Sonnet"], "agent_coauthor": True})[0]["by"], {"kind": "agent", "name": None})
        self.assertEqual(self.build({"coauthors": ["Claudia"], "agent_coauthor": False})[0]["by"], {"kind": "person", "name": "Claude Smith"})
        self.assertEqual(self.build({"coauthors": ["Claude"], "agent_coauthor": False})[0]["by"], {"kind": "person", "name": "Claude Smith"})

    def test_you_only_when_the_request_knew(self):
        md = {"confirmed_at": "2026-11-21T09:00:00+09:00"}
        cp = [{"created_at": "2026-11-21T10:00:00+09:00", "note": None}]
        by = lambda es, title: next(e["by"] for e in es if e["title"] == title)
        es = self.build(mapdoc=md, cps=cp)
        self.assertIsNone(by(es, "Project map confirmed"))
        self.assertIsNone(by(es, "Marked everything as looked at"))
        es = self.build(mapdoc=dict(md, confirmed_by="you"), cps=[dict(cp[0], by="you")])
        self.assertEqual(by(es, "Project map confirmed"), {"kind": "you", "name": None})
        self.assertEqual(by(es, "Marked everything as looked at"), {"kind": "you", "name": None})


class NoCoauthorAddresses(unittest.TestCase):
    def test_no_address_leaves_the_engine(self):
        import json as _j
        import subprocess
        from lemmata.server import App
        d = tempfile.mkdtemp(prefix="lemmata-s36-co-")
        try:
            make_sample.build(d)
            env = dict(__import__("os").environ, GIT_AUTHOR_NAME="j", GIT_AUTHOR_EMAIL="j@x.invalid", GIT_COMMITTER_NAME="j", GIT_COMMITTER_EMAIL="j@x.invalid")
            (Path(d) / "code" / "note.txt").write_text("x\n")
            subprocess.run(["git", "-C", str(Path(d) / "code"), "add", "-A"], check=True, env=env, capture_output=True)
            subprocess.run(["git", "-C", str(Path(d) / "code"), "commit", "-qm", "work\n\nCo-Authored-By: Claude Sonnet <noreply@anthropic.com>\nCo-Authored-By: Pat <pat.secret@example.org>"], check=True, env=env, capture_output=True)
            eng = Engine(d)
            eng.scan()
            evs = _j.dumps(eng.events())
            self.assertNotIn("anthropic.com", evs)
            self.assertNotIn("pat.secret", evs)
            commits = [e for e in eng.events()["events"] if e.get("kind") == "commit" and e.get("subject") == "work"]
            self.assertTrue(commits and commits[0]["agent_coauthor"])
            snap = _j.dumps(App(eng).snapshot())
            self.assertNotIn("anthropic.com", snap)
            self.assertNotIn("pat.secret", snap)
            self.assertEqual([e["by"] for e in eng.trail()["entries"] if e["title"] == "work"], [{"kind": "agent", "name": None}])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class SampleCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="lemmata-s36-")
        make_sample.build(cls.dir)
        cls.eng = Engine(cls.dir)
        cls.eng.scan()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)


class SinceEngine(SampleCase):
    def test_per_person_record_and_no_write_on_read(self):
        a = self.eng.since("alice")
        self.assertTrue(a["first_visit"])
        self.assertTrue(self.eng.since("alice")["first_visit"])      # reading does not record a visit
        self.assertFalse((Path(self.dir) / ".lemmata" / "home_seen.json").exists())
        self.eng.since("alice", mark=True)
        self.assertFalse(self.eng.since("alice")["first_visit"])
        self.assertEqual(self.eng.since("alice")["items"], [])
        self.assertTrue(self.eng.since("bob")["first_visit"])      # another person has not looked
        self.assertTrue(self.eng.since(None)["first_visit"])      # nor the local user
        raw = (Path(self.dir) / ".lemmata" / "home_seen.json").read_text()
        self.assertNotIn("alice", raw.lower())

    def test_trail_entries_carry_by_only_when_recorded(self):
        T = self.eng.trail()
        self.assertTrue(T["entries"])
        for e in T["entries"]:
            self.assertIn("by", e)
            self.assertTrue(e["by"] is None or e["by"]["kind"] in ("you", "agent", "run", "lemmata", "person"))
        self.assertTrue(any(e["by"] for e in T["entries"] if e["kind"] in ("code", "paper")))      # commits name their author

    def test_todo_items_all_carry_needs_you(self):
        T = self.eng.todo("2026-11-22")
        self.assertTrue(all(isinstance(i["needs_you"], bool) for i in T["items"]))


class SinceLocalServer(SampleCase):
    def test_get_and_post(self):
        srv = bind(self.eng, port=18790)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port = srv.server_address[1]
        try:
            def call(method, path):
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
                c.request(method, path, body=b"{}" if method == "POST" else None, headers={"Host": "127.0.0.1:%d" % port, "Content-Type": "application/json"})
                r = c.getresponse()
                out = json.loads(r.read())
                c.close()
                return r.status, out
            s, d = call("GET", "/api/since")
            self.assertEqual((s, d["first_visit"], d["days"]), (200, True, 7))
            self.assertEqual(call("GET", "/api/since")[1]["first_visit"], True)
            s, d = call("POST", "/api/since")
            self.assertEqual((s, d["first_visit"]), (200, True))      # the answer is what they had not seen
            self.assertEqual(call("GET", "/api/since")[1]["first_visit"], False)
            s, d = call("GET", "/api/todo")
            self.assertEqual(s, 200)
            self.assertTrue(all("needs_you" in i for i in d["items"]))
        finally:
            srv.shutdown()
            srv.server_close()


try:
    from test_hub import HubBase
except Exception:      # pragma: no cover
    HubBase = None

if HubBase is not None:
    class SinceHub(HubBase):
        def test_hub_keeps_one_record_per_project(self):
            self.fake.state = "approved"
            if not self.hub.gh.stored():
                self.assertEqual(self.api("POST", "/api/hub/github/start")[0], 200)
                self.fake.approve()
                self.assertEqual(self.api("GET", "/api/hub/github/poll")[1]["state"], "ok")
            s, r = self.api("POST", "/api/hub/projects", {"code_repo": "alice/demo-code"})
            self.assertEqual(s, 201, r)
            pid = r["id"]
            self.assertEqual(self.api("POST", "/api/hub/projects/%s/sync" % pid)[0], 200)
            s, d = self.api("GET", "/p/%s/api/since" % pid)
            self.assertEqual((s, d["first_visit"], d["days"]), (200, True, 7), d)
            self.assertEqual(self.api("GET", "/p/%s/api/since" % pid)[1]["first_visit"], True)
            self.assertEqual(self.api("POST", "/p/%s/api/since" % pid)[0], 200)      # a bearer token (an agent, VS Code) reads but does not record a visit
            self.assertEqual(self.api("GET", "/p/%s/api/since" % pid)[1]["first_visit"], True)
            s, _, out = self.raw("POST", "/p/%s/api/since" % pid, b"{}", {"Cookie": "lemmata_session=" + self.token, "Content-Type": "application/json", "Origin": self.origin})      # a browser session does
            self.assertEqual(s, 200, out)
            self.assertEqual(self.api("GET", "/p/%s/api/since" % pid)[1]["first_visit"], False)
            s2, r2 = self.api("POST", "/api/hub/projects", {"code_repo": "alice/other"})
            if s2 == 201:      # a second project keeps its own record
                self.assertEqual(self.api("GET", "/p/%s/api/since" % r2["id"])[1]["first_visit"], True)
            seen = list((self.data / "projects" / pid).rglob("home_seen.json"))
            self.assertEqual(len(seen), 1)
            self.assertNotIn("alice", seen[0].read_text().lower())


if __name__ == "__main__":
    unittest.main()
