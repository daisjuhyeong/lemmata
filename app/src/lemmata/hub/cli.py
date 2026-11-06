"""`lemmata hub ...` commands."""
from __future__ import annotations

import json
import signal
import socket
import sys
import threading
import urllib.request
from pathlib import Path

from .config import Config, DataDir, DEFAULT_PORT


def _data(args):
    return DataDir(args.data).ensure()


def _host_for_urls(hub_guard_hosts, override=None):
    if override:
        return override
    names = sorted((h for h in hub_guard_hosts if "." not in h and h not in ("localhost",) and not h.replace(".", "").isdigit() and ":" not in h), key=len)
    return names[0] if names else socket.gethostname()


def cmd_serve(args):
    from lemmata.cli import _need_git
    import os

    from . import guard
    from .routes import Hub, make_hub_servers, start_background

    _need_git(args)
    os.umask(0o077)  # every file the hub creates is private from the start
    hub = Hub(args.data, port=args.port, extra_hosts=args.allow_host or [])
    if guard.funnel_active(hub.port):
        raise SystemExit("lemmata: Tailscale Funnel exposes port %d to the internet; turn it off (`tailscale funnel reset`) and start again." % hub.port)
    hosts = [args.host] if args.host else guard.bind_addresses()
    try:
        servers = make_hub_servers(hub, hosts)
    except OSError as e:
        raise SystemExit("lemmata: could not start the hub: %s" % e)
    code = hub.auth.current_code()
    c = hub.cfg.load()
    if hosts == ["127.0.0.1", "::1"]:
        print("lemmata hub: WARNING: Tailscale was not detected; listening on loopback only", flush=True)
    print("lemmata hub: listening on %s port %d (loopback and Tailscale only)" % (", ".join(s.server_address[0] for s in servers), hub.port), flush=True)
    print("lemmata hub: data %s" % hub.data.root, flush=True)
    print("lemmata hub: allowed hosts: %s" % ", ".join(sorted(hub.guard.hosts)), flush=True)
    print("lemmata hub: pairing code %s (valid 10 minutes; `lemmata hub pair-code` makes another)" % code, flush=True)
    if not c.get("github_client_id"):
        print("lemmata hub: no GitHub client id set (lemmata hub config --github-client-id ...)", flush=True)
    loop = start_background(hub)

    def on_term(signum, frame):
        threading.Thread(target=servers[0].shutdown, daemon=True).start()

    try:
        signal.signal(signal.SIGTERM, on_term)
    except ValueError:
        pass
    for s in servers[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    extra = []
    if not args.host:
        stop = threading.Event()

        def watch_tailscale():
            """Tailscale may come up after login/boot: bind its addresses when they appear, then keep watching for new ones."""
            logged = False
            while not stop.wait(15):
                try:
                    bound = {s.server_address[0] for s in servers + extra}
                    new = [a for a in guard.bind_addresses() if a not in bound and a not in ("127.0.0.1", "::1")]
                    if not new:
                        continue
                    hub.guard.refresh()
                    for a in new:
                        try:
                            s = make_hub_servers(hub, [a])[0]
                        except (OSError, IndexError):
                            continue
                        extra.append(s)
                        threading.Thread(target=s.serve_forever, daemon=True).start()
                        if not logged:
                            print("lemmata hub: Tailscale is up; now also listening on %s" % ", ".join(sorted({x.server_address[0] for x in extra})), flush=True)
                            logged = True
                except Exception as e:
                    print("lemmata hub: tailscale watch: %s" % e, flush=True)

        threading.Thread(target=watch_tailscale, name="lemmata-ts-watch", daemon=True).start()
    try:
        servers[0].serve_forever()
    except KeyboardInterrupt:
        print("\nlemmata hub: stopped", flush=True)
    finally:
        loop.stop()
        for s in extra:
            s.shutdown()
            s.server_close()
        for s in servers[1:]:
            s.shutdown()
        for s in servers:
            s.server_close()
    return 0


def cmd_install(args):
    from . import guard, launchd

    if sys.platform != "darwin":
        raise SystemExit("lemmata: `hub install` writes a macOS LaunchAgent; on this system run `lemmata hub serve` yourself.")
    port = args.port or Config(_data(args)).load()["port"]
    ips, _ = guard.tailscale_info()  # run from the user's shell: remembers the Tailscale names for the service
    p = launchd.install(args.data, port)
    if ips:
        print("lemmata hub: Tailscale address(es): %s" % ", ".join(sorted(ips)))
    print("lemmata hub: installed %s and started it on port %d" % (p, port))
    print("lemmata hub: log %s" % (_data(args).log_path))
    print("lemmata hub: get a pairing code with `lemmata hub pair-code`")
    return 0


def cmd_uninstall(args):
    from . import launchd

    print("lemmata hub: %s" % ("uninstalled (data kept)" if launchd.uninstall() else "was not installed"))
    return 0


def cmd_pair_code(args):
    from .auth import Auth

    print(Auth(_data(args)).new_code() if args.new else Auth(_data(args)).current_code())
    return 0


def cmd_token(args):
    from .auth import Auth
    from .guard import Guard

    d = _data(args)
    token, did = Auth(d).new_device(args.device)
    port = Config(d).load()["port"]
    host = _host_for_urls(Guard(detect=True).hosts, args.host) if not args.host else args.host
    print("device %s (%s)" % (did, args.device))
    print("token (shown once): %s" % token)
    print()
    print('claude mcp add --scope user --transport http lemmata http://%s:%d/mcp --header "Authorization: Bearer %s"' % (host, port, token))
    print()
    print("WARNING: this token grants full access to the hub; keep it only in Claude Code's user config (--scope user), never in a project's .mcp.json or a repo.")
    return 0


def cmd_devices(args):
    from .auth import Auth

    devs = Auth(_data(args)).devices()
    if not devs:
        print("no paired devices")
    for x in devs:
        print("%-14s %-20s created %s  last used %s" % (x["device_id"], x["name"], x["created"], x["last_used"] or "never"))
    return 0


def cmd_revoke(args):
    from .auth import Auth

    ok = Auth(_data(args)).revoke(args.device_id)
    print("revoked %s" % args.device_id if ok else "no such device: %s" % args.device_id)
    return 0 if ok else 1


def cmd_config(args):
    cfg = Config(_data(args))
    kw = {}
    if args.github_client_id:
        kw["github_client_id"] = args.github_client_id
    if args.sync_interval:
        kw["sync_interval"] = args.sync_interval
    if args.overleaf:
        kw["overleaf_enabled"] = args.overleaf == "on"
    if args.allow_host:
        kw["allow_hosts"] = sorted(set(cfg.load().get("allow_hosts") or []) | set(args.allow_host))
    c = cfg.update(**kw) if kw else cfg.load()
    print(json.dumps(c, indent=1))
    return 0


def cmd_status(args):
    from .auth import Auth
    from .guard import Guard
    from .projects import Manager
    from .github import GitHub

    d = _data(args)
    cfg = Config(d)
    c = cfg.load()
    port = c["port"]
    g = Guard(c.get("allow_hosts") or [])
    print("URLs:")
    for h in sorted(g.hosts - {"::1"}):
        print("  http://%s:%d/" % (h, port))
    gh = GitHub(d, cfg)
    print("owner: %s" % (c.get("owner") or "(none yet; first GitHub sign-in becomes the owner)"))
    print("GitHub connected: %s" % ("yes" if gh.stored() else "no"))
    ids = Manager(d, cfg, gh).ids()
    print("projects: %s" % (", ".join(ids) or "none"))
    devs = Auth(d).devices()
    print("devices: %s" % (", ".join("%s (%s)" % (x["name"], x["device_id"]) for x in devs) or "none"))
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/hub/status" % port, timeout=2) as r:
            print("running: yes (version %s)" % json.loads(r.read())["version"])
    except Exception:
        print("running: no")
    return 0


def add_parser(sub):
    h = sub.add_parser("hub", help="the always-on multi-project server (Mac mini)")
    hs = h.add_subparsers(dest="hub_cmd", required=True)

    def data(p):
        p.add_argument("--data", default=None, help="data folder (default ~/Lemmata, or $LEMMATA_HOME)")

    p = hs.add_parser("serve")
    data(p)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--host", default=None, help="listen on this one address instead of loopback + Tailscale IPs")
    p.add_argument("--allow-host", action="append", help="extra allowed Host header value")
    p.set_defaults(fn=cmd_serve)
    p = hs.add_parser("install")
    data(p)
    p.add_argument("--port", type=int, default=None)
    p.set_defaults(fn=cmd_install)
    p = hs.add_parser("uninstall")
    p.set_defaults(fn=cmd_uninstall)
    p = hs.add_parser("status")
    data(p)
    p.set_defaults(fn=cmd_status)
    p = hs.add_parser("pair-code")
    data(p)
    p.add_argument("--new", action="store_true", help="always create a fresh code")
    p.set_defaults(fn=cmd_pair_code)
    p = hs.add_parser("token", help="create a device token for an MCP client (shown once)")
    data(p)
    p.add_argument("--device", default="VS Code")
    p.add_argument("--host", default=None)
    p.set_defaults(fn=cmd_token)
    p = hs.add_parser("devices")
    data(p)
    p.set_defaults(fn=cmd_devices)
    p = hs.add_parser("revoke")
    data(p)
    p.add_argument("device_id")
    p.set_defaults(fn=cmd_revoke)
    p = hs.add_parser("config")
    data(p)
    p.add_argument("--github-client-id")
    p.add_argument("--sync-interval", type=int)
    p.add_argument("--allow-host", action="append")
    p.add_argument("--overleaf", choices=["on", "off"], help="switch the dormant Overleaf feature on or off (default off)")
    p.set_defaults(fn=cmd_config)
