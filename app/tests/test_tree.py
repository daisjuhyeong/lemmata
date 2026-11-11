"""Research tree and core-message picker (S08).  PYTHONPATH=app/src python3 -m unittest app/tests/test_tree.py"""
import unittest

from lemmata.engine.claims import pick_core, sentences

ABSTRACT = ("Continuous learning from data streams is critical, e.g. in the internet era. However, data streams often do not conform "
            "to the same distribution over time, leading to concept drift. Existing methods have been limited to labelled data. "
            "In this paper, we propose MCD, a drift detection method based on contrastive learning. Experiments on 11 datasets show gains of 5.2%.")


class CoreTest(unittest.TestCase):
    def test_picks_the_aim_sentence_whole(self):
        s = pick_core(ABSTRACT)
        self.assertTrue(s.startswith("In this paper, we propose MCD"))
        self.assertTrue(s.endswith("."))

    def test_abbreviations_do_not_split(self):
        self.assertEqual(len(sentences(ABSTRACT)), 5)

    def test_falls_back_to_title_then_last_sentence(self):
        plain = "Streams drift over time. Models degrade when that happens."
        self.assertEqual(pick_core(plain, "A Study of Drift"), "A Study of Drift")
        self.assertEqual(pick_core(plain), "Models degrade when that happens.")


if __name__ == "__main__":
    unittest.main()


class NotationTest(unittest.TestCase):
    def test_symbols(self):
        from lemmata.engine.notation import symbols
        keys = lambda t, m=(): [k for k, _, _ in symbols(t, m)]
        self.assertEqual(keys(r"\mathcal{L}_{\text{rec}}(\theta) + \lambda \bm{x}_t"), [r"\mathcal{L}_{\mathrm{rec}}", r"\theta", r"\lambda", r"\mathbf{x}", "t"])
        self.assertEqual(keys(r"\frac{1}{\sqrt{n}} \sum_i \log p"), ["n", "i", "p"])
        self.assertEqual(keys(r"\Loss + F_{PA}", {r"\Loss": "x"}), [r"\Loss", r"F_{\mathrm{PA}}"])

    def test_same_meaning_and_code_tokens(self):
        from lemmata.engine.notation import _same, _tokens
        self.assertTrue(_same("segment length", "length of an anomaly segment"))
        self.assertFalse(_same("window size", "weight vector"))
        self.assertEqual(_tokens("lr"), ["learning", "rate"])
        self.assertEqual(_tokens("windowSize"), ["window", "size"])

    def test_detex_keeps_math(self):
        from lemmata.engine.claims import cut, detex
        self.assertEqual(detex(r"Loss \textbf{is} $\mathbf{x}~+ 1$ \cite{a}."), r"Loss is $\mathbf{x}~+ 1$ .")
        self.assertEqual(cut("abc $x+y$ def", 6), "abc…")


class ExperimentsTest(unittest.TestCase):
    def test_result_file_and_summary(self):
        from lemmata.engine.experiments import lower_better, parse_result, pick_ours, summarise
        t = parse_result("results/main.csv", b"method,seed,F1\nA,1,0.80\nA,2,0.84\nOurs,1,0.90\nOurs,2,0.92\n")
        self.assertEqual((t["cols"], [r["label"] for r in t["rows"]], t["seeds"]), (["F1"], ["A", "Ours"], True))
        self.assertAlmostEqual(t["rows"][0]["values"]["F1"], 0.82)
        self.assertEqual(t["rows"][0]["n"]["F1"], 2)
        self.assertEqual(pick_ours(t, []), ("Ours", "name"))
        s = summarise(t, "Ours", "F1", False)
        self.assertEqual((s["rank"], s["best"]["label"], round(s["gap"], 2)), (1, "A", 0.09))
        self.assertEqual(summarise(t, "Ours", "F1", True)["rank"], 2)
        self.assertTrue(lower_better("val_loss") and not lower_better("F1"))
        j = parse_result("r.json", b'{"A": {"acc": 0.5}, "B": {"acc": 0.7}}')
        self.assertEqual([r["label"] for r in j["rows"]], ["A", "B"])
        self.assertIsNone(parse_result("r.csv", b"just text\n"))

    def test_paper_table_is_checked_cell_by_cell(self):
        from lemmata.engine.experiments import align, num, parse_result
        self.assertEqual(num("91.2\\%")[:3], (91.2, None, True))
        self.assertEqual(num("0.91 ± 0.02")[:2], (0.91, 0.02))
        tab = parse_result("m.csv", b"method,acc,loss\nA,0.8127,0.30\nB,0.9049,0.21\n")
        cell = lambda t, bold=False: dict(tex=t, text=t, bold=bold, **dict(zip(("value", "std", "pct", "dec"), num(t) or (None, None, False, None))))
        grid = [[cell("Method"), cell("acc"), cell("loss")], [cell("A"), cell("81.3"), cell("0.30", True)], [cell("B"), cell("90.4"), cell("0.25")], [cell("C"), cell("77.0"), cell("0.21")]]
        g, tally, problems = align(grid, tab)
        self.assertEqual([c.get("status") for c in g[1]], [None, "match", "match"])            # 0.8127 -> 81.3 %
        self.assertEqual([c.get("status") for c in g[2]], [None, "rounding", "differs"])       # 90.49 printed as 90.4; 0.25 vs 0.21
        self.assertEqual([c.get("status") for c in g[3]], [None, "untraced", "loose"])         # no row C; 0.21 is B's value
        self.assertEqual(tally, {"match": 2, "rounding": 1, "differs": 1, "loose": 1, "untraced": 1})
        self.assertEqual(sorted(p["kind"] for p in problems), ["bold", "differs"])             # bold 0.30 is not the lowest loss
