"""S06 hub-mode UI against a real hub + fake GitHub (loopback). Run: PYTHONPATH=app/src python3 app/tests/shots_s06_hubmode.py"""
import json, sys, tempfile, threading, secrets
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fake_github import CLIENT_ID, FakeGitHub
from lemmata.hub import projects
from lemmata.hub.routes import Hub, make_hub_server
from test_hub import CODE, TEX1
from playwright.sync_api import sync_playwright
import http.client

projects.ALLOWED_PROTOCOLS = ["http", "https"]
OUT = Path(__file__).resolve().parent.parent / "docs" / "screens"
TEX2 = TEX1.replace("91.2", "93.4")
gh = FakeGitHub(); tag = secrets.token_hex(3)
own, mono = "alice/paper-" + tag, "alice/mono-" + tag
gh.add_repo("alice/demo-code", CODE); gh.add_repo(own, {"main.tex": TEX1, "refs.bib": ""}); gh.add_repo(mono, dict(CODE, **{"paper/main.tex": TEX1, "paper/refs.bib": ""}))
tmp = tempfile.TemporaryDirectory(); hub = Hub(Path(tmp.name) / "Lemmata", port=0, detect_tailscale=False)
hub.cfg.update(github_client_id=CLIENT_ID, github_api=gh.url, github_web=gh.url)
srv = make_hub_server(hub, host="127.0.0.1", port=0); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d" % port

def api(method, path, body=None, token=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    h = {"Host": "127.0.0.1:%d" % port, "Content-Type": "application/json"}
    if token: h["Authorization"] = "Bearer " + token
    c.request(method, path, json.dumps(body).encode() if body is not None else None, h)
    r = c.getresponse(); out = r.read(); c.close(); return r.status, json.loads(out or b"{}")

with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
    errs = []
    pg.on("response", lambda r: print("HTTP", r.status, r.url) if r.status >= 400 else None)
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(B + "/")
    code = hub.auth.new_code()
    pg.fill("#code", code); pg.click("#pair-go")
    gh.approve(); pg.wait_for_selector("#gh-start"); pg.click("#gh-start"); pg.wait_for_selector("#new-project", timeout=20000)
    tok = None
    # create the project through the API with the browser's cookie
    r = ctx.request.post(B + "/api/hub/projects", data={"code_repo": mono, "paper_repo": own}, headers={"Origin": B})
    assert r.status == 201, r.text(); pid = r.json()["id"]
    ctx.request.post(B + "/p/%s/api/checkpoints" % pid, data={"note": "start"}, headers={"Origin": B})
    pg.goto(B + "/p/%s/" % pid); pg.wait_for_timeout(2500); pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    print("status bar:", pg.inner_text("#status").replace("\n", " | "))
    pg.screenshot(path=str(OUT / "s06-hubmode-github.png"))
    pg.click("#rb-menu"); pg.wait_for_selector("#menu"); pg.screenshot(path=str(OUT / "s06-hubmode-menu.png"))
    pg.click("text=Connect paper repo…"); pg.wait_for_selector(".modal")
    pg.fill(".modal input >> nth=0", "https://github.com/" + mono); pg.fill(".modal input >> nth=1", "paper")
    pg.screenshot(path=str(OUT / "s06-hubmode-connect.png"))
    pg.click(".modal button:has-text('Connect')"); pg.wait_for_timeout(3500)
    print("after connect:", pg.inner_text("#status").replace("\n", " | "))
    pg.screenshot(path=str(OUT / "s06-hubmode-folder.png"))
    # bad repo error
    pg.click("#rb-menu"); pg.click("text=Connect paper repo…"); pg.fill(".modal input >> nth=0", "nobody/nothing"); pg.click(".modal button:has-text('Connect')"); pg.wait_for_timeout(1500)
    print("error text:", pg.inner_text(".modal .warn-note")); pg.screenshot(path=str(OUT / "s06-hubmode-connect-error.png")); pg.keyboard.press("Escape")
    # a commit in the paper folder, then Sync now
    gh.commit(mono, {"paper/main.tex": TEX2}, "paper: new accuracy")
    pg.click("#status button:has-text('Sync now')"); pg.wait_for_timeout(5000)
    pg.click(".navrow:has-text('Changes')"); pg.wait_for_timeout(800)
    print("cards:", pg.locator("[data-card]").count(), "| status:", pg.inner_text("#status").replace("\n", " | "))
    pg.screenshot(path=str(OUT / "s06-hubmode-synced.png"))
    print("console errors:", errs)
    br.close()
srv.shutdown(); gh.close()
