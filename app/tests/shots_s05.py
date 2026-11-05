"""S05 screenshots of the hub Overleaf UI against the mock hub. Run: python3 app/tests/shots_s05.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mock_hub
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "screens"
PORT = 18771
mock_hub.serve(PORT)
B = "http://127.0.0.1:%d" % PORT
with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 1280, "height": 800})
    errs = []
    pg.on("console", lambda m: errs.append(m.text[:60] + " @ " + pg.url) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(B + "/")
    pg.fill("#code", "ABCD2345"); pg.click("#pair-go")
    pg.wait_for_selector("#gh-start"); pg.click("#gh-start"); pg.wait_for_selector("#new-project", timeout=20000)
    pg.wait_for_selector("#ol-save")
    pg.screenshot(path=str(OUT / "s05-hub-overleaf-card.png"))
    pg.fill("#ol-token", "olp_secret_test_token"); pg.click("#ol-save"); pg.wait_for_selector("#ol-remove")
    assert "olp_secret" not in pg.content()
    pg.screenshot(path=str(OUT / "s05-hub-overleaf-saved.png"))
    pg.click("#new-project"); pg.wait_for_selector("#repos li button")
    pg.click("#repos li button"); pg.fill("#ol-link", "https://www.overleaf.com/project/65a1b2c3d4e5f60718293a4b")
    pg.screenshot(path=str(OUT / "s05-new-project-overleaf.png"))
    pg.click("#create"); pg.wait_for_url("**/p/**", timeout=20000)
    pg.wait_for_selector("#paper-src"); pg.wait_for_timeout(800)
    pg.screenshot(path=str(OUT / "s05-topbar-overleaf.png"), clip={"x": 0, "y": 0, "width": 1280, "height": 60})
    print("topbar:", pg.inner_text("#topbar").replace("\n", " | "))
    assert pg.locator("#btn-upload").count() == 0 and pg.locator("#paper-src").count() == 1
    print("widths", pg.evaluate("[document.getElementById('topbar').scrollWidth, document.getElementById('paper-src').getBoundingClientRect().width, document.querySelector('#topbar .proj').getBoundingClientRect().width]"))
    pg.click("#btn-sync"); pg.wait_for_timeout(800)
    pg.goto(B + "/"); pg.wait_for_selector("#new-project")
    pg.click("#new-project"); pg.wait_for_selector("#repos li button")
    pg.click("#repos li button:nth-of-type(1) >> nth=1"); pg.click("button:has-text('Drop a zip')")
    pg.click("#create"); pg.wait_for_url("**/p/**", timeout=20000); pg.wait_for_selector("#paper-src"); pg.wait_for_timeout(500)
    pg.screenshot(path=str(OUT / "s05-topbar-zip.png"), clip={"x": 0, "y": 0, "width": 1280, "height": 60})
    print("zip topbar:", pg.inner_text("#topbar").replace("\n", " | "))
    pg.click("#paper-src"); pg.wait_for_selector(".modal")
    pg.screenshot(path=str(OUT / "s05-paper-menu-zip.png"))
    pg.click(".modal button:has-text('Connect Overleaf')"); pg.wait_for_selector("#ol-link")
    pg.fill("#ol-link", "https://www.overleaf.com/project/65a1b2c3d4e5f60718293a4b")
    pg.screenshot(path=str(OUT / "s05-connect-overleaf-modal.png"))
    pg.click(".modal button:has-text('Connect')"); pg.wait_for_selector("#paper-src.chip", timeout=10000); pg.wait_for_timeout(500)
    print("after connect:", pg.inner_text("#paper-src"))
    print("console errors:", errs)
    br.close()
