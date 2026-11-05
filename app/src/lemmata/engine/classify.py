"""File -> node kind (data-model 3.2)."""
import posixpath

OUTPUT_DIRS = {"results", "result", "outputs", "output", "out", "figures", "figs", "plots", "tables", "logs"}
ASSET_EXT = {"png", "jpg", "jpeg", "pdf", "svg", "eps"}
CODE_EXT = {"py", "sh", "ipynb", "r", "jl", "m"}
CONFIG_EXT = {"yaml", "yml", "toml", "ini", "cfg"}
DATA_EXT = {"csv", "tsv", "json", "jsonl", "txt", "npz", "npy", "pkl", "gz", "parquet"}
DOC_EXT = {"md", "rst"}
PAPER_EXT = {"tex", "bib", "cls", "sty", "bst"}
BINARY_EXT = {"png", "jpg", "jpeg", "pdf", "eps", "npz", "npy", "pkl", "gz", "parquet"}
MAX_BYTES = 50 * 1024 * 1024


def ext_of(path):
    e = posixpath.splitext(path)[1].lower()
    return e[1:] if e else ""


def is_hidden(path):
    return any(seg.startswith(".") for seg in path.split("/"))


def in_output_dir(path):
    return any(seg.lower() in OUTPUT_DIRS for seg in path.split("/")[:-1])


def is_run_record(path):
    parts = path.split("/")
    return len(parts) == 2 and parts[0] == "runs" and parts[1].endswith(".json")


def classify(path, size=0):
    """Return a node kind or None when the file is not a node."""
    if is_hidden(path) or size > MAX_BYTES:
        return None
    if is_run_record(path):
        return None
    ext = ext_of(path)
    if ext in PAPER_EXT:
        return None
    if ext in ASSET_EXT:
        return "asset"
    if ext in CODE_EXT:
        return "code"
    if ext in CONFIG_EXT:
        return "config"
    if ext in DOC_EXT:
        return None if in_output_dir(path) else "doc"
    if ext in DATA_EXT:
        if ext == "json" and any(seg.lower().startswith(("config", "conf")) for seg in path.split("/")[:-1]):
            return "config"
        return "result" if in_output_dir(path) else "data"
    return None
