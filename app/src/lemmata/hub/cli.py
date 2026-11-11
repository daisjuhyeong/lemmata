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
    pub = hub.cfg.load().get("public_url")
    if pub and not guard.public_host(pub):
        raise SystemExit("lemmata: public_url must be an https:// address without a path (got %r)." % pub)
    if not pub and guard.funnel_active(hub.port):
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
    if pub:
        print("lemmata hub: PUBLIC site at %s — sign-up: %s, up to %s accounts. Anyone admitted can sign in with GitHub; "
              "their repositories are cloned onto this machine." % (pub, c.get("signup", "owner"), c.get("max_users", 50)), flush=True)
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


def cmd_update(args):
    from . import update
    d = _data(args)
    return 0 if update.run(d, Config(d), force=args.force) in ("none", "updated") else 1


def cmd_autoupdate(args):
    from . import update
    d = _data(args)
    cfg = Config(d)
    if args.action == "install":
        kw = {}
        if args.notify is not None:
            from .projects import SLACK_RE
            if args.notify and not SLACK_RE.match(args.notify):
                raise SystemExit("lemmata: --notify must be a Slack incoming-webhook URL (https://hooks.slack.com/services/...).")
            kw["update_webhook"] = args.notify or None
        if args.on_failure is not None:
            kw["update_on_failure"] = args.on_failure or None
        if kw:
            cfg.update(**kw)
        update.setup(d, cfg, branch=args.branch, every=args.every)
    elif args.action == "uninstall":
        update.remove()
    else:
        c, st = cfg.load(), update.state(d)
        on = update.plist_path().exists()
        print("self-update: %s" % ("on, following %s every %s s" % (c.get("update_branch"), c.get("update_every")) if on else "off"))
        print("checkout: %s" % update.deploy_dir(d))
        print("Slack reports: %s · on failure: %s" % ("yes" if c.get("update_webhook") else "no", c.get("update_on_failure") or "nothing"))
        if st:
            print("last change: %s %s %s -> %s%s" % (st.get("time"), st.get("result"), (st.get("from") or "")[:7], (st.get("to") or "")[:7],
                                                   "\n  " + "\n  ".join(st.get("subjects") or []) if st.get("subjects") else ""))
            if st.get("detail"):
                print("  " + st["detail"].replace("\n", "\n  "))
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
    if getattr(args, "public_url", None) is not None:
        from .guard import public_host
        if getattr(args, "public_url", None) in ("", "off", "none"):
            kw["public_url"] = None
            kw["signup"] = "owner"
        elif not public_host(getattr(args, "public_url", None)):
            raise SystemExit("lemmata: --public-url must look like https://name.example (https only, no path).")
        else:
            kw["public_url"] = getattr(args, "public_url", None).rstrip("/")
            if cfg.load().get("signup", "owner") == "owner" and not getattr(args, "signup", None):
                kw["signup"] = "invite"   # safest default once the hub is reachable from the internet
    if getattr(args, "signup", None):
        kw["signup"] = getattr(args, "signup", None)
    if getattr(args, "max_users", None):
        kw["max_users"] = getattr(args, "max_users", None)
    if getattr(args, "invite", None) or getattr(args, "uninvite", None):
        cur = {u.lower() for u in cfg.load().get("allowed_users") or []}
        cur |= {u.lower().lstrip("@") for u in getattr(args, "invite", None) or []}
        cur -= {u.lower().lstrip("@") for u in getattr(args, "uninvite", None) or []}
        kw["allowed_users"] = sorted(cur)
    if args.allow_host:
        kw["allow_hosts"] = sorted(set(cfg.load().get("allow_hosts") or []) | set(args.allow_host))
    c = cfg.update(**kw) if kw else cfg.load()
    print(json.dumps(c, indent=1))
    if kw:
        import sys
        print("Restart the hub for this to take effect (`lemmata hub uninstall && lemmata hub install`, or stop and start `lemmata hub serve`).", file=sys.stderr)
    return 0


def cmd_users(args):
    from .github import GitHub
    from .projects import Manager
    d = _data(args)
    cfg = Config(d)
    gh = GitHub(d, cfg)
    mgr = Manager(d, cfg, gh)
    for login in gh.logins():
        u = gh.stored(login) or {}
        print("%-24s start view: %-9s projects: %d%s" % (login, u.get("view") or u.get("variant") or "-", len(mgr.ids(login)),
                                                        "  (GitHub sign-in needs renewing)" if u.get("needs_reauth") else ""))
    return 0


def cmd_ab(args):
    from .routes import Hub
    hub = Hub(args.data, detect_tailscale=False)
    out = hub.ab_summary()
    cols = ["users", "created_project", "confirmed_a_claim", "added_feedback", "asked", "switched_view", "came_back_another_day", "useful_yes", "useful_no"]
    print("%-10s " % "start view" + " ".join("%-12s" % c[:12] for c in cols))
    for v in out["variants"]:
        print("%-10s " % v["variant"] + " ".join("%-12s" % v[c] for c in cols))
    print(out["note"])
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
    from . import update
    st = update.state(d)
    if update.plist_path().exists():
        print("self-update: on, following %s%s" % (c.get("update_branch"), " · last: %s %s -> %s (%s)" % (st.get("result"), (st.get("from") or "")[:7],
                                                   (st.get("to") or "")[:7], st.get("time")) if st else ""))
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
    p = hs.add_parser("update", help="one self-update pass: pull the followed branch, check it starts, restart, roll back if needed")
    data(p)
    p.add_argument("--force", action="store_true", help="restart even when nothing new was pushed")
    p.set_defaults(fn=cmd_update)
    p = hs.add_parser("autoupdate", help="keep the hub up to date with a GitHub branch, on its own")
    p.add_argument("action", choices=["install", "uninstall", "status"])
    data(p)
    p.add_argument("--branch", help="branch to follow (default: the branch of this checkout)")
    p.add_argument("--every", type=int, default=300, help="seconds between checks (default 300)")
    p.add_argument("--notify", help="Slack incoming-webhook URL for update reports ('' to clear)")
    p.add_argument("--on-failure", help="shell command to run when an update fails or is rolled back ('' to clear)")
    p.set_defaults(fn=cmd_autoupdate)
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
    p.add_argument("--public-url", help="https address other people use (from Tailscale Funnel or a Cloudflare tunnel); 'off' makes the hub private again")
    p.add_argument("--signup", choices=["owner", "invite", "open"], help="who may sign in on the public site (default after --public-url: invite)")
    p.add_argument("--invite", action="append", help="GitHub login to admit when sign-up is invite (repeatable)")
    p.add_argument("--uninvite", action="append", help="remove a GitHub login from the invite list")
    p.add_argument("--max-users", type=int)
    p.set_defaults(fn=cmd_config)
    p = hs.add_parser("users", help="accounts on this hub")
    data(p)
    p.set_defaults(fn=cmd_users)
    p = hs.add_parser("ab", help="A/B summary of the four start views")
    data(p)
    p.set_defaults(fn=cmd_ab)
