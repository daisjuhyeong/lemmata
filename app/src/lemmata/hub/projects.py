"""Hub projects: clone, paper zip ingest, sync, trash. All git runs without hooks and never executes repo content."""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from lemmata.engine.errors import BadRequest, NotFound
from lemmata.server import App

from .config import read_json
from .github import git_auth_header, scrub

MAX_ZIP = 100 * 1024 * 1024
MAX_FILES = 5000
MAX_UNPACKED = 500 * 1024 * 1024
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
AUTHOR = {"GIT_AUTHOR_NAME": "Lemmata", "GIT_AUTHOR_EMAIL": "lemmata@localhost",
          "GIT_COMMITTER_NAME": "Lemmata", "GIT_COMMITTER_EMAIL": "lemmata@localhost"}
ALLOWED_PROTOCOLS = ["https"]  # tests (local fake GitHub over http) extend this; production never speaks http/ssh/file
PID_RE = re.compile(r"^[a-z0-9-]{1,64}$")
CODE_REPO_RE = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")


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


class ProjectError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def git(cwd, args, token=None, scope_url=None, extra_env=None, timeout=900):
    """Run git hardened: no hooks, no symlink checkout, no submodules, only the allowed protocols, no user/system config.
    The token travels only in the child's environment (GIT_CONFIG_*), scoped to the GitHub URL, never in argv,
    .git/config or logs; stderr is scrubbed before it can reach a caller."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_LFS_SKIP_SMUDGE": "1",
                "GIT_OPTIONAL_LOCKS": "0", "GIT_ASKPASS": "/bin/false", "SSH_ASKPASS": "/bin/false"})
    if token:
        base = (scope_url or "").rstrip("/") + "/"
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.%s.extraHeader" % base, "GIT_CONFIG_VALUE_0": git_auth_header(token)})
    env.update(extra_env or {})
    try:
        p = subprocess.run(["git"] + safe_flags(scope_url) + list(args), cwd=str(cwd) if cwd else None, env=env, capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ProjectError(504, "git_timeout", "git timed out")
    except OSError as e:
        raise ProjectError(500, "git_missing", "git could not run: %s" % scrub(e, token))
    if p.returncode != 0:
        msg = scrub(p.stderr.decode("utf-8", "replace").strip()[-600:], token)
        raise ProjectError(502, "git_failed", "git %s failed: %s" % (args[0], msg))
    return p.stdout.decode("utf-8", "replace").strip()


def valid_branch(b):
    if not isinstance(b, str) or not BRANCH_RE.match(b) or ".." in b:
        return False
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "check-ref-format", "--branch", b], capture_output=True, env=env, stdin=subprocess.DEVNULL).returncode == 0


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return (s or "project")[:40]


# ---------------------------------------------------------------- zip ingest
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
            if any(p.lower() == ".git" for p in parts):
                raise ProjectError(400, "bad_zip", "The zip contains a .git folder.")
            mode = (i.external_attr >> 16) & 0o170000
            if mode and mode not in (0o100000, 0o040000):
                raise ProjectError(400, "bad_zip", "Links and special files are not allowed: %r" % name[:80])
            if i.flag_bits & 0x1:
                raise ProjectError(400, "bad_zip", "Encrypted zips are not supported.")
            if not parts or parts[-1] == ".DS_Store":
                continue
            entries.append((i, parts, i.is_dir() or norm.endswith("/")))
        seen = set()
        for _i, parts, is_dir in entries:
            key = "/".join(parts).casefold()
            if key in seen and not is_dir:
                raise ProjectError(400, "bad_zip", "Duplicate file names (ignoring case): %r" % "/".join(parts)[:80])
            seen.add(key)
        top = {p[0] for _, p, d in entries}
        if len(top) == 1 and all(len(p) > 1 or d for _, p, d in entries) and any(len(p) > 1 for _, p, _d in entries):
            entries = [(i, p[1:], d) for i, p, d in entries if len(p) > 1 or not d]
        total = files = 0
        for info, parts, is_dir in entries:
            target = (dest.joinpath(*parts)).resolve()
            if target != dest and not target.is_relative_to(dest):
                raise ProjectError(400, "bad_zip", "Path escapes the folder.")
            if is_dir:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_UNPACKED:
                        raise ProjectError(400, "bad_zip", "The zip unpacks to more than 500 MB.")
                    out.write(chunk)
            files += 1
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
        self.apps = {}
        self.mlock = threading.Lock()
        self.oplocks = {}
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
                a = App(Engine(root))
                self.apps[pid] = a
        return a

    def oplock(self, pid):
        with self.mlock:
            return self.oplocks.setdefault(pid, threading.Lock())

    def _scan(self, pid):
        a = self.app(pid)
        with a.lock:
            return a.engine.scan()

    # --- views
    def summary(self, pid):
        m = self.meta(pid)
        a = self.app(pid)
        with a.lock:
            st = a.engine.project()
            al = a.engine.alarms()
        paper = self.root(pid) / "paper"
        try:
            versions = int(git(paper, ["rev-list", "--count", "HEAD"])) if (paper / ".git").exists() else 0
        except ProjectError:
            versions = 0
        return {"id": pid, "name": m.get("name", pid), "code_repo": m.get("code_repo"), "branch": m.get("branch"),
                "paper_versions": versions, "last_sync": m.get("last_sync"), "scanned_at": st.get("scanned_at"),
                "counts": {"recheck": al.get("summary", {}).get("flagged_nodes", 0), "findings": st["counts"]["findings"]}}

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
    def create(self, name, repo, branch):
        if not isinstance(repo, str) or not CODE_REPO_RE.match(repo) or repo.endswith(".git") or ".." in repo:
            raise ProjectError(400, "bad_request", "code_repo must look like owner/name.")
        if branch is not None and not valid_branch(branch):
            raise ProjectError(400, "bad_request", "bad branch name.")
        token = self.gh.token()
        if not token:
            raise ProjectError(409, "not_signed_in", "Sign in with GitHub first.")
        if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > 100):
            raise ProjectError(400, "bad_request", "name must be text up to 100 characters.")
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
            paper.mkdir()
            git(paper, ["init", "-q", "--template=" + str(tpl)])
            git(paper, ["symbolic-ref", "HEAD", "refs/heads/main"])
            (root / ".lemmata").mkdir()
            (root / ".lemmata" / "project.json").write_text(json.dumps({
                "schema": "lemmata.project/1", "name": (name or repo.split("/")[1]).strip(),
                "repos": [{"id": "paper", "role": "paper", "path": "paper"}, {"id": "code", "role": "code", "path": "code"}]},
                indent=1) + "\n", encoding="utf-8")
            meta = {"schema": "lemmata.hubproject/1", "id": pid, "name": (name or repo.split("/")[1]).strip(),
                    "code_repo": repo, "branch": branch or got, "created": now_iso(), "last_sync": now_iso()}
            self._save_meta(pid, meta)
            self._scan(pid)
        except BaseException:
            self.apps.pop(pid, None)
            shutil.rmtree(root, ignore_errors=True)
            raise
        return self.summary(pid)

    # --- paper upload
    def upload(self, pid, zip_path):
        root = self.root(pid)
        paper = root / "paper"
        with self.oplock(pid):
            work = Path(self.data.tmp) / ("up-" + secrets.token_hex(6))
            work.mkdir(mode=0o700)
            try:
                files = safe_extract(zip_path, work)
                a = self.app(pid)
                with a.lock:
                    for child in paper.iterdir():
                        if child.name == ".git":
                            continue
                        shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
                    for child in work.iterdir():
                        shutil.move(str(child), str(paper / child.name))
                    git(paper, ["add", "-A", "-f"])
                    git(paper, ["commit", "-q", "--allow-empty", "--no-verify", "--no-gpg-sign", "-m", "Overleaf upload " + now_iso()],
                        extra_env=AUTHOR)
                    sha = git(paper, ["rev-parse", "HEAD"])
                    version = int(git(paper, ["rev-list", "--count", "HEAD"]))
                    a.engine.scan()
            finally:
                shutil.rmtree(work, ignore_errors=True)
        return {"version": version, "commit": sha, "files": files}

    # --- sync
    def sync(self, pid):
        m = self.meta(pid)
        code = self.root(pid) / "code"
        token = self.gh.token()
        if not token:
            raise ProjectError(409, "not_signed_in", "Sign in with GitHub first.")
        with self.oplock(pid):
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
                if changed:
                    a.engine.scan()
            m["last_sync"] = now_iso()
            self._save_meta(pid, m)
        return {"changed": changed, "head": head}

    def sync_all(self):
        for pid in self.ids():
            try:
                self.sync(pid)
            except Exception as e:
                print("lemmata hub: sync %s failed: %s" % (pid, scrub(str(e), self.gh.token())), flush=True)

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

    def __init__(self, mgr, device=None):
        self.mgr = mgr
        self.device = device
        self.write_lock = mgr.write_lock

    def list_projects(self):
        return self.mgr.list()

    def resolve(self, project):
        pid = self.mgr.resolve(project)
        return pid, LockedEngine(self.mgr.app(pid))

    def sync(self, pid):
        return self.mgr.sync(pid)
