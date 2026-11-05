"""Tree interface: WorkTree(root) / GitTree(repo, rev), plus read-only git helpers."""
import hashlib
import os
import subprocess


class GitError(Exception):
    pass


GIT_ENV_EXTRA = {}  # hub mode: GIT_CONFIG_NOSYSTEM / GIT_CONFIG_GLOBAL=/dev/null / GIT_LFS_SKIP_SMUDGE; empty in single-project mode


def run_git(cwd, args, check=True):
    env = dict(os.environ)
    env.update(GIT_ENV_EXTRA)
    env["GIT_OPTIONAL_LOCKS"] = "0"  # read-only: never take index locks
    env["GIT_TERMINAL_PROMPT"] = "0"
    p = subprocess.run(["git", "-c", "core.quotepath=false"] + list(args), cwd=str(cwd),
                       capture_output=True, env=env)
    if check and p.returncode != 0:
        raise GitError("git %s failed: %s" % (" ".join(args), p.stderr.decode("utf-8", "replace").strip()))
    return p


def blob_id_bytes(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def is_git_root(path):
    try:
        p = run_git(path, ["rev-parse", "--show-toplevel"], check=False)
    except OSError:
        return False
    if p.returncode != 0:
        return False
    top = os.path.realpath(p.stdout.decode("utf-8", "replace").strip())
    return top == os.path.realpath(str(path))


def rev_parse(path, rev):
    """Full commit sha for rev, or None."""
    p = run_git(path, ["rev-parse", "--verify", "--quiet", rev + "^{commit}"], check=False)
    if p.returncode != 0:
        return None
    return p.stdout.decode().strip() or None


def head_info(path):
    head = rev_parse(path, "HEAD")
    br = run_git(path, ["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    branch = br.stdout.decode().strip() if br.returncode == 0 else None
    if branch == "HEAD":
        branch = None
    return head, branch


def is_ancestor(path, anc, desc):
    return run_git(path, ["merge-base", "--is-ancestor", anc, desc], check=False).returncode == 0


def status_entries(path):
    """[(status, path)] for uncommitted changes (A/M/D), excluding the hub folder."""
    p = run_git(path, ["status", "--porcelain=v1", "-z", "--untracked-files=all"], check=False)
    if p.returncode != 0:
        return []
    out = []
    parts = p.stdout.decode("utf-8", "replace").split("\0")
    i = 0
    while i < len(parts):
        e = parts[i]
        i += 1
        if len(e) < 4:
            continue
        xy, fp = e[:2], e[3:]
        if xy[0] in "RC":
            i += 1  # skip the "from" path
        if fp.startswith(".lemmata/"):
            continue
        if xy == "??" or "A" in xy:
            st = "A"
        elif "D" in xy:
            st = "D"
        else:
            st = "M"
        out.append((st, fp))
    return out


class WorkTree:
    """The working directory of a repo (git or plain folder)."""

    def __init__(self, root, repo_id):
        self.root = str(root)
        self.repo_id = repo_id
        self.is_git = is_git_root(root)
        self._files = None
        self._blobs = {}

    def list_files(self):
        if self._files is None:
            names = set()
            if self.is_git:
                p = run_git(self.root, ["ls-files", "-z", "--cached", "--others", "--exclude-standard"], check=False)
                names = set(x for x in p.stdout.decode("utf-8", "replace").split("\0") if x)
            else:
                for dp, dns, fns in os.walk(self.root):
                    dns[:] = sorted(d for d in dns if not d.startswith("."))
                    for fn in fns:
                        rel = os.path.relpath(os.path.join(dp, fn), self.root).replace(os.sep, "/")
                        names.add(rel)
            out = []
            for n in names:
                if n.startswith(".lemmata/"):
                    continue
                fp = os.path.join(self.root, n)
                if os.path.isfile(fp) and not os.path.islink(fp):
                    out.append(n)
            self._files = sorted(out)
        return self._files

    def _safe(self, path):
        """Absolute path of `path` inside the repo, or None: no absolute paths, no escape via `..`, no symlinked
        component (a repo symlink or \\input{../..} must never surface files outside the repo)."""
        if not isinstance(path, str) or not path or "\x00" in path or os.path.isabs(path) or path.startswith(("/", "\\")):
            return None
        norm = os.path.normpath(path.replace("\\", "/"))
        if norm == "." or norm == ".." or norm.startswith(".." + os.sep) or os.path.isabs(norm):
            return None
        root = os.path.realpath(self.root)
        full = os.path.join(root, norm)
        if os.path.realpath(full) != full:  # any symlink on the way (or a case/normalisation surprise) is refused
            return None
        return full

    def has(self, path):
        p = self._safe(path)
        return p is not None and os.path.isfile(p)

    def read(self, path):
        p = self._safe(path)
        if p is None:
            return None
        try:
            with open(p, "rb") as f:
                return f.read()
        except OSError:
            return None

    def size(self, path):
        p = self._safe(path)
        if p is None:
            return 0
        try:
            return os.path.getsize(p)
        except OSError:
            return 0

    def blob_id(self, path):
        if path not in self._blobs:
            data = self.read(path)
            self._blobs[path] = blob_id_bytes(data) if data is not None else None
        return self._blobs[path]

    def close(self):
        pass


class GitTree:
    """A repo at a given revision, read through git plumbing (ls-tree, cat-file)."""

    def __init__(self, root, repo_id, rev):
        self.root = str(root)
        self.repo_id = repo_id
        self.rev = rev
        self.is_git = True
        self._ls = None
        self._proc = None

    def _entries(self):
        if self._ls is None:
            p = run_git(self.root, ["ls-tree", "-r", "-l", "-z", self.rev])
            ls = {}
            for rec in p.stdout.decode("utf-8", "replace").split("\0"):
                if not rec or "\t" not in rec:
                    continue
                meta, path = rec.split("\t", 1)
                mode, typ, obj, size = meta.split()
                if typ != "blob" or mode == "120000":
                    continue
                ls[path] = (obj, int(size))
            self._ls = ls
        return self._ls

    def list_files(self):
        return sorted(self._entries())

    def has(self, path):
        return path in self._entries()

    def size(self, path):
        e = self._entries().get(path)
        return e[1] if e else 0

    def blob_id(self, path):
        e = self._entries().get(path)
        return e[0] if e else None

    def read(self, path):
        e = self._entries().get(path)
        if not e:
            return None
        return self._cat(e[0])

    def _cat(self, obj):
        if self._proc is None or self._proc.poll() is not None:
            env = dict(os.environ)
            env.update(GIT_ENV_EXTRA)
            env["GIT_OPTIONAL_LOCKS"] = "0"
            self._proc = subprocess.Popen(["git", "cat-file", "--batch"], cwd=self.root, env=env,
                                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._proc.stdin.write(obj.encode() + b"\n")
        self._proc.stdin.flush()
        header = self._proc.stdout.readline().split()
        if len(header) < 3 or header[1] != b"blob":
            return None
        n = int(header[2])
        data = self._proc.stdout.read(n)
        self._proc.stdout.read(1)
        return data

    def close(self):
        if self._proc is not None:
            try:
                self._proc.stdin.close()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
            try:
                self._proc.stdout.close()
            except Exception:
                pass
            self._proc = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
