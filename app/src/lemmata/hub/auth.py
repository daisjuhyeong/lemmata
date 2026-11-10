"""Pairing codes, device tokens (stored as sha256) and session lookup."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
from datetime import datetime, timezone

from .config import read_json, write_private

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LEN = 8
CODE_TTL = 600
MAX_WRONG = 5
COOKIE = "lemmata_session"


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Auth:
    def __init__(self, data):
        self.data = data
        self.lock = threading.Lock()
        self._touched = {}

    # --- tokens
    def _load(self):
        d = read_json(self.data.tokens_path, None)
        if not isinstance(d, dict) or not isinstance(d.get("devices"), list):
            d = {"devices": []}
        return d

    def _save(self, d):
        write_private(self.data.tokens_path, json.dumps(d, indent=1) + "\n")

    def new_device(self, name, user=None, kind=None):
        """user: the GitHub login this session or token belongs to (None = the hub owner, as before S07)."""
        name = (name or "device").strip()[:60] or "device"
        token = secrets.token_urlsafe(32)  # 43 chars
        dev = {"device_id": "dev_" + secrets.token_hex(4), "name": name, "hash": _hash(token), "created": _now(), "last_used": None}
        if user:
            dev["user"] = user
        if kind:
            dev["kind"] = kind
        with self.lock:
            d = self._load()
            d["devices"].append(dev)
            self._save(d)
        return token, dev["device_id"]

    def lookup(self, token):
        """device dict for a valid token, else None. last_used is persisted at most once a minute."""
        if not token or len(token) > 200:
            return None
        h = _hash(token)
        with self.lock:
            d = self._load()
            for dev in d["devices"]:
                if hmac.compare_digest(dev["hash"], h):
                    now = time.time()
                    if now - self._touched.get(dev["device_id"], 0) > 60:
                        self._touched[dev["device_id"]] = now
                        dev["last_used"] = _now()
                        self._save(d)
                    return dev
        return None

    def devices(self):
        return [{k: v for k, v in dv.items() if k != "hash"} for dv in self._load()["devices"]]

    def revoke_user(self, user):
        with self.lock:
            d = self._load()
            n = len(d["devices"])
            d["devices"] = [x for x in d["devices"] if (x.get("user") or "").lower() != user.lower()]
            if len(d["devices"]) != n:
                self._save(d)
            return n - len(d["devices"])

    def revoke(self, device_id, user=None):
        with self.lock:
            d = self._load()
            n = len(d["devices"])
            d["devices"] = [x for x in d["devices"] if not (x["device_id"] == device_id and (user is None or (x.get("user") or "").lower() == user.lower()))]
            if len(d["devices"]) != n:
                self._save(d)
                return True
        return False

    # --- pairing (state lives in hub/pairing.json so `lemmata hub pair-code` and the running server share one code)
    @property
    def _pfile(self):
        return self.data.hub / "pairing.json"

    def _live(self):
        c = read_json(self._pfile, None)
        if isinstance(c, dict) and c.get("expires", 0) > time.time() and c.get("wrong", 0) < MAX_WRONG and c.get("code"):
            return c
        return None

    def new_code(self):
        with self.lock:
            c = {"code": "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN)), "expires": time.time() + CODE_TTL, "wrong": 0}
            write_private(self._pfile, json.dumps(c))
            return c["code"]

    def current_code(self):
        """The live code, creating one if none is valid."""
        with self.lock:
            c = self._live()
        return c["code"] if c else self.new_code()

    def check_code(self, given):
        """True and consumes the code on a match; a wrong guess counts against the live code."""
        with self.lock:
            c = self._live()
            if not c:
                return False
            given = (given or "").strip().upper().replace("-", "").replace(" ", "")
            if hmac.compare_digest(given.encode(), c["code"].encode()):
                try:
                    self._pfile.unlink()
                except OSError:
                    pass
                return True
            c["wrong"] += 1
            write_private(self._pfile, json.dumps(c))
            return False


def cookie_header(token, max_age=60 * 60 * 24 * 365, secure=False):
    """SameSite=Strict on the private hub. On the public site (https) the cookie is Secure and Lax, so a link to a project
    opened from Slack or e-mail arrives signed in; every state-changing request is still checked against the Origin."""
    if secure:
        return "%s=%s; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=%d" % (COOKIE, token, max_age)
    return "%s=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=%d" % (COOKIE, token, max_age)


def parse_cookie(header):
    for part in (header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE:
            return v
    return None
