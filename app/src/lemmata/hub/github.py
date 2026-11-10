"""GitHub device flow, repo listing and per-command git auth. No client secret anywhere."""
from __future__ import annotations

import base64
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .config import read_json, write_private

SCOPE = "repo read:user"
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


class GitHubError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def scrub(text, *secrets_):
    """Remove tokens (and their base64 auth-header form) from any text before it is logged or returned."""
    text = str(text)
    for s in secrets_:
        if s:
            for form in (s, base64.b64encode(("x-access-token:%s" % s).encode()).decode(), base64.b64encode(("git:%s" % s).encode()).decode()):
                text = text.replace(form, "***")
    text = re.sub(r"(?i)(authorization:\s*(?:basic|bearer|token)\s+)\S+", r"\1***", text)
    text = re.sub(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})", "***", text)
    return text


def git_auth_header(token, user="x-access-token"):
    return "Authorization: Basic " + base64.b64encode(("%s:%s" % (user, token)).encode()).decode()


LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
SCOPE_PUBLIC = "read:user"          # sign in only; public repositories need no token scope
VARIANTS = ("claims", "inbox", "timeline", "ask")
REPO_CACHE_TTL = 120
MAX_FLOWS = 200


class GitHub:
    """GitHub sign-ins. The hub owner's sign-in lives in hub/github.json (as before); every other account in
    hub/users/<login>.json. Each account has its own token, so one person's sign-in never reads another's repos."""

    def __init__(self, data, cfg):
        self.data, self.cfg = data, cfg
        self.flows = {}      # flow id -> {"device_code","interval","expires","scope","expect"}
        self._repos = {}     # login -> (time, [repo dicts])
        self._lock = threading.Lock()

    # --- legacy single-flow attribute (tests and old callers)
    @property
    def pending(self):
        return self.flows.get("owner")

    @pending.setter
    def pending(self, v):
        if v is None:
            self.flows.pop("owner", None)
        else:
            self.flows["owner"] = v

    # --- accounts
    def _owner(self):
        return self.cfg.load().get("owner")

    def _is_owner(self, login):
        o = self._owner()
        return login is None or o is None or (o or "").lower() == (login or "").lower()

    def _path(self, login):
        if self._is_owner(login):
            return self.data.github_path
        if not LOGIN_RE.match(login or ""):
            raise GitHubError(400, "bad_request", "bad GitHub login")
        return self.data.hub / "users" / (login.lower() + ".json")

    def stored(self, login=None):
        d = read_json(self._path(login), None)
        return d if isinstance(d, dict) and d.get("token") else None

    def token(self, login=None):
        s = self.stored(login)
        return s["token"] if s else None

    def save(self, token, user, scope=None, login=None):
        login = login or user.get("login")
        old = read_json(self._path(login), None) or {}
        rec = {"token": token, "login": user.get("login"), "name": user.get("name"), "avatar_url": user.get("avatar_url"),
               "scope": scope or old.get("scope") or SCOPE, "created": old.get("created") or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "variant": old.get("variant") or self._next_variant(), "view": old.get("view"), "needs_reauth": False}
        write_private(self._path(login), json.dumps(rec, indent=1) + "\n")
        self._repos.pop((login or "").lower(), None)

    def _patch(self, login, **kw):
        d = read_json(self._path(login), None)
        if isinstance(d, dict):
            d.update(kw)
            write_private(self._path(login), json.dumps(d, indent=1) + "\n")

    def logout(self, login=None):
        try:
            self._path(login).unlink()
        except FileNotFoundError:
            pass
        self.pending = None
        self._repos.pop((login or self._owner() or "").lower(), None)

    def user_public(self, login=None):
        s = self.stored(login)
        if not s:
            return None
        return {"login": s.get("login"), "name": s.get("name"), "avatar_url": s.get("avatar_url"), "private_repos": "repo" in (s.get("scope") or SCOPE).split(),
                "needs_reauth": bool(s.get("needs_reauth")), "variant": s.get("variant"), "view": s.get("view")}

    def logins(self):
        out = []
        o = read_json(self.data.github_path, None)
        if isinstance(o, dict) and o.get("login"):
            out.append(o["login"])
        d = self.data.hub / "users"
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                u = read_json(f, None)
                if isinstance(u, dict) and u.get("login"):
                    out.append(u["login"])
        return out

    def _next_variant(self):
        """A/B assignment: the least-used start view so far (ties in a fixed order), so groups stay balanced."""
        n = dict.fromkeys(VARIANTS, 0)
        for f in [self.data.github_path] + (sorted((self.data.hub / "users").glob("*.json")) if (self.data.hub / "users").is_dir() else []):
            v = (read_json(f, None) or {}).get("variant")
            if v in n:
                n[v] += 1
        return min(VARIANTS, key=lambda v: n[v])

    def set_view(self, login, view):
        if view not in VARIANTS:
            raise GitHubError(400, "bad_request", "view must be one of %s" % ", ".join(VARIANTS))
        self._patch(login, view=view)

    # --- http
    def _http(self, method, url, form=None, token=None, timeout=20, login=False):
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "lemmata-hub")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            hd = e.headers or {}
            try:
                msg = (json.loads(e.read().decode("utf-8", "replace") or "{}").get("message") or "")[:200]
            except (ValueError, OSError):
                msg = ""
            if token and e.code == 401:
                if login is not False:
                    self._patch(login, needs_reauth=True)
                raise GitHubError(401, "github_token_invalid", "GitHub no longer accepts the saved sign-in. Reconnect GitHub to continue.")
            if token and e.code in (403, 429):
                limited = e.code == 429 or hd.get("X-RateLimit-Remaining") == "0" or hd.get("Retry-After") or "rate limit" in msg.lower()
                if limited:
                    wait = hd.get("Retry-After")
                    if not wait and hd.get("X-RateLimit-Reset", "").isdigit():
                        wait = str(max(0, int(hd["X-RateLimit-Reset"]) - int(time.time())))
                    mins = max(1, (int(wait) + 59) // 60) if wait and wait.isdigit() else None
                    raise GitHubError(429, "github_rate_limited", "GitHub is limiting requests right now. Try again in %s." %
                                      ("about %d minute%s" % (mins, "" if mins == 1 else "s") if mins else "a few minutes"))
                raise GitHubError(403, "github_forbidden", "GitHub refused this request%s Your sign-in is still valid." %
                                  (": %s." % scrub(msg, token).rstrip(".") if msg else "."))
            raise GitHubError(502, "github_error", "GitHub answered HTTP %d" % e.code)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise GitHubError(502, "github_unreachable", "Could not reach GitHub: %s" % scrub(getattr(e, "reason", e), token))

    # --- device flow
    def start(self, flow="owner", private=True, expect=None):
        c = self.cfg.load()
        if not c.get("github_client_id"):
            raise GitHubError(409, "no_client_id", "No GitHub client id configured (lemmata hub config --github-client-id).")
        now = time.time()
        with self._lock:
            for k in [k for k, v in self.flows.items() if v["expires"] < now]:
                self.flows.pop(k, None)
            if len(self.flows) >= MAX_FLOWS and flow not in self.flows:
                raise GitHubError(429, "busy", "Too many sign-ins are in progress. Try again in a minute.")
        scope = SCOPE if private else SCOPE_PUBLIC
        r = self._http("POST", c["github_web"].rstrip("/") + "/login/device/code", {"client_id": c["github_client_id"], "scope": scope})
        if "device_code" not in r:
            raise GitHubError(502, "github_error", "GitHub did not return a device code: %s" % scrub(r.get("error_description") or r.get("error") or ""))
        self.flows[flow] = {"device_code": r["device_code"], "interval": int(r.get("interval", 5)), "expires": time.time() + int(r.get("expires_in", 900)),
                            "scope": scope, "expect": expect}
        return {"user_code": r["user_code"], "verification_uri": r["verification_uri"],
                "expires_in": int(r.get("expires_in", 900)), "interval": int(r.get("interval", 5))}

    def _admit(self, login, c):
        """Who may have an account. owner: only the hub owner (private hub). invite: owner + allowed_users. open: anyone, up to max_users."""
        owner, mode = c.get("owner"), c.get("signup", "owner")
        if not owner or owner.lower() == login.lower():
            return
        if mode == "owner":
            raise GitHubError(403, "not_owner", "This hub belongs to GitHub user %s." % owner)
        if self.stored(login):
            return
        if mode == "invite" and login.lower() not in [u.lower() for u in c.get("allowed_users") or []]:
            raise GitHubError(403, "not_invited", "This Lemmata site is invite-only. Ask %s to add your GitHub name (%s)." % (owner, login))
        if len(self.logins()) >= int(c.get("max_users", 50)):
            raise GitHubError(403, "site_full", "This Lemmata site has reached its user limit. Ask %s for a place." % owner)

    def poll(self, flow="owner"):
        """{"state": pending|ok|denied|expired|error, "user"?, "login"?}. Raises GitHubError(403) when the account is not admitted."""
        p = self.flows.get(flow)
        if not p:
            if flow == "owner" and self.stored():
                return {"state": "ok", "user": self.user_public(), "login": self.stored().get("login")}
            return {"state": "error", "message": "no sign-in in progress"}
        if time.time() > p["expires"]:
            self.flows.pop(flow, None)
            return {"state": "expired"}
        c = self.cfg.load()
        r = self._http("POST", c["github_web"].rstrip("/") + "/login/oauth/access_token",
                       {"client_id": c["github_client_id"], "device_code": p["device_code"],
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        err = r.get("error")
        if err in ("authorization_pending", None) and "access_token" not in r:
            return {"state": "pending"}
        if err == "slow_down":
            p["interval"] = int(r.get("interval", p["interval"] + 5))
            return {"state": "pending", "interval": p["interval"]}
        if err == "access_denied":
            self.flows.pop(flow, None)
            return {"state": "denied"}
        if err == "expired_token":
            self.flows.pop(flow, None)
            return {"state": "expired"}
        if err or "access_token" not in r:
            self.flows.pop(flow, None)
            return {"state": "error", "message": scrub(r.get("error_description") or err or "unknown error")}
        token = r["access_token"]
        u = self._http("GET", c["github_api"].rstrip("/") + "/user", token=token)
        login = u.get("login") or ""
        self.flows.pop(flow, None)
        if not LOGIN_RE.match(login):
            return {"state": "error", "message": "GitHub did not return a user name"}
        if p.get("expect") and p["expect"].lower() != login.lower():
            raise GitHubError(403, "wrong_account", "You approved as %s, but this session belongs to %s. Sign in to GitHub as %s and try again."
                              % (login, p["expect"], p["expect"]))
        self._admit(login, c)
        if not c.get("owner"):
            self.cfg.update(owner=login)
        self.save(token, u, scope=p.get("scope"), login=login)
        return {"state": "ok", "user": self.user_public(login), "login": login}

    def check(self, login=None):
        """Ask GitHub whether the saved sign-in still works. -> True/False, or None when GitHub could not be asked."""
        token = self.token(login)
        if not token:
            return False
        try:
            self._http("GET", self.cfg.load()["github_api"].rstrip("/") + "/user", token=token, login=login)
        except GitHubError as e:
            return False if e.code == "github_token_invalid" else None
        if (self.stored(login) or {}).get("needs_reauth"):
            self._patch(login, needs_reauth=False)
        return True

    # --- repos
    def repos(self, q="", login=None, refresh=False):
        token = self.token(login)
        if not token:
            raise GitHubError(409, "not_signed_in", "Sign in with GitHub first.")
        key = (login or self._owner() or "").lower()
        hit = self._repos.get(key)
        if hit and not refresh and time.time() - hit[0] < REPO_CACHE_TTL:
            out = hit[1]
        else:
            api = self.cfg.load()["github_api"].rstrip("/")
            out = []
            for page in range(1, 6):
                url = "%s/user/repos?%s" % (api, urllib.parse.urlencode({"affiliation": "owner,collaborator,organization_member",
                                                                          "sort": "pushed", "per_page": 100, "page": page}))
                items = self._http("GET", url, token=token, login=login)
                if not isinstance(items, list):
                    break
                out += items
                if len(items) < 100:
                    break
            self._repos[key] = (time.time(), out)
        q = (q or "").strip().lower()
        res = [{"full_name": r.get("full_name"), "private": bool(r.get("private")), "default_branch": r.get("default_branch"),
                "pushed_at": r.get("pushed_at"), "description": r.get("description")} for r in out if r.get("full_name")]
        if q:
            res = [r for r in res if q in r["full_name"].lower() or q in (r["description"] or "").lower()]
        res.sort(key=lambda r: r["pushed_at"] or "", reverse=True)
        return {"repos": res}
