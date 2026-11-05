"""Overleaf as a paper source: token store, project-id parsing and the allowed git host. The token is handled like the GitHub
token (0600 from creation, only in the git child's environment, scrubbed from every message); Lemmata never pushes to Overleaf."""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from .config import read_json, write_private

OVERLEAF_HOST = "https://git.overleaf.com"
ID_RE = re.compile(r"^[0-9a-f]{24}$")
SHARE_MSG = "Use the project link from your Overleaf dashboard, not a share link."
BAD_ID_MSG = "That is not an Overleaf project: paste https://www.overleaf.com/project/<24-character id> or the id itself."


class OverleafError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def parse_project(value):
    """Project id from a `https://www.overleaf.com/project/<24hex>` URL or a bare 24-hex id; share links are refused."""
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise OverleafError(400, "bad_request", BAD_ID_MSG)
    v = value.strip()
    if ID_RE.match(v.lower()):
        return v.lower()
    if "://" not in v and v.startswith(("www.overleaf.com/", "overleaf.com/")):
        v = "https://" + v
    u = urlsplit(v)
    host = (u.hostname or "").lower()
    if u.scheme != "https" or u.username or u.password or u.port not in (None, 443) or host not in ("www.overleaf.com", "overleaf.com"):
        raise OverleafError(400, "bad_request", BAD_ID_MSG)
    parts = [x for x in u.path.split("/") if x]
    if parts and parts[0] == "read":
        raise OverleafError(400, "bad_request", SHARE_MSG)
    if len(parts) >= 2 and parts[0] == "project" and ID_RE.match(parts[1].lower()):
        return parts[1].lower()
    raise OverleafError(400, "bad_request", BAD_ID_MSG)


class Overleaf:
    def __init__(self, data, cfg):
        self.data, self.cfg = data, cfg

    def token(self):
        d = read_json(self.data.overleaf_path, None)
        t = d.get("token") if isinstance(d, dict) else None
        return t if isinstance(t, str) and t else None

    def configured(self):
        return bool(self.token())

    def save(self, token):
        if not isinstance(token, str) or not token.strip() or len(token.strip()) > 300 or re.search(r"\s|[\x00-\x1f\x7f]", token.strip()):
            raise OverleafError(400, "bad_request", "token must be the Git authentication token text (no spaces).")
        write_private(self.data.overleaf_path, json.dumps({"token": token.strip()}) + "\n")

    def remove(self):
        try:
            self.data.overleaf_path.unlink()
        except FileNotFoundError:
            pass

    def base(self):
        """https://git.overleaf.com, or (tests) a loopback URL set in config; anything else is ignored."""
        b = str(self.cfg.load().get("overleaf_git") or OVERLEAF_HOST).rstrip("/")
        if b == OVERLEAF_HOST or (urlsplit(b).hostname or "") in ("127.0.0.1", "localhost"):
            return b
        return OVERLEAF_HOST

    def url(self, project_id):
        return "%s/%s" % (self.base(), project_id)
