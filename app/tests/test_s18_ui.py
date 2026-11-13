"""S18 UI tests (stdlib unittest): colours live only in tokens.css, fonts are bundled with their licences, the launcher copy of the tokens
matches, and the one-file export carries the tokens and the fonts. Run: PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_s18*.py'"""
import re
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))
WEB = APP / "src" / "lemmata" / "web"
LAUNCHER = APP.parent / "desktop" / "launcher"
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")


class UiTokensTest(unittest.TestCase):
    def test_colours_only_in_tokens(self):
        files = [WEB / f for f in ("app.css", "app.js", "research.js", "index.html", "fonts.css")] + list((WEB / "hub").glob("*")) + \
                [LAUNCHER / f for f in ("launcher.css", "launcher.js", "index.html", "fonts.css")]
        for f in files:
            hits = [m.group(0) for m in COLOUR.finditer(f.read_text(encoding="utf-8"))]
            self.assertEqual(hits, [], "%s has colour values outside tokens.css" % f)

    def test_tokens_define_the_dais_palette(self):
        css = (WEB / "tokens.css").read_text(encoding="utf-8")
        for name, val in (("--bg", "#fafcfb"), ("--accent", "#819A91"), ("--accent-dark", "#50645b"), ("--highlight", "#dac88e"), ("--error", "#B87474")):
            self.assertIn("%s: %s;" % (name, val), css)

    def test_launcher_copy_matches(self):
        for f in ("tokens.css", "fonts.css"):
            self.assertEqual((WEB / f).read_bytes(), (LAUNCHER / f).read_bytes(), f)
        for f in (WEB / "fonts").iterdir():
            if f.is_file() and not f.name.startswith("."):
                self.assertEqual(f.read_bytes(), (LAUNCHER / "fonts" / f.name).read_bytes(), f.name)

    def test_fonts_are_bundled_with_licences(self):
        names = {p.name for p in (WEB / "fonts").iterdir()}
        for n in ("SourceSerif4-Bold.woff2", "SourceSerif4-Italic.woff2", "SourceSerif4-Regular.woff2", "SourceSans3-Variable.woff2", "OFL-SourceSerif4.txt", "OFL-SourceSans3.txt"):
            self.assertIn(n, names)
        for t in ("OFL-SourceSerif4.txt", "OFL-SourceSans3.txt"):
            self.assertIn("SIL Open Font License", (WEB / "fonts" / t).read_text(encoding="utf-8"))
        css = (WEB / "fonts.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"https?://")
        for ref in re.findall(r"url\((fonts/[^)]+)\)", css):
            self.assertTrue((WEB / ref).is_file(), ref)

    def test_pages_link_tokens_before_styles(self):
        for page in (WEB / "index.html", WEB / "hub" / "index.html", LAUNCHER / "index.html"):
            html = page.read_text(encoding="utf-8")
            self.assertLess(html.index("tokens.css"), html.index("fonts.css"), page)
            self.assertNotRegex(html, r"(?:href|src)=\"https?://", page)

    def test_no_sidebar_or_min_width_in_the_app(self):
        js = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("id: 'ribbon'", js)
        self.assertNotIn("id: 'left'", js)
        # S23 (founder, chat 2026-11-13 14:28 KST): Setup is a top-level page of its own, beside Claims and Experiments
        self.assertIn("const NAV = [['claims', 'Claims'], ['experiments', 'Experiments'], ['setup', 'Setup'], ['digest', 'Digest'], ['review', 'Review']]", js)
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("1024", html)


    def test_export_carries_tokens_and_fonts(self):
        """The one-file export works offline: tokens and all four fonts are inside it, nothing points at a file or a site."""
        from lemmata.fixture_engine import FixtureEngine
        from lemmata.server import App
        html, _name = App(FixtureEngine("")).export_html()
        self.assertIn("--bg: #fafcfb;", html)
        self.assertIn("--accent: #819A91;", html)
        self.assertEqual(html.count("url(data:font/woff2;base64,"), 4)
        self.assertNotIn("url(fonts/", html)
        self.assertNotRegex(html, r'<script[^>]+src=|<link[^>]+href="(?!data:)')
        self.assertNotIn('href="tokens.css"', html)
        self.assertNotIn('href="fonts.css"', html)

    def test_start_page_is_band_sentence_rows(self):
        html = (WEB / "hub" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="bsub"', html)
        js = (WEB / "hub" / "hub.js").read_text(encoding="utf-8")
        land = js[js.index("function viewLanding()"):js.index("function viewWelcome()")]
        self.assertLess(land.index("howSteps()"), land.index("signin,"), "the steps come before the one sign-in button")
        self.assertEqual(land.count("signInCard("), 1)


if __name__ == "__main__":
    unittest.main()
