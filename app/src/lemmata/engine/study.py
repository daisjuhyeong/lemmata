"""The kind of study a project is (S29, ADR-009).

    method     the work proposes a method of its own ("ours"); experiments rank it against baselines.
    benchmark  the work compares existing methods, datasets or measures to find something out. There is no "ours":
               a claim is decided by its own test (a row of the project's test table), never by a method's rank.

The researcher chooses the kind per project and can change it at any time. Until they do, a confirmed project map
decides (its "study" field, or the fact that it names a method), and before that a rule: a project without a paper
that has a protocol or a findings report is read as a benchmark study, because guessing an "ours" where there is none
puts datasets, test rows and synthetic cases in the list of methods.

Column roles say what a column of a result table names: a method, a dataset, a group of datasets, a condition, a seed.
The defaults are common header names; a confirmed map may name the project's own. Rules only, no language model.
"""
from .errors import BadRequest
from .experiments import norm

SCHEMA = "lemmata.study/1"
KINDS = ("method", "benchmark")
WORDS = {"method": "Method paper", "benchmark": "Benchmark study"}
ROLES = ("method", "condition", "dataset", "group", "seed")     # in the order a column is classified
DEFAULT_ROLES = {
    "method": ("model", "method", "detector", "algorithm", "algo", "approach", "baseline", "learner", "classifier", "system"),
    "condition": ("variant", "condition", "setting", "perturbation", "shuffle", "ablation", "case", "scenario"),
    "dataset": ("dataset", "task", "corpus", "source", "stream", "data"),
    "group": ("group", "suite", "collection", "benchmark", "family", "category", "domain"),
    "seed": ("seed", "run", "trial", "rep", "repeat", "fold"),
}
MAX_COLS = 8


def load(hub):
    d = hub.read_json("study.json", None)
    if not isinstance(d, dict) or d.get("kind") not in KINDS + (None,):
        d = {}
    d.setdefault("schema", SCHEMA)
    d.setdefault("kind", None)
    d.setdefault("at", None)
    return d


def choose(store, kind, at):
    """The researcher's own choice. kind: method | benchmark | auto (auto: forget the choice, let the map or the rule decide)."""
    if kind not in KINDS + ("auto",):
        raise BadRequest("study must be one of %s, or auto" % ", ".join(KINDS))
    store["kind"], store["at"] = (None if kind == "auto" else kind), at
    return store


def resolve(store, confirmed_map, hypothesis_first):
    """-> {kind, by: you | map | rule, why}. Rules Y1-Y4 (ADR-009)."""
    k = (store or {}).get("kind")
    if k in KINDS:
        return {"kind": k, "by": "you", "rule": "Y1", "why": "Set by you."}
    m = confirmed_map or {}
    if m.get("study") in KINDS:
        return {"kind": m["study"], "by": "map", "rule": "Y2", "why": "The confirmed project map says so."}
    if m.get("method"):
        return {"kind": "method", "by": "map", "rule": "Y2", "why": "The confirmed project map names a method of its own (%s)." % m["method"]["name"]}
    if hypothesis_first:
        return {"kind": "benchmark", "by": "rule", "rule": "Y3",
                "why": "No paper and no method of its own named: read as a study that compares existing methods. Change it if the work proposes a method."}
    return {"kind": "method", "by": "rule", "rule": "Y4", "why": "A paper is linked and nothing says otherwise: read as a paper that proposes a method."}


def roles_of(confirmed_map=None):
    """Column names by role: the confirmed map's own first, then the defaults. -> {role: (normalised column names)}"""
    mine = (confirmed_map or {}).get("roles") or {}
    out = {}
    for r in ROLES:
        cols = [norm(c) for c in mine.get(r) or [] if norm(c)]
        out[r] = tuple(dict.fromkeys(cols + [c for c in DEFAULT_ROLES[r] if c not in cols]))
    # a column the map gives one role loses the default role it had under another name list
    for r in ROLES:
        own = {norm(c) for c in mine.get(r) or []}
        for other in ROLES:
            if other != r:
                out[other] = tuple(c for c in out[other] if c not in own)
    return out


def role_of(column, roles):
    """What a column names: method | condition | dataset | group | seed, or "row" when none of them."""
    n = norm(column)
    if not n:
        return "row"
    return next((r for r in ROLES if n in roles.get(r, ())), "row")


def first(keys, roles, role):
    """The first of these columns that has the role, in the role's own order of preference (the map's columns first)."""
    by = {norm(k): k for k in reversed(list(keys))}
    return next((by[c] for c in roles.get(role, ()) if c in by), None)


def clean_roles(doc, known, note):
    """A map's "roles" entry, checked: {role: [column names]}; a column must be a real column of some result file.
    known: normalised names seen in the result files; note(level, where, why)."""
    if doc is None:
        return {}
    if not isinstance(doc, dict):
        note("dropped", "roles", "roles must be an object: {\"method\": [\"model\"], \"dataset\": [\"dataset\", \"source\"], ...}")
        return {}
    out, taken = {}, {}
    for k in sorted(set(doc) - set(ROLES)):
        note("dropped", "roles", "unknown role %r (roles: %s)" % (str(k)[:30], ", ".join(ROLES)))
    for r in ROLES:
        cols = doc.get(r)
        if cols is None:
            continue
        cols = [cols] if isinstance(cols, str) else cols if isinstance(cols, list) else []
        keep = []
        for c in cols[:MAX_COLS]:
            if not isinstance(c, str) or not c.strip():
                continue
            c = c.strip()[:60]
            if norm(c) not in known:
                note("dropped", "roles", "%r is not a column of any result file" % c)
            elif norm(c) in taken:
                note("dropped", "roles", "%r is already the %s column" % (c, taken[norm(c)]))
            else:
                taken[norm(c)] = r
                keep.append(c)
        if keep:
            out[r] = keep
    return out
