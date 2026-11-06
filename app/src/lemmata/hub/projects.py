"""Hub projects: clone, paper zip ingest, sync, trash. All git runs without hooks and never executes repo content."""
from __future__ import annotations

import json
import os
import unicodedata
import zlib
import re
import secrets
import shutil
import subprocess
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from lemmata.engine.errors import BadRequest, NotFound
from lemmata.server import App

from .config import read_json
from .github import git_auth_header, scrub
from .overleaf import Overleaf, OverleafError, parse_project

MAX_ZIP = 100 * 1024 * 1024
MAX_FILES = 5000
MAX_UNPACKED = 500 * 1024 * 1024
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
AUTHOR = {"GIT_AUTHOR_NAME": "Lemmata", "GIT_AUTHOR_EMAIL": "lemmata@localhost",
          "GIT_COMMITTER_NAME": "Lemmata", "GIT_COMMITTER_EMAIL": "lemmata@localhost"}
ALLOWED_PROTOCOLS = ["https"]  # tests (local fake GitHub over http) extend this; production never speaks http/ssh/file
PID_RE = re.compile(r"^[a-z0-9-]{1,64}$")
CODE_REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/(?!\.{1,2}$)[A-Za-z0-9._][A-Za-z0-9._-]{0,99}$")
MAX_FILE = 50 * 1024 * 1024
SUBDIR_MAX = 200
MASKS = []  # absolute data paths that must never appear in an error message


def mask(text):
    text = str(text)
    for m in sorted(MASKS, key=len, reverse=True):
        text = text.replace(m, "<data>")
    return text


def safe_flags(scope_url=None):
    protos = list(ALLOWED_PROTOCOLS)
    # end-to-end tests against a loopback fake GitHub only: LEMMATA_GIT_ALLOW_HTTP=1 allows http, and only for a loopback github_web
    if os.environ.get("LEMMATA_GIT_ALLOW_HTTP") == "1" and (scope_url or "").startswith(("http://127.0.0.1", "http://localhost")):
        protos.append("http")
    f = ["core.hooksPath=/dev/null", "core.symlinks=false", "protocol.allow=never", "http.followRedirects=false",
         "credential.helper=", "submodule.recurse=false", "core.quotepath=false", "core.fsmonitor=false"]
    f += ["protocol.%s.allow=always" % p for p in protos]
    out = []
    for x in f:
        out += ["-c", x]
    return out


def todo_changes(alarms, entries):
    """Rule shared with the UI: 'things to look at' = changes (alarm groups) in which at least one affected node is still not looked at."""
    n = 0
    for g in alarms.get("groups", []):
        ids = [c["node_id"] for c in g["changed"]] + [d["node_id"] for d in g["downstream"]]
        if any((entries.get("node:" + i) or {}).get("effective_state", "unreviewed") == "unreviewed" for i in ids):
            n += 1
    return n


class ProjectError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def git(cwd, args, token=None, scope_url=None, extra_env=None, timeout=900, user="x-access-token"):
    """Run git hardened: no hooks, no symlink checkout, no submodules, only the allowed protocols, no user/system config.
    The token travels only in the child's environment (GIT_CONFIG_*), scoped to the GitHub URL, never in argv,
    .git/config or logs; stderr is scrubbed before it can reach a caller."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_LFS_SKIP_SMUDGE": "1",
                "GIT_OPTIONAL_LOCKS": "0", "GIT_ASKPASS": "/bin/false", "SSH_ASKPASS": "/bin/false"})
    if token:
        base = (scope_url or "").rstrip("/") + "/"
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.%s.extraHeader" % base, "GIT_CONFIG_VALUE_0": git_auth_header(token, user)})
    env.update(extra_env or {})
    try:
        p = subprocess.run(["git"] + safe_flags(scope_url) + list(args), cwd=str(cwd) if cwd else None, env=env, capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ProjectError(504, "git_timeout", "git timed out")
    except OSError as e:
        raise ProjectError(500, "git_missing", "git could not run: %s" % scrub(e, token))
    if p.returncode != 0:
        msg = mask(scrub(p.stderr.decode("utf-8", "replace").strip()[-600:], token))
        raise ProjectError(502, "git_failed", "git %s failed: %s" % (args[0], msg))
    return p.stdout.decode("utf-8", "replace").strip()


def _tree_size(path):
    total = 0
    for dp, _dn, fn in os.walk(str(path)):
        for f in fn:
            try:
                total += os.lstat(os.path.join(dp, f)).st_size
            except OSError:
                pass
    return total


def valid_branch(b):
    if not isinstance(b, str) or not BRANCH_RE.match(b) or ".." in b:
        return False
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "check-ref-format", "--branch", b], capture_output=True, env=env, stdin=subprocess.DEVNULL).returncode == 0


def valid_subdir(v):
    """Folder inside the paper repo: relative, forward slashes, no `..`/`.` parts, no leading `-`, no .git alias, <= 200 chars.
    Returns the normalised path (no trailing slash)."""
    bad = ProjectError(400, "bad_request", "paper_subdir must be a relative folder such as paper or docs/paper.")
    if not isinstance(v, str) or not v.strip() or len(v) > SUBDIR_MAX or v != v.strip():
        raise bad
    if v.startswith(("-", "/", "~")) or "\\" in v or re.search(r"[\x00-\x1f\x7f:]", v) or re.match(r"^[A-Za-z]:", v):
        raise bad
    parts = v.split("/")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    if not parts or any(p in ("", ".", "..") or is_git_alias(p) or _has_format_chars(p) for p in parts):
        raise bad
    return "/".join(parts)


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return (s or "project")[:40]


# ---------------------------------------------------------------- zip ingest
def _has_format_chars(s):
    return any(unicodedata.category(c) == "Cf" for c in s)


def is_git_alias(comp):
    """True if a path component could be `.git` on NTFS/HFS+/APFS: NFC/NFKC, format chars dropped, trailing dots/spaces
    stripped, case-folded; also the 8.3 short name git~N."""
    for form in ("NFC", "NFKC"):
        c = unicodedata.normalize(form, comp)
        c = "".join(ch for ch in c if unicodedata.category(ch) != "Cf").rstrip(". ").casefold()
        c = c.lstrip(" ") if c.startswith(" ") else c
        if c == ".git" or re.fullmatch(r"git~\d+", c):
            return True
    return False


def _bad(msg):
    return ProjectError(400, "bad_zip", msg)


def safe_extract(zip_path, dest):
    """Extract an Overleaf zip into the empty folder `dest`. Rejects absolute paths, `..`, symlinks/special files, encrypted
    entries, more than 5,000 files or 500 MB unpacked (counted while writing, not from headers). Strips one top-level folder."""
    dest = Path(dest).resolve()
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError):
        raise ProjectError(400, "bad_zip", "That file is not a valid zip.")
    with zf:
        infos = [i for i in zf.infolist() if not i.filename.startswith("__MACOSX/")]
        if len(infos) > MAX_FILES:
            raise ProjectError(400, "bad_zip", "The zip has more than %d files." % MAX_FILES)
        if sum(i.file_size for i in infos) > MAX_UNPACKED:
            raise ProjectError(400, "bad_zip", "The zip unpacks to more than 500 MB.")
        entries = []
        for i in infos:
            name = i.filename
            if "\x00" in name:
                raise ProjectError(400, "bad_zip", "Unsafe name in zip.")
            if "\\" in name:
                raise ProjectError(400, "bad_zip", "Backslashes in names are not allowed: %r" % name[:80])
            norm = name
            if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
                raise ProjectError(400, "bad_zip", "Absolute path in zip: %r" % name[:80])
            parts = [p for p in norm.split("/") if p not in ("", ".")]
            if ".." in parts:
                raise ProjectError(400, "bad_zip", "Path escapes the folder: %r" % name[:80])
            if any(_has_format_chars(p) for p in parts):
                raise _bad("Invisible formatting characters in a file name are not allowed.")
            if any(is_git_alias(p) for p in parts):
                raise _bad("The zip contains a .git folder.")
            mode = (i.external_attr >> 16) & 0o170000
            if mode and mode not in (0o100000, 0o040000):
                raise ProjectError(400, "bad_zip", "Links and special files are not allowed: %r" % name[:80])
            if i.flag_bits & 0x1:
                raise ProjectError(400, "bad_zip", "Encrypted zips are not supported.")
            if not parts or parts[-1] == ".DS_Store":
                continue
            entries.append((i, parts, i.is_dir() or norm.endswith("/")))
        files_seen, dirs_seen = set(), set()
        for _i, parts, is_dir in entries:
            segs = [unicodedata.normalize("NFC", x).casefold() for x in parts]
            for k in range(1, len(segs) if not is_dir else len(segs) + 1):
                dirs_seen.add("/".join(segs[:k]))
            if not is_dir:
                key = "/".join(segs)
                if key in files_seen:
                    raise _bad("Duplicate file names (ignoring case and accents form): %r" % "/".join(parts)[:80])
                files_seen.add(key)
        if files_seen & dirs_seen:
            raise _bad("A name is used both as a file and as a folder.")
        top = {p[0] for _, p, d in entries}
        if len(top) == 1 and all(len(p) > 1 or d for _, p, d in entries) and any(len(p) > 1 for _, p, _d in entries):
            entries = [(i, p[1:], d) for i, p, d in entries if len(p) > 1 or not d]
        try:
            total = files = 0
            for info, parts, is_dir in entries:
                target = (dest.joinpath(*parts)).resolve()
                if target != dest and not target.is_relative_to(dest):
                    raise ProjectError(400, "bad_zip", "Path escapes the folder.")
                if is_dir:
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                one = 0
                with zf.open(info) as src, open(target, "wb") as out:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        one += len(chunk)
                        if total > MAX_UNPACKED:
                            raise _bad("The zip unpacks to more than 500 MB.")
                        if one > MAX_FILE:
                            raise _bad("A file in the zip is larger than 50 MB.")
                        out.write(chunk)
                files += 1
        except ProjectError:
            raise
        except (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError, ValueError):
            raise _bad("The zip is damaged or its sizes do not match its content.")
        except OSError:
            raise _bad("The zip could not be unpacked (conflicting or unusable file names).")
    return files


# ---------------------------------------------------------------- manager
class LockedEngine:
    """Engine proxy: every call runs under the project's lock (the data-model rule for mutating calls)."""

    def __init__(self, app):
        self._app = app
        self._engine = app.engine

    def __getattr__(self, name):
        attr = getattr(self._engine, name)
        if not callable(attr):
            return attr

        def call(*a, **kw):
            with self._app.lock:
                return attr(*a, **kw)
        return call


class Manager:
    def __init__(self, data, cfg, gh):
        self.data, self.cfg, self.gh = data, cfg, gh
        self.ol = Overleaf(data, cfg)
        self.apps = {}
        self.mlock = threading.Lock()
        self.oplocks = {}
        MASKS.append(str(Path(data.root).resolve()))
        MASKS.append(str(data.root))
        self.write_lock = threading.RLock()

    # --- lookup
    def root(self, pid):
        if not isinstance(pid, str) or not PID_RE.match(pid):
            raise NotFound("unknown project")
        p = self.data.projects / pid
        if not (p / "project.json").is_file():
            raise NotFound("unknown project")
        return p

    def meta(self, pid):
        return read_json(self.root(pid) / "project.json", {}) or {}

    def _save_meta(self, pid, m):
        p = self.data.projects / pid / "project.json"
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(m, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, p)

    def ids(self):
        if not self.data.projects.is_dir():
            return []
        return sorted(d.name for d in self.data.projects.iterdir() if (d / "project.json").is_file())

    def app(self, pid):
        root = self.root(pid)
        with self.mlock:
            a = self.apps.get(pid)
            if a is None:
                from lemmata.engine.api import Engine
                a = App(Engine(root, online=bool((read_json(root / "project.json", {}) or {}).get("online_refs", False))))
                self.apps[pid] = a
        return a

    def oplock(self, pid):
        with self.mlock:
            return self.oplocks.setdefault(pid, threading.Lock())

    def _scan(self, pid):
        a = self.app(pid)
        with a.lock:
            return a.engine.scan()

    def overleaf_on(self):
        return bool(self.cfg.load().get("overleaf_enabled", False))

    def _need_overleaf(self):
        if not self.overleaf_on():
            raise ProjectError(404, "feature_disabled", "Overleaf is switched off.")

    # --- views
    def summary(self, pid):
        m = self.meta(pid)
        a = self.app(pid)
        with a.lock:
            st = a.engine.project()
            al = a.engine.alarms()
            ents = a.engine.triage().get("entries", {})
        paper = self.root(pid) / "paper"
        sub = self.paper_source(m).get("subdir")
        try:
            versions = int(git(paper, ["rev-list", "--count", "HEAD"] + (["--", sub] if sub else []))) if (paper / ".git").exists() else 0
        except ProjectError:
            versions = 0
        return {"id": pid, "name": m.get("name", pid), "paper_source": self.paper_source(m), "online_refs": bool(m.get("online_refs", False)), "code_repo": m.get("code_repo"), "branch": m.get("branch"),
                "paper_versions": versions, "last_sync": m.get("last_sync"), "scanned_at": st.get("scanned_at"),
                "counts": {"recheck": todo_changes(al, ents), "findings": st["counts"]["findings"]}}

    @staticmethod
    def paper_source(m):
        ps = m.get("paper_source")
        if isinstance(ps, dict) and ps.get("kind") == "overleaf" and ps.get("project_id"):
            return {"kind": "overleaf", "project_id": ps["project_id"]}
        if isinstance(ps, dict) and ps.get("kind") == "github" and ps.get("repo"):
            out = {"kind": "github", "repo": ps["repo"], "branch": ps.get("branch")}
            if ps.get("subdir"):
                out["subdir"] = ps["subdir"]
            return out
        return {"kind": "zip"}

    def list(self):
        out = []
        for pid in self.ids():
            try:
                out.append(self.summary(pid))
            except Exception as e:  # one broken project must not hide the others
                out.append({"id": pid, "name": pid, "error": scrub(str(e))[:200], "counts": {"recheck": 0, "findings": 0}})
        return out

    def resolve(self, ref):
        """pid, project name, GitHub repo or repo short name. An exact pid wins; an ambiguous name is a BadRequest."""
        ref_l = (ref or "").strip().lower()
        if PID_RE.match(ref_l) and (self.data.projects / ref_l / "project.json").is_file():
            return ref_l
        hits = []
        for pid in self.ids():
            m = self.meta(pid)
            repo = (m.get("code_repo") or "").lower()
            if ref_l in ((m.get("name") or "").lower(), repo, repo.split("/")[-1]):
                hits.append(pid)
        if len(hits) > 1:
            raise BadRequest("%r matches several projects (%s); use the project id." % (ref, ", ".join(hits)))
        if not hits:
            raise NotFound("unknown project %r" % ref)
        return hits[0]

    # --- create
    def create(self, name, repo, branch, paper_overleaf=None, paper_repo=None, paper_branch=None, paper_subdir=None):
        if not isinstance(repo, str) or not CODE_REPO_RE.match(repo) or repo.endswith(".git") or ".." in repo:
            raise ProjectError(400, "bad_request", "code_repo must look like owner/name.")
        if branch is not None and not valid_branch(branch):
            raise ProjectError(400, "bad_request", "bad branch name.")
        token = self.gh.token()
        if not token:
            raise ProjectError(409, "not_signed_in", "Sign in with GitHub first.")
        if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > 100):
            raise ProjectError(400, "bad_request", "name must be text up to 100 characters.")
        gh_src = None
        if paper_repo not in (None, ""):
            gh_src = self._check_github_source(paper_repo, paper_branch, paper_subdir)
        elif paper_branch not in (None, "") or paper_subdir not in (None, ""):
            raise ProjectError(400, "bad_request", "paper_branch and paper_subdir need paper_repo.")
        ol_id = None
        if paper_overleaf not in (None, ""):
            if gh_src:
                raise ProjectError(400, "bad_request", "Give either paper_repo or paper_overleaf, not both.")
            self._need_overleaf()
            ol_id = parse_project(paper_overleaf)  # OverleafError -> 400
            if not self.ol.token():
                raise ProjectError(409, "overleaf_token_missing", "Save your Overleaf Git token on the hub page first.")
        pid = "%s-%s" % (slug(repo.split("/")[1]), secrets.token_hex(2))
        root = self.data.projects / pid
        root.mkdir(parents=True)
        try:
            web = self.cfg.load()["github_web"].rstrip("/")
            url = web + "/" + repo + ".git"
            tpl = self.data.hub / "empty-template"
            tpl.mkdir(mode=0o700, exist_ok=True)
            args = ["clone", "--depth", "1000", "--no-tags", "--no-recurse-submodules", "--template=" + str(tpl)]
            if branch:
                args += ["--branch", branch]
            git(None, args + ["--", url, str(root / "code")], token=token, scope_url=web)
            got = git(root / "code", ["rev-parse", "--abbrev-ref", "HEAD"])
            paper = root / "paper"
            if ol_id:
                self._overleaf_clone(ol_id, paper)
            elif gh_src:
                gh_src = self._github_clone(gh_src, paper, token, web)
            else:
                paper.mkdir()
                git(paper, ["init", "-q", "--template=" + str(tpl)])
                git(paper, ["symbolic-ref", "HEAD", "refs/heads/main"])
            (root / ".lemmata").mkdir()
            (root / ".lemmata" / "project.json").write_text(json.dumps({
                "schema": "lemmata.project/1", "name": (name or repo.split("/")[1]).strip(),
                "repos": [self._paper_entry(gh_src.get("subdir") if gh_src else None), {"id": "code", "role": "code", "path": "code"}]},
                indent=1) + "\n", encoding="utf-8")
            meta = {"schema": "lemmata.hubproject/1", "id": pid, "name": (name or repo.split("/")[1]).strip(),
                    "code_repo": repo, "branch": branch or got, "created": now_iso(), "last_sync": now_iso(),
                    "paper_source": {"kind": "overleaf", "project_id": ol_id} if ol_id else (gh_src or {"kind": "zip"})}
            if ol_id:
                meta["overleaf_last_fetch"] = time.time()
            self._save_meta(pid, meta)
            self._scan(pid)
        except BaseException:
            self.apps.pop(pid, None)
            shutil.rmtree(root, ignore_errors=True)
            raise
        return self.summary(pid)

    # --- paper upload
    def upload(self, pid, zip_path):
        """Atomic: the zip is unpacked and committed through a throw-away index first; paper/ is only touched once the new
        commit exists, and is restored from a backup if the swap itself fails."""
        root = self.root(pid)
        paper = root / "paper"
        kind = self.paper_source(self.meta(pid))["kind"]
        if kind == "overleaf":
            raise ProjectError(409, "paper_is_overleaf", "This project's paper comes from Overleaf; switch it back to a zip first.")
        if kind == "github":
            raise ProjectError(409, "paper_is_github", "This project's paper comes from a GitHub repo; push your changes there, or switch the paper source to a zip first.")
        with self.oplock(pid):
            work = Path(self.data.tmp) / ("up-" + secrets.token_hex(6))
            backup = Path(self.data.tmp) / ("bk-" + secrets.token_hex(6))
            work.mkdir(mode=0o700)
            try:
                files = safe_extract(zip_path, work)
                a = self.app(pid)
                gd = str(paper / ".git")
                idx = Path(self.data.tmp) / ("idx-" + secrets.token_hex(6))
                try:
                    env = dict(AUTHOR, GIT_DIR=gd, GIT_WORK_TREE=str(work), GIT_INDEX_FILE=str(idx))
                    try:
                        git(work, ["add", "-A", "-f"], extra_env=env)
                        tree = git(work, ["write-tree"], extra_env=env)
                    except ProjectError as e:
                        raise ProjectError(400, "bad_zip", "The zip contains a file name git cannot store.")
                    with a.lock:
                        parent = None
                        try:
                            parent = git(paper, ["rev-parse", "-q", "--verify", "HEAD"])
                        except ProjectError:
                            pass
                        args = ["commit-tree", tree, "-m", "Overleaf upload " + now_iso()] + (["-p", parent] if parent else [])
                        sha = git(paper, args, extra_env=AUTHOR)
                        backup.mkdir(mode=0o700)
                        moved = []
                        try:
                            for child in list(paper.iterdir()):
                                if child.name != ".git":
                                    shutil.move(str(child), str(backup / child.name))
                                    moved.append(child.name)
                            for child in work.iterdir():
                                shutil.move(str(child), str(paper / child.name))
                            git(paper, ["update-ref", "-m", "overleaf upload", "HEAD", sha])
                            git(paper, ["reset", "-q"])
                        except BaseException:
                            for child in list(paper.iterdir()):
                                if child.name != ".git":
                                    shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink()
                            for name in moved:
                                shutil.move(str(backup / name), str(paper / name))
                            if parent:
                                git(paper, ["reset", "-q"])
                            raise
                        version = int(git(paper, ["rev-list", "--count", "HEAD"]))
                        a.engine.scan()
                finally:
                    try:
                        idx.unlink()
                    except OSError:
                        pass
            finally:
                shutil.rmtree(work, ignore_errors=True)
                shutil.rmtree(backup, ignore_errors=True)
        return {"version": version, "commit": sha, "files": files}

    # --- Overleaf
    def _overleaf_git(self, cwd, args, token, timeout=300):
        """git against Overleaf: the token only in the child's environment, errors mapped to short API messages, and a time
        cap (plus a stall cap: under 1 kB/s for 30 s aborts)."""
        try:
            return git(cwd, ["-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=30"] + list(args), token=token,
                       scope_url=self.ol.base(), user="git", timeout=timeout)
        except ProjectError as e:
            if e.code == "git_timeout":
                raise ProjectError(504, "overleaf_unavailable", "Overleaf did not answer in time; will retry at the next sync.")
            if e.code != "git_failed":
                raise
            t = e.message.lower()
            if re.search(r"returned error: 429\b", t) or "too many requests" in t:
                raise ProjectError(429, "overleaf_rate_limited", "Overleaf is rate-limiting; will retry at the next sync.")
            if re.search(r"returned error: 5\d\d\b", t) or "unable to access" in t or "could not resolve" in t or "failed to connect" in t or "timed out" in t:
                raise ProjectError(502, "overleaf_unavailable", "Overleaf is not reachable right now; will retry at the next sync.")
            if re.search(r"returned error: 40[13]\b", t) or any(k in t for k in ("authentication failed", "terminal prompts disabled", "could not read username", "invalid credentials")):
                raise ProjectError(502, "overleaf_auth_failed", "Overleaf token missing or expired, or the project isn't yours/shared.")
            if re.search(r"returned error: 404\b", t) or "not found" in t or "does not exist" in t:
                raise ProjectError(404, "overleaf_not_found", "Overleaf has no project with that id.")
            raise

    def _overleaf_clone(self, project_id, dest):
        token = self.ol.token()
        if not token:
            raise ProjectError(409, "overleaf_token_missing", "Save your Overleaf Git token on the hub page first.")
        tpl = self.data.hub / "empty-template"
        tpl.mkdir(mode=0o700, exist_ok=True)
        self._overleaf_git(None, ["clone", "--no-tags", "--no-recurse-submodules", "--template=" + str(tpl), "--", self.ol.url(project_id), str(dest)], token)
        if _tree_size(dest) > MAX_UNPACKED:
            shutil.rmtree(dest, ignore_errors=True)
            raise ProjectError(413, "overleaf_too_large", "The Overleaf project is larger than 500 MB.")
        return git(dest, ["rev-parse", "HEAD"])

    # --- GitHub paper source
    @staticmethod
    def _check_github_source(repo, branch, subdir):
        """Validated {"kind":"github","repo","branch","subdir"?}; branch None means the repo's default branch (filled in at clone)."""
        if not isinstance(repo, str) or not CODE_REPO_RE.match(repo) or repo.endswith(".git") or ".." in repo:
            raise ProjectError(400, "bad_request", "paper_repo must look like owner/name.")
        if branch not in (None, "") and not valid_branch(branch):
            raise ProjectError(400, "bad_request", "bad paper_branch name.")
        src = {"kind": "github", "repo": repo, "branch": branch or None}
        if subdir not in (None, ""):
            src["subdir"] = valid_subdir(subdir)
        return src

    def _github_clone(self, src, dest, token, web):
        """Hardened clone of the paper repo into `dest` (never the code clone). Fills in the real branch. A `subdir` that is not
        a folder of the clone removes it again and answers 400 paper_subdir_missing."""
        tpl = self.data.hub / "empty-template"
        tpl.mkdir(mode=0o700, exist_ok=True)
        args = ["clone", "--depth", "1000", "--no-tags", "--no-recurse-submodules", "--template=" + str(tpl)]
        if src.get("branch"):
            args += ["--branch", src["branch"]]
        try:
            git(None, args + ["--", web + "/" + src["repo"] + ".git", str(dest)], token=token, scope_url=web)
        except ProjectError as e:
            shutil.rmtree(dest, ignore_errors=True)
            t = e.message.lower()
            if e.code == "git_failed" and "remote branch" in t:
                raise ProjectError(404, "paper_branch_not_found", "The paper repo has no branch %r." % src.get("branch"))
            if e.code == "git_failed" and ("not found" in t or "returned error: 40" in t or "authentication failed" in t or "terminal prompts disabled" in t):
                raise ProjectError(404, "paper_repo_not_found", "GitHub has no repo %s that your account can read." % src["repo"])
            raise
        out = dict(src)
        try:
            if _tree_size(dest) > MAX_UNPACKED:
                raise ProjectError(413, "paper_too_large", "The paper repo is larger than 500 MB.")
            out["branch"] = git(dest, ["rev-parse", "--abbrev-ref", "HEAD"])
            sub = src.get("subdir")
            if sub:
                d = (Path(dest) / sub).resolve()
                if not d.is_dir() or not d.is_relative_to(Path(dest).resolve()) or (d == Path(dest).resolve()):
                    raise ProjectError(400, "paper_subdir_missing", "The folder %r does not exist in %s (branch %s)." % (sub, src["repo"], out["branch"]))
        except BaseException:
            shutil.rmtree(dest, ignore_errors=True)
            raise
        return out

    @staticmethod
    def _paper_entry(subdir):
        e = {"id": "paper", "role": "paper", "path": "paper/" + subdir if subdir else "paper"}
        if subdir:
            e["git_subdir"] = True  # engine: this folder lives inside the clone paper/; use that clone's history, filtered to it
        return e

    def _set_manifest_paper(self, pid, subdir):
        p = self.root(pid) / ".lemmata" / "project.json"
        man = read_json(p, {}) or {}
        man["repos"] = [self._paper_entry(subdir) if r.get("id") == "paper" else r for r in man.get("repos", [])]
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, p)

    def _swap_paper(self, pid, new_dir, source, subdir=None, set_meta=None, drop_meta=()):
        """Atomic switch (caller holds the project's oplock): old paper/ is kept as paper.prev-<time>, `new_dir` becomes paper/,
        manifest path and project.json follow; rolled back if any step fails. Then rescan."""
        root = self.root(pid)
        paper = root / "paper"
        a = self.app(pid)
        with a.lock:
            m = self.meta(pid)
            old_meta = json.loads(json.dumps(m))
            man_path = root / ".lemmata" / "project.json"
            old_man = man_path.read_bytes()
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            prev = root / ("paper.prev-" + stamp)
            n = 1
            while prev.exists():
                n += 1
                prev = root / ("paper.prev-%s-%d" % (stamp, n))
            os.rename(paper, prev)
            try:
                os.rename(new_dir, paper)
                self._set_manifest_paper(pid, subdir)
                m["paper_source"] = source
                for k in drop_meta:
                    m.pop(k, None)
                m.update(set_meta or {})
                self._save_meta(pid, m)
            except BaseException:
                if paper.exists():
                    os.rename(paper, new_dir)
                os.rename(prev, paper)
                man_path.write_bytes(old_man)
                self._save_meta(pid, old_meta)
                raise
            a.engine.scan()

    def set_paper_source(self, pid, kind, project=None, repo=None, branch=None, subdir=None):
        root = self.root(pid)
        if kind not in ("github", "overleaf", "zip"):
            raise ProjectError(400, "bad_request", 'kind must be "github", "overleaf" or "zip".')
        if kind == "overleaf":
            self._need_overleaf()
        pid_ol = parse_project(project) if kind == "overleaf" else None
        src = self._check_github_source(repo, branch, subdir) if kind == "github" else None
        paper = root / "paper"
        with self.oplock(pid):
            m = self.meta(pid)
            clone = Path(self.data.tmp) / ("pp-" + secrets.token_hex(6))
            try:
                if kind == "github":
                    token = self.gh.token()
                    if not token:
                        raise ProjectError(409, "not_signed_in", "Sign in with GitHub first.")
                    got = self._github_clone(src, clone, token, self.cfg.load()["github_web"].rstrip("/"))
                    self._swap_paper(pid, clone, got, got.get("subdir"), drop_meta=("overleaf_last_fetch",))
                elif kind == "overleaf":
                    if not self.ol.token():
                        raise ProjectError(409, "overleaf_token_missing", "Save your Overleaf Git token on the hub page first.")
                    self._overleaf_clone(pid_ol, clone)
                    self._swap_paper(pid, clone, {"kind": "overleaf", "project_id": pid_ol}, None, set_meta={"overleaf_last_fetch": time.time()})
                else:
                    cur = self.paper_source(m)
                    if cur["kind"] != "zip":
                        if cur.get("subdir"):
                            self._import_subdir(paper / cur["subdir"], clone, cur)
                            self._swap_paper(pid, clone, {"kind": "zip"}, None, drop_meta=("overleaf_last_fetch",))
                        else:
                            with self.app(pid).lock:
                                try:
                                    git(paper, ["remote", "remove", "origin"])
                                except ProjectError:
                                    pass
                                m["paper_source"] = {"kind": "zip"}
                                m.pop("overleaf_last_fetch", None)
                                self._save_meta(pid, m)
                                self.app(pid).engine.scan()
            finally:
                shutil.rmtree(clone, ignore_errors=True)
            m = self.meta(pid)
        src = self.paper_source(m)
        out = dict(src)
        if "branch" in out and out["branch"] is None:
            out.pop("branch")
        out["head"] = git(paper, ["rev-parse", "HEAD"])
        out["versions"] = int(git(paper, ["rev-list", "--count", "HEAD"] + (["--", src["subdir"]] if src.get("subdir") else [])))
        return out

    def _import_subdir(self, folder, dest, cur):
        """Zip fallback from a subfolder source: the folder's files become a fresh one-commit paper repo (the shared clone is
        not a zip-style repo)."""
        tpl = self.data.hub / "empty-template"
        tpl.mkdir(mode=0o700, exist_ok=True)
        shutil.copytree(str(folder), str(dest), symlinks=True)
        git(dest, ["init", "-q", "--template=" + str(tpl)])
        git(dest, ["symbolic-ref", "HEAD", "refs/heads/main"])
        git(dest, ["add", "-A", "-f"], extra_env=AUTHOR)
        git(dest, ["commit", "-q", "--allow-empty", "-m", "Imported from %s/%s" % (cur["repo"], cur["subdir"])], extra_env=AUTHOR)

    # --- sync
    def sync(self, pid):
        self.root(pid)
        code = self.root(pid) / "code"
        paper = self.root(pid) / "paper"
        token = self.gh.token()
        if not token:
            raise ProjectError(409, "not_signed_in", "Sign in with GitHub first.")
        with self.oplock(pid):
            m = self.meta(pid)  # read under the project lock: the throttle check-and-set below is atomic
            before = git(code, ["rev-parse", "HEAD"])
            git(code, ["fetch", "--no-tags", "origin", m["branch"]], token=token, scope_url=self.cfg.load()["github_web"])
            a = self.app(pid)
            with a.lock:
                try:
                    git(code, ["merge", "--ff-only", "-q", "FETCH_HEAD"])
                except ProjectError:
                    raise ProjectError(409, "not_fast_forward", "The branch was rewritten on GitHub; delete and re-add the project to re-clone it.")
                head = git(code, ["rev-parse", "HEAD"])
                changed = head != before
            pp = self._sync_paper(pid, m, paper, a, token)
            with a.lock:
                if changed or pp["changed"]:
                    a.engine.scan()
            m["last_sync"] = now_iso()
            self._save_meta(pid, m)
        return {"changed": changed, "head": head, "code": {"changed": changed, "head": head}, "paper": pp}

    def _sync_github_paper(self, m, paper, a, res, token, head):
        src = self.paper_source(m)
        web = self.cfg.load()["github_web"]
        try:
            git(paper, ["fetch", "--no-tags", "origin", src["branch"]], token=token, scope_url=web)
            if _tree_size(paper / ".git") > 2 * MAX_UNPACKED:
                raise ProjectError(413, "paper_too_large", "The paper repo history is larger than 1 GB; not merged.")
            if src.get("subdir"):
                try:
                    git(paper, ["cat-file", "-e", "FETCH_HEAD:" + src["subdir"]])
                except ProjectError:
                    raise ProjectError(400, "paper_subdir_missing", "The folder %r no longer exists on GitHub; not merged." % src["subdir"])
            with a.lock:
                try:
                    git(paper, ["merge", "--ff-only", "-q", "FETCH_HEAD"])
                except ProjectError:
                    raise ProjectError(409, "not_fast_forward", "The paper branch was rewritten on GitHub; connect the paper again.")
            res["head"] = head()
            res["changed"] = res["head"] != res.get("_before")
        except ProjectError as e:
            res["error"] = {"code": e.code, "message": e.message}
        res.pop("_before", None)
        return res

    def _sync_paper(self, pid, m, paper, a, gh_token=None):
        """Fetch the Overleaf paper repo (never push); at most once per overleaf_min_interval seconds per project. Errors are
        reported in the result, they never abort the code sync. Mutates `m` (last fetch time); the caller saves it."""
        def head():
            try:
                return git(paper, ["rev-parse", "HEAD"])
            except ProjectError:
                return None
        before = head()
        res = {"changed": False, "head": before, "source": self.paper_source(m)["kind"]}
        if res["source"] == "github":
            res["_before"] = before
            return self._sync_github_paper(m, paper, a, res, gh_token, head)
        if res["source"] != "overleaf":
            return res
        if not self.overleaf_on():
            res["skipped"] = "feature_disabled"  # Overleaf is switched off: never contacted
            return res
        gap = float(self.cfg.load().get("overleaf_min_interval", 120))
        if time.time() - float(m.get("overleaf_last_fetch") or 0) < gap:
            res["skipped"] = "rate_limited"
            return res
        token = self.ol.token()
        if not token:
            res["error"] = {"code": "overleaf_token_missing", "message": "Save your Overleaf Git token on the hub page first."}
            return res
        m["overleaf_last_fetch"] = time.time()
        try:
            self._overleaf_git(paper, ["fetch", "--no-tags", "origin", "HEAD"], token, timeout=120)
            if _tree_size(paper / ".git") > 2 * MAX_UNPACKED:
                raise ProjectError(413, "overleaf_too_large", "The Overleaf paper history is larger than 1 GB; not merged.")
            with a.lock:
                try:
                    git(paper, ["merge", "--ff-only", "-q", "FETCH_HEAD"])
                except ProjectError:
                    raise ProjectError(409, "not_fast_forward", "The Overleaf history was rewritten; connect the project again.")
            res["head"] = head()
            res["changed"] = res["head"] != before
        except ProjectError as e:
            res["error"] = {"code": e.code, "message": e.message}
        return res

    def sync_all(self):
        for pid in self.ids():
            try:
                self.sync(pid)
            except Exception as e:
                print("lemmata hub: sync %s failed: %s" % (pid, scrub(str(e), self.gh.token(), self.ol.token())), flush=True)

    def set_online_refs(self, pid, value):
        if not isinstance(value, bool):
            raise ProjectError(400, "bad_request", "online_refs must be true or false.")
        a = self.app(pid)
        with self.oplock(pid):
            m = self.meta(pid)
            m["online_refs"] = value
            self._save_meta(pid, m)
            with a.lock:
                a.engine.online = value
                a.engine.scan()
        return self.summary(pid)

    # --- delete
    def delete(self, pid):
        root = self.root(pid)
        with self.oplock(pid):
            dest = self.data.trash / ("%s-%s" % (pid, datetime.now().strftime("%Y%m%d-%H%M%S")))
            shutil.move(str(root), str(dest))
            self.apps.pop(pid, None)
        return {"ok": True, "trashed": dest.name}


class HubContext:
    """The interface lemmata.mcp expects (S04 brief)."""

    def __init__(self, mgr, device=None, device_id=None):
        self.mgr = mgr
        self.device = device
        self.device_id = device_id
        self.write_lock = mgr.write_lock

    def list_projects(self):
        return self.mgr.list()

    def resolve(self, project):
        pid = self.mgr.resolve(project)
        return pid, LockedEngine(self.mgr.app(pid))

    def sync(self, pid):
        return self.mgr.sync(pid)
