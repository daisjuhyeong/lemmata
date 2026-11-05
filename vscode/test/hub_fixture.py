"""Integration fixture for the VS Code extension tests (S05).

Starts a fake GitHub (app/tests/fake_github.py) and a real Lemmata hub HTTP server (lemmata.hub.routes, the code behind
`lemmata hub serve`), builds the synthetic sample (lemmata.samples.make_sample), pushes the sample's code repo to the fake
GitHub, creates a hub project from it, uploads the sample's paper as zips, and sets the checkpoint at the sample's CP1.
The Bearer token comes from the real CLI: `lemmata hub token --device "VS Code"`.

Prints one JSON line (url, token, pid, paths) and then runs until stdin closes.
    python3 vscode/test/hub_fixture.py <workdir>
"""
import http.client
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "app"
sys.path.insert(0, str(APP / "src"))
sys.path.insert(0, str(APP / "tests"))
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

from fake_github import CLIENT_ID, FakeGitHub  # noqa: E402
from lemmata.hub import projects  # noqa: E402
from lemmata.hub.routes import Hub, make_hub_server  # noqa: E402
from lemmata.samples.make_sample import build  # noqa: E402

projects.ALLOWED_PROTOCOLS = ["http", "https"]  # test only: the fake GitHub speaks plain http on loopback


def sh(cwd, *args):
    return subprocess.run(args, cwd=str(cwd), check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()


def zip_of(repo, rev):
    raw = subprocess.run(["git", "archive", "--format=zip", rev], cwd=str(repo), check=True, capture_output=True).stdout
    return raw


def main(work):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    data = work / "Lemmata"
    sample = work / "sample"
    build(sample)
    cp1 = sh(sample / "code", "git", "rev-parse", "cp1")

    # token from the real CLI, before the server starts
    env = dict(os.environ, PYTHONPATH=str(APP / "src"))
    out = subprocess.run([sys.executable, "-m", "lemmata", "hub", "token", "--data", str(data), "--device", "VS Code", "--host", "127.0.0.1"],
                         env=env, check=True, capture_output=True, text=True).stdout
    token = re.search(r"token \(shown once\): (\S+)", out).group(1)

    fake = FakeGitHub()
    fake.add_repo("alice/demo-code", {"README.md": "seed\n"}, description="sample code")
    bare = fake.root / "git" / "alice" / "demo-code.git"
    sh(sample / "code", "git", "push", "-q", "--force", str(bare), "HEAD:refs/heads/main")

    hub = Hub(data, port=0, detect_tailscale=False)
    hub.cfg.update(github_client_id=CLIENT_ID, github_api=fake.url, github_web=fake.url)
    srv = make_hub_server(hub, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def call(method, path, body=None, ctype="application/json", raw=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
        h = {"Host": "127.0.0.1:%d" % port, "Authorization": "Bearer " + token}
        data_ = raw if raw is not None else (json.dumps(body if body is not None else {}).encode() if method in ("POST", "PATCH") else None)
        if data_ is not None:
            h["Content-Type"] = ctype
        c.request(method, path, body=data_, headers=h)
        r = c.getresponse()
        txt = r.read()
        c.close()
        if r.status >= 300:
            raise SystemExit("fixture: %s %s -> %d %s" % (method, path, r.status, txt[:300]))
        return json.loads(txt)

    call("POST", "/api/hub/github/start")
    fake.approve()
    assert call("GET", "/api/hub/github/poll")["state"] == "ok"
    created = call("POST", "/api/hub/projects", {"code_repo": "alice/demo-code", "branch": "main"})
    pid = (created.get("project") or created)["id"]
    call("POST", "/api/hub/projects/%s/paper" % pid, ctype="application/zip", raw=zip_of(sample / "paper", "cp1"))
    call("POST", "/p/%s/api/checkpoints" % pid, {"note": "CP1 from the sample", "at": {"code": cp1}})
    call("POST", "/api/hub/projects/%s/paper" % pid, ctype="application/zip", raw=zip_of(sample / "paper", "HEAD"))
    # Pretend the paper is an Overleaf project (matching only; no fetch happens in these tests).
    meta_path = data / "projects" / pid / "project.json"
    meta = json.loads(meta_path.read_text())
    meta["paper_source"] = {"kind": "overleaf", "project_id": "65a1b2c3d4e5f60718293a4b"}
    meta_path.write_text(json.dumps(meta, indent=1) + "\n")

    print(json.dumps({"url": "http://127.0.0.1:%d" % port, "token": token, "pid": pid, "sample": str(sample), "cp1": cp1,
                      "overleaf_id": "65a1b2c3d4e5f60718293a4b", "data": str(data)}), flush=True)
    try:
        sys.stdin.read()
    finally:
        srv.shutdown()
        fake.close()


if __name__ == "__main__":
    main(sys.argv[1])
