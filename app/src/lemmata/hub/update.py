"""Self-update for the hub on the Mac mini.

A second LaunchAgent (ai.lemmata.hub.update) runs `lemmata hub update` every few minutes. It keeps a checkout of its
own (<data>/deploy/lemmata, separate from the folder people and agents work in), follows one branch of the GitHub repo,
and when that branch moves forward: fast-forwards, checks that the new code starts, restarts the hub, checks that it
answers, and rolls back if it does not. Each run that changed something is written to <data>/hub/update.log and
update.json, and posted to Slack if a webhook is configured.

It only ever fast-forwards from `origin`; it never pushes and never touches the working checkout.
"""
from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import launchd
from .config import Config, DataDir, write_private

LABEL = "ai.lemmata.hub.update"
GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}


def deploy_dir(data):
    return data.root / "deploy" / "lemmata"


def base_python():
    return getattr(sys, "_base_executable", None) or sys.executable


def _git(cwd, *args, timeout=120):
    env = dict(os.environ)
    env.update(GIT_ENV)
    env["PATH"] = launchd.PATH_ENV + ":" + env.get("PATH", "")
    return subprocess.run(["git"] + list(args), cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)


def _sha(cwd, rev="HEAD"):
    r = _git(cwd, "rev-parse", rev)
    return r.stdout.strip() if r.returncode == 0 else None


def _log(data, line):
    p = data.hub / "update.log"
    with open(p, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S%z"), line))


def state(data):
    try:
        return json.loads((data.hub / "update.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _notify(cfg, text):
    url = cfg.load().get("update_webhook")
    if not url:
        return
    try:
        req = urllib.request.Request(url, data=json.dumps({"text": text}).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": "lemmata-hub"})
        urllib.request.urlopen(req, timeout=15).read(100)
    except Exception:
        pass   # reporting must never break an update


def _env_for(dep):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(dep / "app" / "src")
    env["PATH"] = launchd.PATH_ENV + ":" + env.get("PATH", "")
    return env


def smoke(dep):
    """Does the code in the deploy checkout import, and does a hub on a throwaway folder start and answer? -> (ok, detail)"""
    code = (
        "import json, tempfile, threading, urllib.request\n"
        "import lemmata.engine.api, lemmata.mcp, lemmata.server\n"
        "from lemmata.hub.routes import Hub, make_hub_server\n"
        "from pathlib import Path\n"
        "t = tempfile.TemporaryDirectory()\n"
        "hub = Hub(Path(t.name) / 'L', port=0, detect_tailscale=False)\n"
        "srv = make_hub_server(hub, host='127.0.0.1', port=0)\n"
        "threading.Thread(target=srv.serve_forever, daemon=True).start()\n"
        "u = 'http://127.0.0.1:%d' % srv.server_address[1]\n"
        "assert json.loads(urllib.request.urlopen(u + '/api/hub/status', timeout=10).read())['ok']\n"
        "assert b'<html' in urllib.request.urlopen(u + '/', timeout=10).read().lower()\n"
        "srv.shutdown(); print('smoke ok')\n")
    env = _env_for(dep)
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    try:
        r = subprocess.run([base_python(), "-c", code], capture_output=True, text=True, timeout=90, env=env, cwd=str(dep))
    except subprocess.TimeoutExpired:
        return False, "the new code did not start within 90 seconds"
    return r.returncode == 0, (r.stderr or r.stdout).strip()[-600:]


def healthy(port, wait=45):
    end = time.time() + wait
    while time.time() < end:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/api/hub/status" % port, timeout=3) as r:
                if json.loads(r.read()).get("ok"):
                    return True
        except Exception:
            time.sleep(1.5)
    return False


def restart_hub():
    if sys.platform != "darwin":
        return False
    r = launchd._lc("kickstart", "-k", "gui/%d/%s" % (os.getuid(), launchd.LABEL))
    return r.returncode == 0


def run(data, cfg, force=False, restart=restart_hub, check=healthy, out=print):
    """One update pass. -> "none" | "updated" | "failed" | "rolled_back" | "not_set_up" """
    c = cfg.load()
    dep = deploy_dir(data)
    branch = c.get("update_branch")
    if not branch or not (dep / ".git").exists():
        out("lemmata hub: self-update is not set up. Run `lemmata hub autoupdate install`.")
        return "not_set_up"
    lock = data.hub / "update.lock"
    try:
        if lock.exists() and time.time() - lock.stat().st_mtime < 900:
            return "none"
        lock.write_text(str(os.getpid()))
    except OSError:
        return "none"
    try:
        f = _git(dep, "fetch", "--quiet", "origin", branch)
        if f.returncode != 0:
            _log(data, "fetch failed: %s" % f.stderr.strip()[-200:])
            return "failed"
        old, new = _sha(dep), _sha(dep, "FETCH_HEAD")
        if not new or (old == new and not force):
            return "none"
        subjects = [s for s in _git(dep, "log", "--format=%s", "%s..%s" % (old, new)).stdout.splitlines() if s][:8]
        rec = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "branch": branch, "from": old, "to": new, "subjects": subjects}

        def finish(result, detail=""):
            rec.update(result=result, detail=detail, running=_sha(dep))
            write_private(data.hub / "update.json", json.dumps(rec, indent=1) + "\n")
            _log(data, "%s %s -> %s%s" % (result, (old or "")[:7], new[:7], " | " + detail.replace("\n", " ")[:300] if detail else ""))
            head = {"updated": "Lemmata updated", "failed": "Lemmata update FAILED (still running the old version)",
                    "rolled_back": "Lemmata update ROLLED BACK (the new version did not come up)"}[result]
            _notify(cfg, "*%s* on `%s`: `%s` → `%s`\n%s%s" % (head, branch, (old or "")[:7], new[:7], "\n".join("• " + s for s in subjects),
                                                           "\n```%s```" % detail[-500:] if detail and result != "updated" else ""))
            hook = c.get("update_on_failure")
            if result != "updated" and hook:
                try:
                    env = dict(os.environ, LEMMATA_UPDATE_LOG=str(data.hub / "update.log"), LEMMATA_UPDATE_RESULT=result,
                               PATH=launchd.PATH_ENV + ":" + os.environ.get("PATH", ""))
                    subprocess.Popen(hook, shell=True, env=env, cwd=str(Path.home()), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except OSError:
                    pass
            out("lemmata hub: %s (%s -> %s)" % (result, (old or "")[:7], new[:7]))
            return result

        if old != new:
            m = _git(dep, "merge", "--ff-only", "FETCH_HEAD")
            if m.returncode != 0:
                return finish("failed", "The branch did not move straight forward (history was rewritten?). Nothing was changed.\n" + m.stderr.strip()[-200:])
        ok, detail = smoke(dep)
        if not ok:
            _git(dep, "reset", "--hard", old)
            return finish("failed", detail)
        if not restart():
            return finish("failed", "launchctl could not restart %s. Run `lemmata hub install`." % launchd.LABEL) if sys.platform == "darwin" else finish("updated")
        if check(c["port"]):
            return finish("updated")
        _git(dep, "reset", "--hard", old)
        restart()
        back = check(c["port"])
        return finish("rolled_back", "The hub did not answer after the restart; went back to %s%s. See %s" %
                      ((old or "")[:7], "" if back else " (and it is STILL not answering)", data.log_path))
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


# ------------------------------------------------------------------ set-up
def plist_path():
    return Path("~/Library/LaunchAgents/%s.plist" % LABEL).expanduser()


def make_plist(data, every):
    dep = deploy_dir(data)
    log = str(data.hub / "update.log")
    return {"Label": LABEL, "ProgramArguments": [base_python(), "-m", "lemmata", "hub", "update", "--data", str(data.root)],
            "StartInterval": int(every), "RunAtLoad": True, "StandardOutPath": log, "StandardErrorPath": log,
            "EnvironmentVariables": {"PATH": launchd.PATH_ENV, "PYTHONPATH": str(dep / "app" / "src")}, "WorkingDirectory": str(data.root)}


def hub_plist(data, port):
    """The hub's own LaunchAgent, running from the deploy checkout with the system Python (no virtualenv to rebuild)."""
    p = launchd.make_plist(str(data.root), port)
    p["ProgramArguments"][0] = base_python()
    p["EnvironmentVariables"]["PYTHONPATH"] = str(deploy_dir(data) / "app" / "src")
    return p


def setup(data, cfg, branch=None, every=300, source=None, out=print, service=True):
    """Clone the deploy checkout, point both LaunchAgents at it, start them. service=False (tests) never touches launchd."""
    src = Path(source or Path(__file__).resolve().parents[4])
    url = _git(src, "remote", "get-url", "origin").stdout.strip()
    if not url:
        raise SystemExit("lemmata: could not find the GitHub address of this checkout (%s has no `origin`)." % src)
    if "@" in url.split("://", 1)[-1].split("/", 1)[0] and url.startswith("http"):
        url = url.split("://", 1)[0] + "://" + url.split("@", 1)[1]      # never store credentials from a remote URL
    branch = branch or _git(src, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if not branch or branch == "HEAD":
        raise SystemExit("lemmata: say which branch to follow: `lemmata hub autoupdate install --branch <name>`.")
    if not 60 <= int(every) <= 86400:
        raise SystemExit("lemmata: --every must be between 60 and 86400 seconds.")
    dep = deploy_dir(data)
    if not (dep / ".git").exists():
        dep.parent.mkdir(parents=True, exist_ok=True)
        r = _git(dep.parent, "clone", "--quiet", "--branch", branch, "--single-branch", url, str(dep), timeout=600)
        if r.returncode != 0:
            raise SystemExit("lemmata: could not clone %s (%s): %s" % (url, branch, r.stderr.strip()[-300:]))
    else:
        _git(dep, "remote", "set-url", "origin", url)
        _git(dep, "remote", "set-branches", "origin", branch)
        r = _git(dep, "fetch", "--quiet", "origin", branch)
        if r.returncode != 0:
            raise SystemExit("lemmata: could not fetch %s: %s" % (branch, r.stderr.strip()[-300:]))
        _git(dep, "checkout", "--quiet", "-B", branch, "FETCH_HEAD")
    ok, detail = smoke(dep)
    if not ok:
        raise SystemExit("lemmata: the code on %s does not start, so nothing was changed:\n%s" % (branch, detail))
    cfg.update(update_branch=branch, update_every=int(every))
    out("lemmata hub: following %s of %s in %s" % (branch, url, dep))
    if not service:
        return dep
    if sys.platform != "darwin":
        out("lemmata hub: not macOS, so no LaunchAgents were written. Run `lemmata hub update` from your own scheduler.")
        return dep
    if launchd.temp_data(data.root if hasattr(data, "root") else data):
        out("lemmata hub: %s is a temporary folder, so the background hub was left as it is." % (data.root if hasattr(data, "root") else data))
        return dep
    c = cfg.load()
    from . import guard
    guard.tailscale_info()   # as `hub install` does: run from the user's shell so the service knows the Tailscale addresses
    dom = "gui/%d" % os.getuid()
    for label, path, body in ((launchd.LABEL, launchd.plist_path(), hub_plist(data, c["port"])), (LABEL, plist_path(), make_plist(data, every))):
        path.parent.mkdir(parents=True, exist_ok=True)
        launchd._lc("bootout", "%s/%s" % (dom, label))
        for _ in range(20):
            if launchd._lc("print", "%s/%s" % (dom, label)).returncode != 0:
                break
            time.sleep(0.5)
        path.write_bytes(plistlib.dumps(body))
        for _ in range(8):
            if launchd._lc("bootstrap", dom, str(path)).returncode == 0:
                break
            time.sleep(1.5)
        else:
            raise SystemExit("lemmata: launchctl could not start %s." % label)
    out("lemmata hub: the hub now runs from %s and checks GitHub every %d seconds." % (dep, int(every)))
    out("lemmata hub: running %s" % ("yes" if healthy(c["port"], 40) else "NOT YET — see %s" % data.log_path))
    return dep


def remove(out=print):
    if sys.platform == "darwin":
        launchd._lc("bootout", "gui/%d/%s" % (os.getuid(), LABEL))
    p = plist_path()
    if p.exists():
        p.unlink()
        out("lemmata hub: self-update switched off. The hub keeps running the version it has; `lemmata hub install` from a checkout moves it back there.")
    else:
        out("lemmata hub: self-update was not on.")
