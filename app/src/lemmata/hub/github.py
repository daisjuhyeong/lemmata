"""GitHub device flow, repo listing and per-command git auth. No client secret anywhere."""
from __future__ import annotations

import base64
import json
import re
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
            for form in (s, base64.b64encode(("x-access-token:%s" % s).encode()).decode()):
                text = text.replace(form, "***")
    text = re.sub(r"(?i)(authorization:\s*(?:basic|bearer|token)\s+)\S+", r"\1***", text)
    text = re.sub(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})", "***", text)
    return text


def git_auth_header(token):
    return "Authorization: Basic " + base64.b64encode(("x-access-token:%s" % token).encode()).decode()


class GitHub:
    def __init__(self, data, cfg):
        self.data, self.cfg = data, cfg
        self.pending = None  # {"device_code","interval","expires"}

    # --- stored login
    def stored(self):
        d = read_json(self.data.github_path, None)
        return d if isinstance(d, dict) and d.get("token") else None

    def token(self):
        s = self.stored()
        return s["token"] if s else None

    def save(self, token, user):
        write_private(self.data.github_path, json.dumps({"token": token, "login": user.get("login"), "name": user.get("name"),
                                                         "avatar_url": user.get("avatar_url")}, indent=1) + "\n")

    def logout(self):
        try:
            self.data.github_path.unlink()
        except FileNotFoundError:
            pass
        self.pending = None

    def user_public(self):
        s = self.stored()
        return {"login": s.get("login"), "name": s.get("name"), "avatar_url": s.get("avatar_url")} if s else None

    # --- http
    def _http(self, method, url, form=None, token=None, timeout=20):
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
            if e.code in (401, 403) and token:
                raise GitHubError(401, "github_token_invalid", "GitHub rejected the saved sign-in; sign in again.")
            raise GitHubError(502, "github_error", "GitHub answered HTTP %d" % e.code)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise GitHubError(502, "github_unreachable", "Could not reach GitHub: %s" % scrub(getattr(e, "reason", e), token))

    # --- device flow
    def start(self):
        import time
        c = self.cfg.load()
        if not c.get("github_client_id"):
            raise GitHubError(409, "no_client_id", "No GitHub client id configured (lemmata hub config --github-client-id).")
        r = self._http("POST", c["github_web"].rstrip("/") + "/login/device/code", {"client_id": c["github_client_id"], "scope": SCOPE})
        if "device_code" not in r:
            raise GitHubError(502, "github_error", "GitHub did not return a device code: %s" % scrub(r.get("error_description") or r.get("error") or ""))
        self.pending = {"device_code": r["device_code"], "interval": int(r.get("interval", 5)), "expires": time.time() + int(r.get("expires_in", 900))}
        return {"user_code": r["user_code"], "verification_uri": r["verification_uri"],
                "expires_in": int(r.get("expires_in", 900)), "interval": int(r.get("interval", 5))}

    def poll(self):
        """{"state": pending|ok|denied|expired|error, "user"?}. Raises GitHubError(403, not_owner)."""
        import time
        p = self.pending
        if not p:
            if self.stored():
                return {"state": "ok", "user": self.user_public()}
            return {"state": "error", "message": "no sign-in in progress"}
        if time.time() > p["expires"]:
            self.pending = None
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
            self.pending = None
            return {"state": "denied"}
        if err == "expired_token":
            self.pending = None
            return {"state": "expired"}
        if err or "access_token" not in r:
            self.pending = None
            return {"state": "error", "message": scrub(r.get("error_description") or err or "unknown error")}
        token = r["access_token"]
        u = self._http("GET", c["github_api"].rstrip("/") + "/user", token=token)
        login = u.get("login")
        owner = c.get("owner")
        self.pending = None
        if owner and owner != login:
            raise GitHubError(403, "not_owner", "This hub belongs to GitHub user %s." % owner)
        self.save(token, u)
        if not owner:
            self.cfg.update(owner=login)
        return {"state": "ok", "user": self.user_public()}

    # --- repos
    def repos(self, q=""):
        token = self.token()
        if not token:
            raise GitHubError(409, "not_signed_in", "Sign in with GitHub first.")
        api = self.cfg.load()["github_api"].rstrip("/")
        out = []
        for page in range(1, 6):
            url = "%s/user/repos?%s" % (api, urllib.parse.urlencode({"affiliation": "owner,collaborator,organization_member",
                                                                      "sort": "pushed", "per_page": 100, "page": page}))
            items = self._http("GET", url, token=token)
            if not isinstance(items, list):
                break
            out += items
            if len(items) < 100:
                break
        q = (q or "").strip().lower()
        res = [{"full_name": r.get("full_name"), "private": bool(r.get("private")), "default_branch": r.get("default_branch"),
                "pushed_at": r.get("pushed_at"), "description": r.get("description")} for r in out if r.get("full_name")]
        if q:
            res = [r for r in res if q in r["full_name"].lower() or q in (r["description"] or "").lower()]
        res.sort(key=lambda r: r["pushed_at"] or "", reverse=True)
        return {"repos": res}
