"""S36 design-system tests (stdlib unittest): WCAG contrast of the tokens in both themes, sand (--highlight) used only for "your turn",
no font size below 13px for information, no hex colour outside tokens.css.
Run: PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_s36*.py'"""
import re
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))
WEB = APP / "src" / "lemmata" / "web"

# Selectors that may use var(--highlight): the your-turn button and the dots of items waiting for the researcher.
HIGHLIGHT_ALLOWED = {
    ".btn.primary", ".btn.primary:hover", ".rdot.d-highlight", ".chip.proposed::before",
    ".rxt-li.att > .rxt-row .rxt-dot",
    ".hm-dot", ".sd-dot",      # S36 phase 2: the your-turn dot of a Needs you row, and Home's dot in the sidebar
}
# Glyph-only text that carries no information (carets, +/- marks, one-character state glyphs) may stay below 13px.
SIZE_EXCEPTIONS = {".rx-m-g", ".rxt-caret", ".rh .caret", ".rx-chk .cg"}


def _strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rules(css):
    """(selector, body) for every innermost rule; @media wrappers are skipped, selector lists are returned whole."""
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", _strip_comments(css))]


def _theme(css):
    css = _strip_comments(css)
    light, dark = {}, {}
    for sel, body in _rules(css):
        target = light if sel == ":root" else dark if sel == ':root[data-theme="dark"]' else None
        if target is not None:
            target.update({k: v.strip() for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body)})
    merged = dict(light)
    merged.update(dark)
    return {"light": light, "dark": merged}


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hexv):
    h = hexv.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class DesignSystemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.themes = _theme((WEB / "tokens.css").read_text(encoding="utf-8"))

    def test_text_tokens_are_readable_on_every_surface(self):
        for name, t in self.themes.items():
            for fg in ("--text", "--text-secondary", "--muted", "--accent-dark"):
                for bg in ("--bg", "--bg-2", "--surface", "--surface-hover"):
                    r = _contrast(t[fg], t[bg])
                    self.assertGreaterEqual(r, 4.5, "%s: %s on %s is %.2f" % (name, fg, bg, r))

    def test_text_on_sand(self):
        for name, t in self.themes.items():
            r = _contrast(t["--on-highlight"], t["--highlight"])
            self.assertGreaterEqual(r, 4.5, "%s: --on-highlight on --highlight is %.2f" % (name, r))

    def test_state_colours_and_edge_are_visible_on_the_page(self):
        for name, t in self.themes.items():
            for fg in ("--success", "--warning", "--error", "--highlight-edge"):
                r = _contrast(t[fg], t["--bg"])
                self.assertGreaterEqual(r, 3, "%s: %s on --bg is %.2f" % (name, fg, r))

    def test_warning_and_sand_differ_in_lightness(self):
        for name, t in self.themes.items():
            d = abs(_lum(t["--warning"]) - _lum(t["--highlight"]))
            self.assertGreaterEqual(d, 0.15, "%s: luminance gap %.3f" % (name, d))

    def test_sand_only_for_your_turn(self):
        css = (WEB / "app.css").read_text(encoding="utf-8")
        found = set()
        for sel, body in _rules(css):
            if re.search(r"var\(--highlight\)", body):  # the closing paren keeps --highlight-edge out
                found.update(s.strip() for s in sel.split(","))
        self.assertTrue(found, "no use of --highlight found; the parser is broken")
        self.assertEqual(found - HIGHLIGHT_ALLOWED, set(), "var(--highlight) outside the allow-list")
        for sel, body in _rules(css):
            if sel in HIGHLIGHT_ALLOWED and "var(--highlight)" in body:
                self.assertIn("var(--highlight-edge)", body, sel)

    def test_no_text_below_13px(self):
        css = (WEB / "app.css").read_text(encoding="utf-8")
        bad = []
        for sel, body in _rules(css):
            if sel in SIZE_EXCEPTIONS or sel.startswith(":root"):
                continue
            for decl in re.findall(r"font(?:-size)?\s*:\s*([^;]+)", body):
                for v in re.findall(r"(?<![\d.\w-])(\d+(?:\.\d+)?)px", decl):
                    if float(v) < 13:
                        bad.append("%s { %s }" % (sel, decl.strip()))
        self.assertEqual(bad, [])
        root = re.search(r":root\s*\{[^}]*\}", css).group(0)
        for name in ("--fs-11", "--fs-12"):
            self.assertIn("%s:13px" % name, root)

    def test_no_hex_colours_outside_tokens(self):
        for f in ("app.css", "app.js", "research.js"):
            hits = re.findall(r"#[0-9a-fA-F]{3,8}\b", (WEB / f).read_text(encoding="utf-8"))
            # '#' ids such as #status are not hex colours unless all characters are hex digits; none of ours are
            self.assertEqual(hits, [], f)


class PageHeadsTest(unittest.TestCase):
    """Phase 2 (acceptance lines 10, 11, 15, 16, 17): strings and structure that the browser cannot be asked about here."""
    @classmethod
    def setUpClass(cls):
        cls.js = (WEB / "research.js").read_text(encoding="utf-8")
        cls.app = (WEB / "app.js").read_text(encoding="utf-8")
        cls.css = (WEB / "app.css").read_text(encoding="utf-8")

    def test_each_page_starts_with_its_question(self):
        qs = re.search(r"const RX_Q = \{([^}]*)\}", self.js).group(1)
        for key, q in (("digest", "What needs you today?"), ("experiments", "Is each claim backed?"), ("setup", "What was used?"),
                       ("review", "What disagrees?"), ("history", "What did you do, and when?")):
            self.assertIn("%s: '%s'" % (key, q), qs)
        for page, use in (("pageDigest", "RX_Q.digest"), ("pageExperiments", "RX_Q.experiments"), ("pageSetup", "RX_Q.setup"), ("pageReview", "RX_Q.review"), ("pageTrail", "RX_Q.history")):
            body = self.js[self.js.index("function %s(" % page):]
            body = body[:body.index("\n}\n")]
            self.assertIn("rxPageHead(" + use, body, page)

    def test_home_tiles_are_gone(self):
        self.assertNotIn("hm-cards", self.js + self.css + self.app)
        self.assertNotIn("hm-card", self.js + self.css)
        body = self.js[self.js.index("function pageDigest("):]
        body = body[:body.index("\n}\n")]
        for section in ("'Needs you'", "'Since you last looked'", "'This month'"):
            self.assertIn(section, body)
        self.assertIn("rxTodoList(0)", body)      # the to-do list stays reachable from the answer line
        self.assertIn("All to-do (", body)

    def test_review_has_four_sections_in_order(self):
        body = self.js[self.js.index("function pageReview("):]
        body = body[:body.index("\n}\n")]
        order = [body.index(x) for x in ("'Mismatches'", "'Stale'", "'To confirm'", "'Checked and fine'")]
        self.assertEqual(order, sorted(order))
        self.assertIn("'no run'", self.js)      # a missing cell is said in words
        self.assertIn("open: open ? '' : null", body)      # closed by default

    def test_sidebar_dot_is_only_on_home(self):
        left = self.app[self.app.index("side.append(h('div', { class: 'sd-g sd-main' }"):]
        left = left[:left.index("\n")]
        self.assertIn("k === 'digest' && RX.todo ? h('i', { class: 'sd-dot'", left)
        self.assertEqual(self.app.count("sd-dot"), 1)
        self.assertRegex(self.css, r"\.sd-n \{[^}]*color:var\(--text-secondary\)")

    def test_tree_frame_scrolls_on_its_own_below_1100px(self):
        self.assertRegex(self.css, r"@media \(max-width:1100px\) \{ \.rx-treeframe \{ overflow-x:auto;")
        self.assertIn("rx-treeframe", self.js)

    def test_needs_you_rows_use_the_your_turn_dot_and_one_nowrap_line(self):
        self.assertRegex(self.css, r"\.hm-line \{[^}]*white-space:nowrap")
        self.assertRegex(self.css, r"\.hm-line \{[^}]*text-overflow:ellipsis")
        self.assertIn("h('i', { class: 'hm-dot', 'aria-hidden': 'true' })", self.js)
        self.assertIn("'your turn'", self.js)

    def test_vscode_tab_keeps_its_one_word_titles(self):
        head = self.js[self.js.index("function rxPageHead("):]
        head = head[:head.index("\n}\n")]
        self.assertIn("if (EMBED) return h('h1', { class: 'ptitle' }, RX_SHORT[", head)
        self.assertIn("setup: 'Setup'", self.js)
        self.assertNotIn("html.embed .pghead", self.css)      # vscode.css sets the tab's title size; nothing here may outrank it
        self.assertNotIn("html.embed h1.ptitle.pq", self.css)

    def test_thesis_draws_the_tree_without_a_paper(self):
        body = self.js[self.js.index("function pageExperiments("):]
        body = body[:body.index("\n}\n")]
        line = next(l for l in body.split("\n") if "rxThesisTree()" in l)
        self.assertNotIn("has_paper", line)

    def test_thesis_and_review_count_mismatches_from_one_list(self):
        self.assertIn("const rxMismatches = ", self.js)
        self.assertGreaterEqual(self.js.count("rxMismatches()"), 2)
        ans = self.js[self.js.index("function rxThesisAnswer("):]
        self.assertIn("rxMismatches()", ans[:ans.index("\n}\n")])
        self.assertNotIn("st.refuted", ans[:ans.index("\n}\n")])

    def test_numbers_in_a_mismatch_open_their_file(self):
        body = self.js[self.js.index("async function rxOpenNumber("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("mine.length === 1", body)      # one file: straight to the file
        self.assertIn("openTab('node', one.node_id)", body)
        self.assertIn("rxGoto('setup'", body)      # several: the trace
        sent = self.js[self.js.index("function rxRvSentence("):]
        self.assertIn("rxOpenNumber(cell.x, cell.row, cell.col)", sent[:sent.index("\n}\n")])

    def test_decision_commits_are_not_sand(self):
        self.assertNotIn("plainChip('◆', 'Decision', 'proposed')", self.js)


if __name__ == "__main__":
    unittest.main()
