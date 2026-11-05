#!/usr/bin/env python3
"""Regenerate app/tests/fixtures/api/*.json and fixtures/files/** (web-eng fixture data).

Hand-built to follow wiki/architecture/data-model.md (ids from section 14). Not the engine's
output: it only lets the UI be developed and tested before (and next to) the real engine.
Usage: python3 build_fixtures.py
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = HERE / "api"
FILES = HERE / "files"

TEX = {
"paper/main.tex": r"""\documentclass{article}
\usepackage{graphicx}
\begin{document}
\title{Tiny Transformers for Forecasting}
\maketitle

\begin{abstract}
We ask whether a small transformer matches larger baselines on forecasting (RQ1) and how sensitive it is to its training settings (RQ2).
\end{abstract}

\section{Introduction}\label{sec:intro}
Attention models are common in forecasting \cite{vaswani2017attention}.
RQ1: does a small model match larger ones? RQ2: how sensitive is it to hyperparameters?

\section{Related work}\label{sec:related}
Attention was introduced by \cite{vaswani2017attention} and refined by \cite{devlin2019bert}.
A recent report \cite{smith2021ghost} disagrees; see also \cite{nobody2020}.

\section{Method}\label{sec:method}
The architecture is shown in Figure~\ref{fig:missing}. We minimise the loss in Eq.~\ref{eq:loss}.
\begin{equation}\label{eq:loss}
\mathcal{L} = \sum_t (y_t - \hat y_t)^2
\end{equation}
\begin{figure}
% generated-by: manual
\includegraphics{figures/arch.pdf}
\caption{Model architecture.}\label{fig:arch}
\end{figure}

\section{Experimental setup}\label{sec:setup}
We train with a learning rate of $3\times10^{-4}$ and batch size 64, using the Adam optimizer.
Details are in Appendix~\ref{app:hparams}.

\section{Results}\label{sec:results}
Table~\ref{tab:main} reports the main results; our model reaches 92.4 F1 on the benchmark.
Figure~\ref{fig:curve} shows training curves and Figure~\ref{fig:qual} shows examples.
\begin{table}
% source: code:results/table2.csv
\caption{Main results.}\label{tab:main}
\begin{tabular}{lr}
Baseline & 0.871 \\
Ours & 0.902 \\
\end{tabular}
\end{table}
\begin{table}
\caption{Ablation.}\label{tab:ablation}
\begin{tabular}{lr}
No attention & 0.842 \\
\end{tabular}
\end{table}
\begin{figure}
% generated-by: code:plot_curve.py
\includegraphics{figures/curve.png}
\caption{Training curves.}\label{fig:curve}
\end{figure}
\begin{figure}
\includegraphics{figures/qual.png}
\caption{Qualitative examples.}\label{fig:qual}
\end{figure}

\section{Conclusion}\label{sec:concl}
A small model is competitive (RQ1) and moderately sensitive to settings (RQ2).

\appendix
\input{appendix}
\bibliography{refs}
\end{document}
""",
"paper/appendix.tex": r"""\section{Extra results}\label{app:extra}
Additional curves are omitted for space.

\section{Hyperparameters}\label{app:hparams}
\begin{tabular}{ll}
Learning rate & $1\times10^{-3}$ \\
Batch size & 128 \\
Optimizer & Adam \\
\end{tabular}
""",
"paper/refs.bib": """@inproceedings{vaswani2017attention,
  title={Attention is all you need},
  year={2017}
}
@inproceedings{devlin2019bert,
  title={BERT: Pre-training of deep bidirectional transformers},
  year={2019}
}
@article{smith2021ghost,
  title={Ghost transformers for time series},
  year={2021}
}
@article{unused2019,
  title={An uncited entry},
  year={2019}
}
""",
"code/train.py": """import yaml
from eval import evaluate


def main(config_path="configs/default.yaml"):
    cfg = yaml.safe_load(open(config_path))
    lr = cfg["learning_rate"]
    print("training with", lr)
    evaluate(cfg)


if __name__ == "__main__":
    main()
""",
"code/eval.py": """# evaluation helpers


def evaluate(cfg):
    return {"f1": 0.902}
""",
"code/plot_curve.py": """import matplotlib.pyplot as plt
from eval import evaluate

plt.plot([1, 2, 3])
plt.savefig("figures/curve.png")
""",
"code/configs/default.yaml": """model: tiny
learning_rate: 1.0e-3
batch_size: 128
optimizer: adam
""",
"code/results/table2.csv": """method,f1
baseline,0.871
ours,0.902
""",
"code/results/metrics.json": '{"f1": 0.902, "baseline": 0.871}\n',
"code/README.md": "# sample code\n\n| Paper | Script |\n|---|---|\n| Fig. 2 | `plot_curve.py` |\n",
}

OLD_CFG = TEX["code/configs/default.yaml"].replace("1.0e-3", "3.0e-4").replace("128", "64")


def sha(s):
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()


def blob(s):
    b = s.encode()
    return "blob:" + hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def L(path, needle, nth=1):
    """(line, text) of the nth line containing needle."""
    n = 0
    for i, ln in enumerate(TEX[path].split("\n"), 1):
        if needle in ln:
            n += 1
            if n == nth:
                return i, ln.rstrip()
    raise SystemExit("needle not found: %s %s" % (path, needle))


def ev(repo_path, needle, role, nth=1):
    repo, path = repo_path.split("/", 1)
    line, text = L(repo_path, needle, nth)
    return {"repo": repo, "path": path, "line": line, "text": text, "role": role, "page": None}


nodes = []
edges = []
LAYER = {}


def node(id, kind, layer, repo, name, detail="", path=None, needle=None, end=None, attrs=None, hash=None):
    loc = {"path": path, "line": None, "end_line": None}
    if path and needle:
        line, _ = L(repo + "/" + path, needle)
        loc["line"] = line
        loc["end_line"] = end
    n = {"id": id, "kind": kind, "layer": layer, "repo": repo, "name": name, "detail": detail,
         "loc": loc, "hash": hash or sha(id), "attrs": attrs or {}}
    nodes.append(n)
    LAYER[id] = layer
    return n


def sec_end(path, start_line):
    lines = TEX[path].split("\n")
    for i in range(start_line, len(lines)):
        if lines[i].startswith("\\section") or lines[i].startswith("\\appendix") or lines[i].startswith("\\bibliography"):
            return i
    return len(lines)


def section(id, name, title, path, label, number, app=False):
    line, _ = L("paper/" + path, "\\label{%s}" % label)
    n = node(id, "section", 2, "paper", name, title, path, "\\label{%s}" % label, sec_end("paper/" + path, line),
             {"tex_label": label, "level": 1, "number": number, "in_appendix": app, "title": title})
    return n


node("thesis", "thesis", 0, "paper", "Thesis", "Tiny transformers can match larger baselines", "main.tex", "\\begin{abstract}", 9,
     {"text": "We ask whether a small transformer matches larger baselines on forecasting"})
node("rq:RQ1", "rq", 1, "paper", "RQ1", "Does a small model match larger ones?", "main.tex", "RQ1: does", None, {"text": "Does a small model match larger ones?"})
node("rq:RQ2", "rq", 1, "paper", "RQ2", "How sensitive is it to hyperparameters?", "main.tex", "RQ1: does", None, {"text": "How sensitive is it to hyperparameters?"})
section("tex:sec:intro", "§1 Introduction", "Introduction", "main.tex", "sec:intro", "1")
section("tex:sec:related", "§2 Related work", "Related work", "main.tex", "sec:related", "2")
section("tex:sec:method", "§3 Method", "Method", "main.tex", "sec:method", "3")
section("tex:sec:setup", "§4 Experimental setup", "Experimental setup", "main.tex", "sec:setup", "4")
section("tex:sec:results", "§5 Results", "Results", "main.tex", "sec:results", "5")
section("tex:sec:concl", "§6 Conclusion", "Conclusion", "main.tex", "sec:concl", "6")
section("tex:app:extra", "App. A Extra results", "Extra results", "appendix.tex", "app:extra", "A", True)
section("tex:app:hparams", "App. B Hyperparameters", "Hyperparameters", "appendix.tex", "app:hparams", "B", True)
node("tex:eq:loss", "equation", 3, "paper", "Eq. 1", "", "main.tex", "\\label{eq:loss}", None, {"tex_label": "eq:loss", "number": "1"})
node("tex:fig:arch", "figure", 3, "paper", "Fig. 1", "Model architecture.", "main.tex", "\\label{fig:arch}", None,
     {"tex_label": "fig:arch", "number": "1", "in_appendix": False, "caption": "Model architecture.", "manual": True, "assets": ["figures/arch.pdf"]})
node("tex:fig:curve", "figure", 3, "paper", "Fig. 2", "Training curves.", "main.tex", "\\label{fig:curve}", None,
     {"tex_label": "fig:curve", "number": "2", "in_appendix": False, "caption": "Training curves.", "manual": False, "assets": ["figures/curve.png"]})
node("tex:fig:qual", "figure", 3, "paper", "Fig. 3", "Qualitative examples.", "main.tex", "\\label{fig:qual}", None,
     {"tex_label": "fig:qual", "number": "3", "in_appendix": False, "caption": "Qualitative examples.", "manual": False, "assets": ["figures/qual.png"]})
node("tex:tab:main", "table", 3, "paper", "Table 2", "Main results.", "main.tex", "\\label{tab:main}", None,
     {"tex_label": "tab:main", "number": "2", "in_appendix": False, "caption": "Main results."})
node("tex:tab:ablation", "table", 3, "paper", "Table 1", "Ablation.", "main.tex", "\\label{tab:ablation}", None,
     {"tex_label": "tab:ablation", "number": "1", "in_appendix": False, "caption": "Ablation."})
node("file:paper/figures/arch.pdf", "asset", 4, "paper", "figures/arch.pdf", "", "figures/arch.pdf", attrs={"size": 18200, "binary": True, "ext": ".pdf"}, hash=blob("arch"))
node("file:paper/figures/curve.png", "asset", 4, "paper", "figures/curve.png", "", "figures/curve.png", attrs={"size": 40200, "binary": True, "ext": ".png"}, hash=blob("curve"))
node("file:paper/figures/qual.png", "asset", 4, "paper", "figures/qual.png", "", "figures/qual.png", attrs={"size": 90100, "binary": True, "ext": ".png"}, hash=blob("qual"))
node("file:code/results/table2.csv", "result", 4, "code", "results/table2.csv", "", "results/table2.csv", attrs={"size": 40, "binary": False, "ext": ".csv"}, hash=blob(TEX["code/results/table2.csv"]))
node("file:code/results/metrics.json", "result", 4, "code", "results/metrics.json", "", "results/metrics.json", attrs={"size": 34, "binary": False, "ext": ".json"}, hash=blob(TEX["code/results/metrics.json"]))
node("run:code/train_main", "run", 5, "code", "run train_main", "python train.py --config configs/default.yaml", "runs/train_main.json",
     attrs={"command": "python train.py --config configs/default.yaml", "started_at": "2026-09-30T14:00:00+09:00"}, hash=blob("run"))
node("file:code/train.py", "code", 6, "code", "train.py", "", "train.py", attrs={"size": 300, "ext": ".py"}, hash=blob(TEX["code/train.py"]))
node("file:code/eval.py", "code", 6, "code", "eval.py", "", "eval.py", attrs={"size": 80, "ext": ".py"}, hash=blob(TEX["code/eval.py"]))
node("file:code/plot_curve.py", "code", 6, "code", "plot_curve.py", "", "plot_curve.py", attrs={"size": 120, "ext": ".py"}, hash=blob(TEX["code/plot_curve.py"]))
node("file:code/configs/default.yaml", "config", 6, "code", "configs/default.yaml", "", "configs/default.yaml", attrs={"size": 70, "ext": ".yaml"}, hash=blob(TEX["code/configs/default.yaml"]))
node("file:code/README.md", "doc", 6, "code", "README.md", "", "README.md", attrs={"size": 90, "ext": ".md"}, hash=blob(TEX["code/README.md"]))
for key, title, year, needle in [
    ("vaswani2017attention", "Attention is all you need", 2017, "@inproceedings{vaswani"),
    ("devlin2019bert", "BERT: Pre-training of deep bidirectional transformers", 2019, "@inproceedings{devlin"),
    ("smith2021ghost", "Ghost transformers for time series", 2021, "@article{smith"),
    ("unused2019", "An uncited entry", 2019, "@article{unused"),
]:
    node("ref:" + key, "reference", None, "paper", "[%s]" % key, title, "refs.bib", needle, None,
         {"bib_key": key, "title": title, "year": year, "doi": None,
          "lookup": "not_found" if key == "smith2021ghost" else "matched"})
# FIX: node() expects path inside repo; refs.bib needle lookup uses paper/refs.bib
PROP = {"includes", "generated_by", "traces_to", "produced_by", "executes", "reads", "imports"}


def edge(frm, kind, to, evid=None, status="detected", reason=None):
    prop = (kind in PROP or (kind == "value_match" and status == "approved")) and status in ("detected", "approved")
    edges.append({"id": "%s|%s|%s" % (frm, kind, to), "from": frm, "to": to, "kind": kind, "status": status,
                  "propagates": prop, "evidence": evid or [], "reason": reason})


def st(path, needle, role="structure", nth=1):
    return [ev(path, needle, role, nth)]


for r in ("rq:RQ1", "rq:RQ2"):
    edge("thesis", "contains", r, st("paper/main.tex", "RQ1: does"))
for s in ("intro", "related", "method", "setup", "results", "concl"):
    edge("thesis", "contains", "tex:sec:" + s, st("paper/main.tex", "\\label{sec:%s}" % s.replace("concl", "concl")))
edge("thesis", "contains", "tex:app:extra", st("paper/appendix.tex", "\\label{app:extra}"))
edge("thesis", "contains", "tex:app:hparams", st("paper/appendix.tex", "\\label{app:hparams}"))
edge("rq:RQ1", "answers", "tex:sec:results", st("paper/main.tex", "RQ1: does", "mention"))
edge("rq:RQ2", "answers", "tex:app:hparams", st("paper/appendix.tex", "Learning rate", "mention"))
edge("tex:sec:method", "contains", "tex:eq:loss", st("paper/main.tex", "\\label{eq:loss}"))
edge("tex:sec:method", "contains", "tex:fig:arch", st("paper/main.tex", "\\label{fig:arch}"))
for f in ("tab:main", "tab:ablation", "fig:curve", "fig:qual"):
    edge("tex:sec:results", "contains", "tex:" + f, st("paper/main.tex", "\\label{%s}" % f))
edge("tex:sec:results", "refs", "tex:tab:main", st("paper/main.tex", "Table~\\ref{tab:main}", "ref"))
edge("tex:sec:results", "refs", "tex:fig:curve", st("paper/main.tex", "Figure~\\ref{fig:curve}", "ref"))
edge("tex:sec:results", "refs", "tex:fig:qual", st("paper/main.tex", "Figure~\\ref{fig:curve}", "ref"))
edge("tex:sec:method", "refs", "tex:eq:loss", st("paper/main.tex", "Eq.~\\ref{eq:loss}", "ref"))
edge("tex:sec:setup", "refs", "tex:app:hparams", st("paper/main.tex", "Appendix~\\ref{app:hparams}", "ref"))
edge("tex:sec:intro", "cites", "ref:vaswani2017attention", st("paper/main.tex", "\\cite{vaswani2017attention}", "cite"))
edge("tex:sec:related", "cites", "ref:vaswani2017attention", st("paper/main.tex", "\\cite{vaswani2017attention}", "cite", 2))
edge("tex:sec:related", "cites", "ref:devlin2019bert", st("paper/main.tex", "\\cite{devlin2019bert}", "cite"))
edge("tex:sec:related", "cites", "ref:smith2021ghost", st("paper/main.tex", "\\cite{smith2021ghost}", "cite"))
edge("tex:fig:arch", "includes", "file:paper/figures/arch.pdf", st("paper/main.tex", "includegraphics{figures/arch.pdf}", "include"))
edge("tex:fig:curve", "includes", "file:paper/figures/curve.png", st("paper/main.tex", "includegraphics{figures/curve.png}", "include"))
edge("tex:fig:qual", "includes", "file:paper/figures/qual.png", st("paper/main.tex", "includegraphics{figures/qual.png}", "include"))
edge("tex:fig:curve", "generated_by", "file:code/plot_curve.py", st("paper/main.tex", "% generated-by: code:plot_curve.py", "marker"))
edge("tex:tab:main", "traces_to", "file:code/results/table2.csv", st("paper/main.tex", "% source: code:results/table2.csv", "marker"))
edge("file:code/results/table2.csv", "produced_by", "run:code/train_main", [{"repo": "code", "path": "runs/train_main.json", "line": 7, "text": '"outputs": ["results/table2.csv", "results/metrics.json"]', "role": "run_record", "page": None}])
edge("file:code/results/metrics.json", "produced_by", "run:code/train_main", [{"repo": "code", "path": "runs/train_main.json", "line": 7, "text": '"outputs": ["results/table2.csv", "results/metrics.json"]', "role": "run_record", "page": None}])
edge("run:code/train_main", "executes", "file:code/train.py", [{"repo": "code", "path": "runs/train_main.json", "line": 5, "text": '"script": "train.py",', "role": "run_record", "page": None}])
edge("run:code/train_main", "reads", "file:code/configs/default.yaml", [{"repo": "code", "path": "runs/train_main.json", "line": 6, "text": '"inputs": ["configs/default.yaml"],', "role": "run_record", "page": None}])
edge("file:code/train.py", "imports", "file:code/eval.py", [ev("code/train.py", "from eval import", "import")])
edge("file:code/plot_curve.py", "imports", "file:code/eval.py", [ev("code/plot_curve.py", "from eval import", "import")])
edge("file:code/results/table2.csv", "produced_by", "file:code/train.py", [ev("code/train.py", "evaluate(cfg)", "write_call")])
edge("tex:sec:setup", "value_match", "file:code/configs/default.yaml",
     [ev("paper/main.tex", "learning rate of", "main"), ev("code/configs/default.yaml", "learning_rate", "config")],
     "proposed", "learning_rate: paper 3e-4, config 1.0e-3; batch_size: paper 64, config 128")
edge("tex:app:hparams", "value_match", "file:code/configs/default.yaml",
     [ev("paper/appendix.tex", "Learning rate", "appendix"), ev("code/configs/default.yaml", "learning_rate", "config")],
     "proposed", "learning_rate: paper 1e-3, config 1.0e-3; batch_size: paper 128, config 128")
edges.sort(key=lambda e: e["id"])


def ordkey(n):
    return (99 if n["layer"] is None else n["layer"], n["id"])


nodes.sort(key=ordkey)
GRAPH = {"schema": "lemmata.graph/1", "scanned_at": "2026-11-04T15:00:00+09:00", "nodes": nodes, "edges": edges}

# ---- events
def commit(repo, sha12, t, subj, files, after, changed=None, flags=None, cp=False):
    return {"id": "ev:commit:%s:%s" % (repo, sha12), "kind": "commit", "repo": repo, "rev": (sha12 * 4)[:40], "short": sha12[:7],
            "time": t, "subject": subj, "files": [{"path": p, "status": s} for p, s in files],
            "at_checkpoint": cp, "after_checkpoint": after, "changed_nodes": changed, "flags": flags or []}


events = [
    commit("paper", "a1b2c3d4e5f6", "2026-09-20T10:00:00+09:00", "P1 initial draft", [("main.tex", "A"), ("refs.bib", "A")], False),
    commit("code", "b1c2d3e4f5a6", "2026-09-22T10:00:00+09:00", "K1 initial training code", [("train.py", "A"), ("configs/default.yaml", "A")], False),
    commit("paper", "c1d2e3f4a5b6", "2026-09-27T10:00:00+09:00", "P2 add tables and figures", [("main.tex", "M"), ("appendix.tex", "A")], False, cp=True),
    commit("code", "d1e2f3a4b5c6", "2026-09-29T10:00:00+09:00", "K2 add eval and plotting", [("eval.py", "A"), ("plot_curve.py", "A")], False, cp=True),
    {"id": "ev:run:code/train_main", "kind": "run", "repo": "code", "rev": None, "short": "train_main", "time": "2026-09-30T14:00:00+09:00",
     "subject": "run train_main", "files": [{"path": "results/table2.csv", "status": "A"}, {"path": "results/metrics.json", "status": "A"}],
     "at_checkpoint": False, "after_checkpoint": False, "changed_nodes": None, "flags": []},
    commit("code", "9f1c2e7a4b3d", "2026-10-03T10:00:00+09:00", "change learning rate 3e-4 to 1e-3", [("configs/default.yaml", "M")], True, ["file:code/configs/default.yaml"]),
    commit("paper", "2b7e5d1c9a0f", "2026-10-04T09:00:00+09:00", "appendix B: learning rate 1e-3", [("appendix.tex", "M")], True, ["tex:app:hparams"]),
    commit("code", "3c8d1e4f7a2b", "2026-10-05T11:00:00+09:00", "tmp: edit comment in eval.py", [("eval.py", "M")], True, []),
    commit("code", "4d9e2f5a8b3c", "2026-10-05T11:30:00+09:00", "revert eval.py", [("eval.py", "M")], True, []),
]
EVENTS = {"schema": "lemmata.events/1", "events": events}

# ---- findings
def fnd(id, check, sev, title, msg, nodes_, evid, details):
    return {"id": id, "check": check, "severity": sev, "title": title, "message": msg, "nodes": nodes_, "evidence": evid,
            "details": details, "fingerprint": sha(id + "".join(e["text"] for e in evid))}


bib = lambda key: ev("paper/refs.bib", "{%s," % key, "bib_entry")
F = [
    fnd("reference_unmatched/smith2021ghost", "reference_unmatched", "warning", "Reference could not be matched",
        'Reference could not be matched: "Ghost transformers for time series" (smith2021ghost) was not found in OpenAlex or Crossref (lookup 2026-10-01).',
        ["ref:smith2021ghost"], [bib("smith2021ghost")],
        {"lookup": {"status": "not_found", "source": "seed", "checked_at": "2026-10-01T18:00:00+09:00", "match": None}}),
    fnd("main_appendix_mismatch/learning_rate", "main_appendix_mismatch", "warning", "Main text and appendix differ",
        "Learning rate differs between the main text (3e-4, main.tex:%d) and the appendix (1e-3, appendix.tex:%d)." % (L("paper/main.tex", "learning rate of")[0], L("paper/appendix.tex", "Learning rate")[0]),
        ["tex:sec:setup", "tex:app:hparams"], [ev("paper/main.tex", "learning rate of", "main"), ev("paper/appendix.tex", "Learning rate", "appendix")],
        {"name": "learning_rate", "main_value": "3e-4", "appendix_value": "1e-3"}),
    fnd("main_appendix_mismatch/batch_size", "main_appendix_mismatch", "warning", "Main text and appendix differ",
        "Batch size differs between the main text (64, main.tex:%d) and the appendix (128, appendix.tex:%d)." % (L("paper/main.tex", "learning rate of")[0], L("paper/appendix.tex", "Batch size")[0]),
        ["tex:sec:setup", "tex:app:hparams"], [ev("paper/main.tex", "learning rate of", "main"), ev("paper/appendix.tex", "Batch size", "appendix")],
        {"name": "batch_size", "main_value": "64", "appendix_value": "128"}),
    fnd("uncited_reference/unused2019", "uncited_reference", "info", "Reference not cited",
        'Bibliography entry "unused2019" is not cited anywhere in the text.', ["ref:unused2019"], [bib("unused2019")], {}),
    fnd("unreferenced_float/fig:arch", "unreferenced_float", "info", "Figure or table not referenced",
        "Fig. 1 is defined at main.tex:%d but is not referenced in the text." % L("paper/main.tex", "\\label{fig:arch}")[0],
        ["tex:fig:arch"], [ev("paper/main.tex", "\\label{fig:arch}", "label")], {}),
    fnd("unreferenced_float/tab:ablation", "unreferenced_float", "info", "Figure or table not referenced",
        "Table 1 is defined at main.tex:%d but is not referenced in the text." % L("paper/main.tex", "\\label{tab:ablation}")[0],
        ["tex:tab:ablation"], [ev("paper/main.tex", "\\label{tab:ablation}", "label")], {}),
    fnd("undefined_ref/fig:missing", "undefined_ref", "warning", "Reference target not defined",
        "\\ref{fig:missing} at main.tex:%d has no matching \\label." % L("paper/main.tex", "fig:missing")[0],
        ["tex:sec:method"], [ev("paper/main.tex", "fig:missing", "ref")], {"label": "fig:missing"}),
    fnd("undefined_cite/nobody2020", "undefined_cite", "warning", "Citation key not defined",
        "\\cite{nobody2020} at main.tex:%d has no entry in the bibliography." % L("paper/main.tex", "nobody2020")[0],
        ["tex:sec:related"], [ev("paper/main.tex", "nobody2020", "cite")], {"key": "nobody2020"}),
    fnd("untraced_number/tex:sec:results#92.4", "untraced_number", "info", "Number not traced to a result file",
        "The value 92.4 at main.tex:%d was not found in any result file." % L("paper/main.tex", "92.4")[0],
        ["tex:sec:results"], [ev("paper/main.tex", "92.4", "number")], {"value": "92.4"}),
    fnd("figure_without_provenance/tex:fig:qual", "figure_without_provenance", "info", "Figure without provenance",
        "Fig. 3 uses figures/qual.png, but no script that writes this file was found.",
        ["tex:fig:qual"], [ev("paper/main.tex", "\\label{fig:qual}", "label")], {}),
]
ORDER = ["reference_unmatched", "main_appendix_mismatch", "uncited_reference", "unreferenced_float", "undefined_ref", "undefined_cite", "untraced_number", "figure_without_provenance"]
TITLES = {"reference_unmatched": "Reference could not be matched", "main_appendix_mismatch": "Main text and appendix differ",
          "uncited_reference": "Reference not cited", "unreferenced_float": "Figure or table not referenced",
          "undefined_ref": "Reference target not defined", "undefined_cite": "Citation key not defined",
          "untraced_number": "Number not traced to a result file", "figure_without_provenance": "Figure without provenance"}
checks = [{"check": c, "title": TITLES[c], "status": "ran", "count": sum(1 for f in F if f["check"] == c),
           "note": "offline cache: 3 matched, 1 could not be matched, 0 not checked" if c == "reference_unmatched" else ""} for c in ORDER]
FINDINGS = {"schema": "lemmata.findings/1", "checks": checks, "findings": F}

# ---- alarms (state 0)
cfg = "file:code/configs/default.yaml"
ALARMS = {
    "schema": "lemmata.alarms/1", "computed_at": "2026-11-04T15:00:00+09:00",
    "checkpoint": {"id": "cp1", "created_at": "2026-10-01T18:00:00+09:00", "note": "CP1: draft v2 validated"},
    "excluded_repos": [],
    "groups": [
        {"id": "ev:commit:code:9f1c2e7a4b3d", "display": "A1",
         "cause": {"event_id": "ev:commit:code:9f1c2e7a4b3d", "kind": "commit", "repo": "code", "rev": "9f1c2e7a4b3d" * 3 + "9f1c", "short": "9f1c2e7",
                   "time": "2026-10-03T10:00:00+09:00", "subject": "change learning rate 3e-4 to 1e-3", "files": ["configs/default.yaml"]},
         "changed": [{"node_id": cfg, "change": "content_changed", "hash_checkpoint": blob(OLD_CFG), "hash_now": blob(TEX["code/configs/default.yaml"]), "also_changed_in": []}],
         "removed": [],
         "downstream": [
             {"node_id": "run:code/train_main", "depth": 1, "via": "run:code/train_main|reads|" + cfg, "output_identical": None},
             {"node_id": "file:code/results/metrics.json", "depth": 2, "via": "file:code/results/metrics.json|produced_by|run:code/train_main", "output_identical": True},
             {"node_id": "file:code/results/table2.csv", "depth": 2, "via": "file:code/results/table2.csv|produced_by|run:code/train_main", "output_identical": True},
             {"node_id": "tex:tab:main", "depth": 3, "via": "tex:tab:main|traces_to|file:code/results/table2.csv", "output_identical": None},
         ], "flags": []},
        {"id": "ev:commit:paper:2b7e5d1c9a0f", "display": "A2",
         "cause": {"event_id": "ev:commit:paper:2b7e5d1c9a0f", "kind": "commit", "repo": "paper", "rev": "2b7e5d1c9a0f" * 3 + "2b7e", "short": "2b7e5d1",
                   "time": "2026-10-04T09:00:00+09:00", "subject": "appendix B: learning rate 1e-3", "files": ["appendix.tex"]},
         "changed": [{"node_id": "tex:app:hparams", "change": "content_changed", "hash_checkpoint": sha("old-app"), "hash_now": sha("tex:app:hparams"), "also_changed_in": []}],
         "removed": [], "downstream": [], "flags": []},
    ],
    "summary": {"groups": 2, "changed": 2, "removed": 0, "downstream": 4, "flagged_nodes": 6},
}
CP = {"id": "cp1", "created_at": "2026-10-01T18:00:00+09:00", "note": "CP1: draft v2 validated",
      "repos": {"paper": {"rev": "c1d2e3f4a5b6" * 3 + "c1d2", "dirty": False}, "code": {"rev": "d1e2f3a4b5c6" * 3 + "d1e2", "dirty": False}},
      "node_count": len(nodes), "active": True}
CHECKPOINTS = {"active": "cp1", "checkpoints": [CP]}
PROJECT = {
    "schema": "lemmata.project/1", "version": "0.1.0", "name": "Sample: tiny transformer", "root": str(FILES),
    "repos": [
        {"id": "paper", "role": "paper", "path": "paper", "abs_path": str(FILES / "paper"), "vcs": "git", "head": "2b7e5d1c" * 5, "branch": "main", "dirty": False},
        {"id": "code", "role": "code", "path": "code", "abs_path": str(FILES / "code"), "vcs": "git", "head": "4d9e2f5a" * 5, "branch": "main", "dirty": False}],
    "scanned_at": "2026-11-04T15:00:00+09:00",
    "counts": {"nodes": len(nodes), "edges": len(edges), "proposed": 2, "events": len(events), "findings": len(F), "alarm_groups": 2},
    "checkpoint": {"id": "cp1", "created_at": CP["created_at"], "note": CP["note"]},
    "capabilities": {"paper": True, "online_lookup": False, "ask_ai": False},
    "warnings": [],
}
TRIAGE = {"schema": "lemmata.triage/1", "entries": {}, "links": {}}
ANALYZE = {
    "group_id": "ev:commit:code:9f1c2e7a4b3d", "node_id": "tex:tab:main",
    "chain": {"nodes": [cfg, "run:code/train_main", "file:code/results/table2.csv", "tex:tab:main"],
              "edges": ["run:code/train_main|reads|" + cfg, "file:code/results/table2.csv|produced_by|run:code/train_main", "tex:tab:main|traces_to|file:code/results/table2.csv"]},
    "diffs": [{"node_id": cfg, "repo": "code", "path": "configs/default.yaml", "from_label": "checkpoint cp1", "to_label": "now", "binary": False, "truncated": False,
               "unified": "--- a/configs/default.yaml (cp1)\n+++ b/configs/default.yaml (now)\n@@ -2,3 +2,3 @@\n model: tiny\n-learning_rate: 3.0e-4\n-batch_size: 64\n+learning_rate: 1.0e-3\n+batch_size: 128\n optimizer: adam\n"}],
    "explanation": 'configs/default.yaml changed in 9f1c2e7 ("change learning rate 3e-4 to 1e-3"). run train_main reads it. results/table2.csv is produced by run train_main and is byte-identical to the checkpoint (not regenerated, or regenerated identically). Table 2 traces to results/table2.csv.',
    "ai": {"available": False, "label": "Ask Claude why — not available in this demo"},
}
DIFFS = {cfg: ANALYZE["diffs"][0]}


def w(name, obj):
    API.mkdir(parents=True, exist_ok=True)
    (API / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    for rel, text in TEX.items():
        p = FILES / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    w("project.json", PROJECT)
    w("graph.json", GRAPH)
    w("events.json", EVENTS)
    w("findings.json", FINDINGS)
    w("alarms.json", ALARMS)
    w("analyze.json", ANALYZE)
    w("checkpoints.json", CHECKPOINTS)
    w("triage.json", TRIAGE)
    w("diffs.json", DIFFS)
    print("wrote", len(nodes), "nodes", len(edges), "edges")


if __name__ == "__main__":
    main()
