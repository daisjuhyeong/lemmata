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
