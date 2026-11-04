"""Command line: demo, open, serve, scan, checkpoint (demo-architecture section 3)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from rmap import __version__

MARKER = ".rmap-sample"
HUB = ".rmap"


def _engine_class(fixtures):
    if fixtures:
        from rmap.fixture_engine import FixtureEngine

        variant = fixtures if isinstance(fixtures, str) else "sample"

        def make(root, online=False):
            return FixtureEngine(root, online=online, variant=variant)

        return make
    try:
        from rmap.engine.api import Engine
    except ImportError as e:
        raise SystemExit("rmap: the engine is not available (%s). Use --fixtures to run the UI on fixture data." % e)
    return Engine


def _serve(engine, args):
    from rmap.server import bind

    try:
        srv = bind(engine, port=args.port)
    except OSError as e:
        raise SystemExit("rmap: could not start the server: %s" % e)
    url = "http://127.0.0.1:%d" % srv.server_address[1]
    name = engine.project().get("name", "project")
    print("rmap: serving %s at %s  (Ctrl-C to stop)" % (name, url), flush=True)
    if not args.no_open:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nrmap: stopped")
    finally:
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
    data = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {"schema": "rmap.project/1", "name": root.name, "repos": []}
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
    make = Path(__file__).resolve().parents[2] / "samples" / "make_sample.py"
    if not args.keep:
        if root.exists():
            if not (root / MARKER).exists():
                raise SystemExit("rmap: %s exists and is not a sample folder (no %s); refusing to delete it. Pick another --dir." % (root, MARKER))
            shutil.rmtree(root)
    if not root.exists() or not args.keep:
        if not make.exists():
            raise SystemExit("rmap: demo needs a source checkout (app/samples/make_sample.py not found).")
        r = subprocess.run([sys.executable, str(make), str(root)])
        if r.returncode:
            raise SystemExit("rmap: building the sample failed")
    engine = _engine_class(False)(root, online=args.online)
    engine.scan()
    return _serve(engine, args)


def cmd_open(args):
    root = Path(args.project_dir).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit("rmap: %s is not a folder" % root)
    if args.fixtures:
        return _serve(_engine_class(args.fixtures)(root), args)
    _write_manifest(root, args.paper, args.code)
    engine = _engine_class(False)(root, online=args.online)
    engine.scan()
    return _serve(engine, args)


def cmd_serve(args):
    root = Path(args.project_dir).expanduser().resolve()
    if not args.fixtures and not (root / HUB / "project.json").exists():
        raise SystemExit("rmap: %s has no %s/project.json; use `rmap open` first." % (root, HUB))
    engine = _engine_class(args.fixtures)(root, online=args.online)
    engine.scan()
    return _serve(engine, args)


def cmd_scan(args):
    root = Path(args.project_dir).expanduser().resolve()
    engine = _engine_class(args.fixtures)(root, online=args.online)
    st = engine.scan()
    c = st.get("counts", {})
    print("rmap: %s: %s nodes, %s edges, %s proposed links, %s findings, %s alarm groups" % (
        st.get("name", root.name), c.get("nodes"), c.get("edges"), c.get("proposed"), c.get("findings"), c.get("alarm_groups")))
    return 0


def cmd_checkpoint(args):
    root = Path(args.project_dir).expanduser().resolve()
    at = {}
    for item in args.at or []:
        if "=" not in item:
            raise SystemExit("rmap: --at expects repo=rev, got %r" % item)
        k, v = item.split("=", 1)
        at[k] = v
    engine = _engine_class(args.fixtures)(root)
    engine.scan()
    out = engine.create_checkpoint(note=args.note or "", at=at or None)
    cp = out["checkpoint"]
    print("rmap: created checkpoint %s (%s nodes)" % (cp["id"], cp.get("node_count")))
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="rmap", description="Research Map: track paper, code and runs as a dependency graph.")
    ap.add_argument("--version", action="version", version="rmap " + __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, serving=True):
        p.add_argument("--fixtures", nargs="?", const="sample", default=None, choices=["sample", "large"],
                       help="run on fixture data instead of the engine (UI development)")
        p.add_argument("--online", action="store_true", help="opt in to online reference lookup (OpenAlex, Crossref)")
        if serving:
            p.add_argument("--port", type=int, default=8765)
            p.add_argument("--no-open", action="store_true", help="do not open the browser")

    d = sub.add_parser("demo", help="build the synthetic sample, scan it and serve it")
    d.add_argument("--dir", default="~/rmap-demo")
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
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
