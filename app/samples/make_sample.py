#!/usr/bin/env python3
"""Build the deterministic synthetic sample: a paper repo (P1-P3) and a code repo (K1-K5).

Usage: python3 make_sample.py <target_dir>
Stdlib + the git binary only. Writes only inside <target_dir>. Fixed identity, fixed dates and an isolated
git config make every commit hash identical on every run.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MARKER = ".rmap-sample"
TZ = "+0900"
IDENT = {"name": "Sample Author", "email": "author@example.invalid"}

# ----------------------------------------------------------------------------------------------- paper
FIG_ARCH = r"""\begin{figure}[t]
% generated-by: manual
\centering
\includegraphics[width=0.8\linewidth]{figures/arch.pdf}
\caption{Architecture of the model.}\label{fig:arch}
\end{figure}
"""
FIG_CURVE = r"""\begin{figure}[t]
% generated-by: code:plot_curve.py
\centering
\includegraphics[width=0.8\linewidth]{figures/curve.png}
\caption{Validation curve during training.}\label{fig:curve}
\end{figure}
"""
FIG_QUAL = r"""\begin{figure}[t]
\centering
\includegraphics[width=0.8\linewidth]{figures/qual.png}
\caption{Qualitative examples.}\label{fig:qual}
\end{figure}
"""
TAB_DATA = r"""\begin{table}[t]
\centering
\caption{Dataset sizes.}\label{tab:data}
\begin{tabular}{lr}
Split & Sentences \\
Train & 8000 \\
Test & 2000 \\
\end{tabular}
\end{table}
"""
TAB_MAIN = r"""\begin{table}[t]
% source: code:results/table2.csv
\centering
\caption{Main results on the benchmark.}\label{tab:main}
\begin{tabular}{lrrr}
Model & F1 & Precision & Recall \\
Baseline & 0.871 & 0.862 & 0.880 \\
Ours & 0.912 & 0.905 & 0.919 \\
\end{tabular}
\end{table}
"""
TAB_ABL = r"""\begin{table}[t]
\centering
\caption{Ablation of the attention heads.}\label{tab:ablation}
\begin{tabular}{lr}
Heads & F1 \\
1 & 0.871 \\
4 & 0.912 \\
\end{tabular}
\end{table}
"""

MAIN_TEX = r"""\documentclass{article}
\usepackage{graphicx}
\begin{document}
\title{A Tiny Transformer for Sequence Labelling}
\author{Anonymous}
\maketitle

\begin{abstract}
We ask whether a very small transformer can match a larger baseline on a sequence labelling benchmark.
We also report where every number in the paper comes from.
\end{abstract}

\section{Introduction}\label{sec:intro}
Sequence labelling is a standard task~\cite{vaswani2017attention,devlin2019bert}.
We study two questions.
RQ1: Can a tiny transformer match a larger baseline?
RQ2: How much does each component contribute?

\section{Related Work}\label{sec:related}
Residual networks~\cite{he2016deep} and adaptive methods~\cite{kingma2015adam} are widely used.
A study of ghost gradients~\cite{smith2021ghost} reports similar trends, as does earlier work~\cite{nobody2020}.

\section{Method}\label{sec:method}
The model is a small encoder with a linear classification head.
{{FIG_ARCH}}
\section{Experimental Setup}\label{sec:setup}
We train with a learning rate of $3\times10^{-4}$ and batch size 64.
The optimizer is Adam.
Table~\ref{tab:data} lists the dataset sizes.
{{TAB_DATA}}
\section{Results}\label{sec:results}
Table~\ref{tab:main} compares our model with the baseline (RQ1).
Our model reaches 92.4 F1, while the baseline reaches 0.871.
{{TAB_MAIN}}
Figure~\ref{fig:curve} shows the validation curve, and Figure~\ref{fig:qual} shows examples.
See also Figure~\ref{fig:missing}. The ablation (RQ2) is discussed in the text.
{{FIG_CURVE}}
{{FIG_QUAL}}
{{TAB_ABL}}
\bibliographystyle{plain}
\bibliography{refs}
\appendix
\input{appendix}
\end{document}
"""

APPENDIX_TEX = r"""\section{Additional Details}\label{app:details}
The data splits follow the benchmark protocol. Main results are in Table~\ref{tab:main}.

\section{Hyperparameters}\label{app:hparams}
All runs use the settings below.
\begin{tabular}{ll}
Learning rate & $3\times10^{-4}$ \\
Batch size & 128 \\
Optimizer & Adam \\
\end{tabular}
"""

REFS_BIB = r"""@inproceedings{vaswani2017attention,
  title={Attention is all you need},
  author={Vaswani, Ashish and others},
  year={2017}
}
@inproceedings{devlin2019bert,
  title={{BERT}: Pre-training of Deep Bidirectional Transformers for Language Understanding},
  author={Devlin, Jacob and others},
  year={2019}
}
@inproceedings{he2016deep,
  title={Deep Residual Learning for Image Recognition},
  author={He, Kaiming and others},
  year={2016}
}
@inproceedings{kingma2015adam,
  title={Adam: A Method for Stochastic Optimization},
  author={Kingma, Diederik and Ba, Jimmy},
  year={2015}
}
@article{smith2021ghost,
  title={Ghost Gradients in Tiny Transformers},
  author={Smith, Sam},
  year={2021}
}
@article{unused2019,
  title={A Survey of Sequence Labelling Methods},
  author={Doe, Jane},
  year={2019}
}
"""

# ------------------------------------------------------------------------------------------------ code
TRAIN_PY = '''"""Train the tiny transformer (synthetic stand-in for a real training script)."""
CONFIG = "configs/default.yaml"


def load_config(path=CONFIG):
    cfg = {}
    for line in open(path):
        if ":" in line and not line.startswith("#"):
            key, value = line.split(":", 1)
            cfg[key.strip()] = value.strip()
    return cfg


def main():
    cfg = load_config()
    rows = [("baseline", 0.871, 0.862, 0.880), ("ours", 0.912, 0.905, 0.919)]
    with open("results/table2.csv", "w") as f:
        f.write("model,f1,precision,recall\\n")
        for r in rows:
            f.write("%s,%.3f,%.3f,%.3f\\n" % r)
    return cfg


if __name__ == "__main__":
    main()
'''
EVAL_PY = '''"""Evaluate the trained model and write metrics."""
import json

from train import load_config


def evaluate():
    cfg = load_config()
    metrics = {"loss": 0.311, "accuracy": 0.894}
    with open("results/metrics.json", "w") as f:
        json.dump(metrics, f)
    return cfg, metrics
'''
EVAL_PY_K4 = EVAL_PY.replace('    cfg = load_config()\n', '    cfg = load_config()\n    # tmp: scratch note\n')
PLOT_PY = '''"""Plot the validation curve for the paper figure."""
import matplotlib.pyplot as plt


def plot(history):
    plt.plot(history)
    plt.savefig("curve_tmp.png")
'''
CONFIG_YAML_OLD = "# default training configuration\nlearning_rate: 3.0e-4\nbatch_size: 128\noptimizer: adam\nseed: 0\n"
CONFIG_YAML_NEW = CONFIG_YAML_OLD.replace("3.0e-4", "1.0e-3")
TABLE2_CSV = "model,f1,precision,recall\nbaseline,0.871,0.862,0.880\nours,0.912,0.905,0.919\n"
METRICS_JSON = '{"loss": 0.311, "accuracy": 0.894}\n'
RUN_RECORD = {"schema": "rmap.run/1", "run_id": "train_main", "started_at": "2026-09-30T14:00:00+09:00",
              "command": "python train.py --config configs/default.yaml", "script": "train.py",
              "inputs": ["configs/default.yaml"], "outputs": ["results/table2.csv"]}
CODE_README = "# Sample code repo\n\nSynthetic code for the sample project.\n"

REFS_CACHE_ENTRIES = [
    ("vaswani2017attention", "Attention is all you need", 2017, "matched"),
    ("devlin2019bert", "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding", 2019, "matched"),
    ("he2016deep", "Deep Residual Learning for Image Recognition", 2016, "matched"),
    ("kingma2015adam", "Adam: A Method for Stochastic Optimization", 2015, "matched"),
    ("unused2019", "A Survey of Sequence Labelling Methods", 2019, "matched"),
    ("smith2021ghost", "Ghost Gradients in Tiny Transformers", 2021, "not_found"),
]


def _norm(t):
    return "".join(c for c in t.lower() if c.isalnum())


def _env(date):
    e = dict(os.environ)
    e.update({
        "GIT_AUTHOR_NAME": IDENT["name"], "GIT_AUTHOR_EMAIL": IDENT["email"], "GIT_AUTHOR_DATE": "%s %s" % (date, TZ),
        "GIT_COMMITTER_NAME": IDENT["name"], "GIT_COMMITTER_EMAIL": IDENT["email"], "GIT_COMMITTER_DATE": "%s %s" % (date, TZ),
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
    })
    return e


def git(repo, args, date="2026-09-01T00:00:00"):
    subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", "-c", "init.defaultBranch=main"] + args,
                   cwd=str(repo), env=_env(date), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write(repo, rel, content):
    p = Path(repo) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        p.write_bytes(content)
    else:
        p.write_text(content, encoding="utf-8", newline="\n")


def commit(repo, msg, date, files):
    for rel, content in files.items():
        write(repo, rel, content)
    git(repo, ["add", "-A"], date)
    git(repo, ["commit", "-q", "-m", msg], date)


def fill(template, **blocks):
    for k, v in blocks.items():
        template = template.replace("{{%s}}" % k, v)
    return template


def build(target):
    target = Path(target).resolve()
    if target.exists() and any(target.iterdir()):
        if not (target / MARKER).exists():
            raise SystemExit("refusing to overwrite %s (no %s marker)" % (target, MARKER))
        for child in target.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    target.mkdir(parents=True, exist_ok=True)
    (target / MARKER).write_text("synthetic sample; safe to delete\n", encoding="utf-8")
    paper, code = target / "paper", target / "code"
    for r in (paper, code):
        r.mkdir()
        git(r, ["init", "-q", "-b", "main"])

    empty = dict(FIG_ARCH="", FIG_CURVE="", FIG_QUAL="", TAB_MAIN="", TAB_ABL="", TAB_DATA="")
    full = dict(FIG_ARCH=FIG_ARCH, FIG_CURVE=FIG_CURVE, FIG_QUAL=FIG_QUAL, TAB_MAIN=TAB_MAIN, TAB_ABL=TAB_ABL, TAB_DATA=TAB_DATA)
    # P1: initial draft (no floats yet)
    commit(paper, "P1: initial draft", "2026-09-20T10:00:00", {
        "main.tex": fill(MAIN_TEX, **empty), "appendix.tex": APPENDIX_TEX, "refs.bib": REFS_BIB})
    # P2: add tables and figures  (CP1 is seeded here)
    commit(paper, "P2: add tables and figures", "2026-09-28T10:00:00", {
        "main.tex": fill(MAIN_TEX, **full),
        "figures/arch.pdf": b"%PDF-1.4 sample architecture figure\n",
        "figures/curve.png": b"\x89PNG sample curve figure\n",
        "figures/qual.png": b"\x89PNG sample qualitative figure\n"})
    git(paper, ["tag", "cp1"], "2026-09-28T10:00:00")
    # P3: appendix B learning rate
    commit(paper, "appendix B: learning rate 1e-3", "2026-10-04T09:00:00", {
        "appendix.tex": APPENDIX_TEX.replace(r"Learning rate & $3\times10^{-4}$", r"Learning rate & $1\times10^{-3}$")})

    # K1: initial training code
    commit(code, "K1: initial training code", "2026-09-25T10:00:00", {
        "README.md": CODE_README, "train.py": TRAIN_PY, "configs/default.yaml": CONFIG_YAML_OLD,
        "runs/train_main.json": json.dumps(RUN_RECORD, indent=1) + "\n", "results/table2.csv": TABLE2_CSV})
    # K2: add eval and plotting  (CP1 is seeded here)
    commit(code, "K2: add eval and plotting", "2026-09-29T10:00:00", {
        "eval.py": EVAL_PY, "plot_curve.py": PLOT_PY, "results/metrics.json": METRICS_JSON})
    git(code, ["tag", "cp1"], "2026-09-29T10:00:00")
    # K3: config only; results are not regenerated
    commit(code, "change learning rate 3e-4 to 1e-3", "2026-10-03T10:00:00", {"configs/default.yaml": CONFIG_YAML_NEW})
    # K4/K5: edit then revert eval.py -> identical bytes
    commit(code, "tmp: edit comment in eval.py", "2026-10-05T11:00:00", {"eval.py": EVAL_PY_K4})
    commit(code, "revert eval.py", "2026-10-05T11:30:00", {"eval.py": EVAL_PY})

    hub = target / ".rmap"
    (hub / "cache").mkdir(parents=True)
    manifest = {
        "schema": "rmap.project/1", "name": "Sample: tiny transformer",
        "repos": [{"id": "paper", "role": "paper", "path": "paper", "main_tex": "main.tex", "exclude": []},
                  {"id": "code", "role": "code", "path": "code", "exclude": []}],
        "seed_checkpoint": {"id": "cp1", "note": "CP1: draft v2 validated", "created_at": "2026-10-01T18:00:00+09:00",
                            "at": {"paper": "cp1", "code": "cp1"}},
    }
    refs = {"schema": "rmap.refs/1", "entries": {}}
    for key, title, year, status in REFS_CACHE_ENTRIES:
        refs["entries"][_norm(title)] = {
            "status": status, "source": "seed", "checked_at": "2026-10-01T12:00:00+09:00",
            "match": {"title": title, "year": year, "doi": None, "url": None} if status == "matched" else None}
    for name, obj in (("project.json", manifest), ("cache/refs.json", refs)):
        (hub / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (hub / ".gitignore").write_text("*\n", encoding="utf-8")
    return target


def main(argv):
    if len(argv) != 2:
        print("usage: make_sample.py <target_dir>", file=sys.stderr)
        return 2
    out = build(argv[1])
    print("sample written to %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
