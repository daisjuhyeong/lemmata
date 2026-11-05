"""Command line: demo, open, serve, scan, checkpoint (demo-architecture section 3)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path

from lemmata import __version__

MARKER = ".lemmata-sample"
HUB = ".lemmata"


def _engine_class(fixtures):
    if fixtures:
        from lemmata.fixture_engine import FixtureEngine

        variant = fixtures if isinstance(fixtures, str) else "sample"

        def make(root, online=False):
            return FixtureEngine(root, online=online, variant=variant)

        return make
    try:
        from lemmata.engine.api import Engine
    except ImportError as e:
        raise SystemExit("lemmata: the engine is not available (%s). Use --fixtures to run the UI on fixture data." % e)
    return Engine


class Fatal(SystemExit):
    """Fatal error with a short machine code (sidecar contract)."""


def _fail(args, code, message):
    """--ready-json: one JSON error line on stdout; otherwise a plain message on stderr. Exit code 1 either way."""
    if getattr(args, "ready_json", False):
        print(json.dumps({"event": "error", "code": code, "message": message}, ensure_ascii=False, separators=(",", ":")), flush=True)
        print("lemmata: %s" % message, file=sys.stderr, flush=True)
        raise Fatal(1)
    raise Fatal("lemmata: %s" % message)


def _need_git(args):
    from lemmata.gitbin import ensure_git

    if not ensure_git():
        _fail(args, "git_missing", "git was not found. Install Apple's Command Line Tools (xcode-select --install) or git, then try again.")


def _scan(engine, args):
    try:
        engine.scan()
    except Exception as e:
        _fail(args, "scan_failed", "scanning the project failed: %s: %s" % (type(e).__name__, e))


def _looks_like_project(root: Path):
    """A .lemmata/project.json, a git repo, or a .tex file within three levels."""
    if (root / HUB / "project.json").exists():
        return True
    seen = 0
    base = len(root.parts)
    for dp, dns, fns in os.walk(root):
        if ".git" in dns or ".git" in fns or any(f.endswith(".tex") for f in fns):
            return True
        dns[:] = [d for d in dns if not d.startswith(".") and d not in ("node_modules", "__pycache__")]
        if len(Path(dp).parts) - base >= 3:
            dns[:] = []
        seen += len(fns)
        if seen > 5000:
            break
    return False


def _watch_parent(pid, srv):
    """Exit (clean shutdown, hard exit after 1 s as a fallback) when process `pid` disappears."""
    def alive():
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    def loop():
        while True:
            time.sleep(0.5)
            if not alive():
                try:  # stderr may already be closed if the app was killed; never let that stop the exit
                    print("lemmata: parent process %d is gone; exiting" % pid, file=sys.stderr, flush=True)
                except Exception:
                    pass
                threading.Timer(1.0, lambda: os._exit(0)).start()
                srv.shutdown()
                return

    threading.Thread(target=loop, name="lemmata-parent", daemon=True).start()


def _serve(engine, args):
    from lemmata.server import bind

    try:
        srv = bind(engine, port=args.port)
    except OSError as e:
        _fail(args, "bind_failed", "could not start the server: %s" % e)
    port = srv.server_address[1]
    url = "http://127.0.0.1:%d/" % port
    proj = engine.project()
    name = proj.get("name", "project")
    root = str(Path(proj.get("root") or getattr(engine, "root", "") or ".").resolve())
    if getattr(args, "ready_json", False):
        print(json.dumps({"event": "ready", "url": url, "port": port, "project": name, "root": root}, ensure_ascii=False, separators=(",", ":")), flush=True)
        print("lemmata: serving %s at %s" % (name, url), file=sys.stderr, flush=True)
    else:
        print("lemmata: serving %s at %s  (Ctrl-C to stop)" % (name, url.rstrip("/")), flush=True)
    if not args.no_open:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    watcher = None
    if getattr(args, "watch", False) and not args.fixtures:
        from lemmata.watch import Watcher

        watcher = Watcher(srv.app)
        watcher.start()
    if getattr(args, "parent_pid", None):
        _watch_parent(args.parent_pid, srv)

    def on_term(signum, frame):
        threading.Thread(target=srv.shutdown, daemon=True).start()

    try:
        signal.signal(signal.SIGTERM, on_term)
    except ValueError:  # not the main thread
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nlemmata: stopped", file=sys.stderr, flush=True)
    finally:
        if watcher:
            watcher.stop()
        srv.server_close()
    return 0


def _detect_role(d: Path):
    for p in list(d.glob("*.tex")) + list(d.glob("*/*.tex")):
        try:
            if "\\documentclass" in p.read_text(encoding="utf-8", errors="ignore"):
                return "paper"
        except OSError:
            pass
    return "code"


def _write_manifest(root: Path, paper, code):
    hub = root / HUB
    hub.mkdir(exist_ok=True)
    gi = hub / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")
    mf = hub / "project.json"
    data = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {"schema": "lemmata.project/1", "name": root.name, "repos": []}
    repos = {r["id"]: r for r in data.get("repos", [])}
    if not repos and not paper and not code:
        role = _detect_role(root)
        repos[role] = {"id": role, "role": role, "path": "."}
    for rid, path in (("paper", paper), ("code", code)):
        if path:
            repos[rid] = {"id": rid, "role": rid, "path": str(Path(path).expanduser().resolve())}
    data["repos"] = [repos[k] for k in ("paper", "code") if k in repos]
    tmp = mf.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, mf)


def cmd_demo(args):
    root = Path(args.dir).expanduser()
    if args.fixtures:
        engine = _engine_class(args.fixtures)(root, online=False)
        return _serve(engine, args)
    _need_git(args)
    if not args.keep and root.exists():
        if root.is_dir() and not any(root.iterdir()):
            pass  # an empty folder is fine
        elif not (root / MARKER).exists():
            _fail(args, "not_sample", "%s exists and is not a sample folder (no %s); refusing to delete it. Pick another --dir." % (root, MARKER))
        else:
            shutil.rmtree(root)
    if not root.exists() or not args.keep:
        from lemmata.samples.make_sample import build

        try:
            build(root)
        except SystemExit as e:
            _fail(args, "scan_failed", "building the sample failed: %s" % (e.code,))
        except Exception as e:
            _fail(args, "scan_failed", "building the sample failed: %s: %s" % (type(e).__name__, e))
    engine = _engine_class(False)(root, online=args.online)
    _scan(engine, args)
    return _serve(engine, args)


def cmd_open(args):
    root = Path(args.project_dir).expanduser().resolve()
    if not root.is_dir():
        _fail(args, "not_found", "%s is not a folder" % root)
    for extra in (args.paper, args.code):
        if extra and not Path(extra).expanduser().is_dir():
            _fail(args, "not_found", "%s is not a folder" % extra)
    if args.fixtures:
        return _serve(_engine_class(args.fixtures)(root), args)
    _need_git(args)
    if not (args.paper or args.code or _looks_like_project(root)):
        _fail(args, "no_project", "%s has no LaTeX files and no git repository; pick the folder that holds your paper and/or code." % root)
    _write_manifest(root, args.paper, args.code)
    engine = _engine_class(False)(root, online=args.online)
    _scan(engine, args)
    return _serve(engine, args)


def cmd_serve(args):
    root = Path(args.project_dir).expanduser().resolve()
    if not root.is_dir():
        _fail(args, "not_found", "%s is not a folder" % root)
    if not args.fixtures:
        _need_git(args)
        if not (root / HUB / "project.json").exists():
            _fail(args, "no_project", "%s has no %s/project.json; use `lemmata open` first." % (root, HUB))
    engine = _engine_class(args.fixtures)(root, online=args.online)
    _scan(engine, args)
    return _serve(engine, args)


def cmd_scan(args):
    root = Path(args.project_dir).expanduser().resolve()
    if not args.fixtures:
        _need_git(args)
    engine = _engine_class(args.fixtures)(root, online=args.online)
    st = engine.scan()
    c = st.get("counts", {})
    print("lemmata: %s: %s nodes, %s edges, %s proposed links, %s findings, %s alarm groups" % (
        st.get("name", root.name), c.get("nodes"), c.get("edges"), c.get("proposed"), c.get("findings"), c.get("alarm_groups")))
    return 0


def cmd_checkpoint(args):
    root = Path(args.project_dir).expanduser().resolve()
    if not args.fixtures:
        _need_git(args)
    at = {}
    for item in args.at or []:
        if "=" not in item:
            raise SystemExit("lemmata: --at expects repo=rev, got %r" % item)
        k, v = item.split("=", 1)
        at[k] = v
    engine = _engine_class(args.fixtures)(root)
    engine.scan()
    out = engine.create_checkpoint(note=args.note or "", at=at or None)
    cp = out["checkpoint"]
    print("lemmata: created checkpoint %s (%s nodes)" % (cp["id"], cp.get("node_count")))
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="lemmata", description="Lemmata: track paper, code and runs as a dependency graph.")
    ap.add_argument("--version", action="version", version="lemmata " + __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, serving=True):
        p.add_argument("--fixtures", nargs="?", const="sample", default=None, choices=["sample", "large"],
                       help="run on fixture data instead of the engine (UI development)")
        p.add_argument("--online", action="store_true", help="opt in to online reference lookup (OpenAlex, Crossref)")
        if serving:
            p.add_argument("--port", type=int, default=8765, help="0 = any free port")
            p.add_argument("--no-open", action="store_true", help="do not open the browser")
            p.add_argument("--ready-json", action="store_true", help="print one JSON line (ready or error) on stdout; logs go to stderr")
            p.add_argument("--parent-pid", type=int, default=None, help="exit within 2 s after this process disappears")
            p.add_argument("--watch", action="store_true", help="rescan every time the project changes (polled every 3 s)")

    d = sub.add_parser("demo", help="build the synthetic sample, scan it and serve it")
    d.add_argument("--dir", default="~/lemmata-demo")
    d.add_argument("--keep", action="store_true", help="keep an existing sample folder (keeps triage)")
    common(d)
    d.set_defaults(fn=cmd_demo)

    o = sub.add_parser("open", help="scan a project folder and serve it")
    o.add_argument("project_dir")
    o.add_argument("--paper", help="folder of the unzipped paper project")
    o.add_argument("--code", help="folder of the code repository")
    common(o)
    o.set_defaults(fn=cmd_open)

    s = sub.add_parser("serve", help="serve an already opened project")
    s.add_argument("project_dir")
    common(s)
    s.set_defaults(fn=cmd_serve)

    sc = sub.add_parser("scan", help="scan a project and print a one-line summary")
    sc.add_argument("project_dir")
    common(sc, serving=False)
    sc.set_defaults(fn=cmd_scan)

    c = sub.add_parser("checkpoint", help="create a checkpoint (your 'last known good')")
    c.add_argument("project_dir")
    c.add_argument("--at", action="append", metavar="REPO=REV")
    c.add_argument("--note")
    common(c, serving=False)
    c.set_defaults(fn=cmd_checkpoint)
    return ap


def main(argv=None):
    from lemmata.gitbin import restore_loader_env

    restore_loader_env()
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except Fatal:
        raise
    except Exception as e:  # with --ready-json the caller always gets a JSON error line
        if getattr(args, "ready_json", False):
            _fail(args, "scan_failed", "%s: %s" % (type(e).__name__, e))
        raise


if __name__ == "__main__":
    sys.exit(main())
