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


if __name__ == "__main__":
    unittest.main()
