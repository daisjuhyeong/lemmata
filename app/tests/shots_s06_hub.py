"""S06 hub screenshots against the mock hub. Run: python3 app/tests/shots_s06_hub.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mock_hub
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "screens"
PORT = 18772
mock_hub.serve(PORT)
B = "http://127.0.0.1:%d" % PORT
with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 1100, "height": 760})
    errs = []
    pg.on("console", lambda m: errs.append(m.text[:80] + " @ " + pg.url) if m.type == "error" and "404" not in m.text else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(B + "/")
    pg.screenshot(path=str(OUT / "s06-hub-pair.png"))
    pg.fill("#code", "ABCD2345"); pg.click("#pair-go")
    pg.wait_for_selector("#gh-start"); pg.screenshot(path=str(OUT / "s06-hub-signin.png"))
    pg.click("#gh-start"); pg.wait_for_selector("#new-project", timeout=20000)
    assert "verleaf" not in pg.inner_text("body")
    pg.screenshot(path=str(OUT / "s06-hub-empty.png"))
    # project 1: paper as a folder in the code repo
    pg.click("#new-project"); pg.wait_for_selector("#repos li button")
    pg.click("#repos li button >> nth=0")
    pg.screenshot(path=str(OUT / "s06-hub-new-repo.png"), full_page=True)
    pg.click("button:has-text('A folder in the code repo')")
    pg.screenshot(path=str(OUT / "s06-hub-new-folder.png"), full_page=True)
    pg.click("button:has-text('Upload a zip instead')")
    pg.screenshot(path=str(OUT / "s06-hub-new-zip.png"), full_page=True)
    pg.click("button:has-text('A folder in the code repo')"); pg.fill("#paper-subdir", "missing"); pg.click("#create")
    pg.wait_for_selector("#back"); pg.screenshot(path=str(OUT / "s06-hub-new-error.png"))
    pg.click("#back"); pg.fill("#paper-subdir", "paper"); pg.click("#create"); pg.wait_for_url("**/p/**", timeout=20000)
    # project 2: own paper repo
    pg.goto(B + "/"); pg.wait_for_selector("#new-project"); pg.click("#new-project"); pg.wait_for_selector("#repos li button")
    pg.click("#repos li button >> nth=1"); pg.wait_for_selector("#paper-repos li button")
    pg.click("#paper-repos li button >> nth=3")
    pg.click("#create"); pg.wait_for_url("**/p/**", timeout=20000)
    pg.goto(B + "/"); pg.wait_for_selector(".proj >> nth=1")
    pg.screenshot(path=str(OUT / "s06-hub-projects.png"))
    print(pg.inner_text("#plist"))
    print("console errors:", errs)
    br.close()
