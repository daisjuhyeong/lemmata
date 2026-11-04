#!/usr/bin/env python3
"""Rename the product in one step.

The current names live in app/branding.json:
    {"slug": "rmap", "display": "Research Map"}

slug    = package, CLI command and hub folder (.rmap/), lowercase
display = the name shown in the UI and docs

Usage (from the repo root):
    python3 app/scripts/rename.py --slug sivro --display Sivro
    python3 app/scripts/rename.py --slug sivro --display Sivro --dry-run

It replaces the old slug and display name in every text file under app/ and wiki/
(except wiki/log.md and wiki/research/, which keep their history), renames
app/src/<old slug>/ to app/src/<new slug>/, and updates app/branding.json.
Existing hub folders in projects you already scanned are not touched: rescan them.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRANDING = ROOT / "app" / "branding.json"
SCAN_DIRS = [ROOT / "app", ROOT / "wiki"]
SKIP_PARTS = {".git", "__pycache__", ".venv", "node_modules", "vendor"}
SKIP_FILES = {ROOT / "wiki" / "log.md"}
SKIP_PREFIXES = [ROOT / "wiki" / "research"]
TEXT_SUFFIXES = {".py", ".js", ".html", ".css", ".md", ".toml", ".json", ".lock", ".txt", ".yaml", ".yml", ".tex", ".bib", ".cfg", ".sh"}


def text_files():
    for base in SCAN_DIRS:
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in TEXT_SUFFIXES:
                continue
            if SKIP_PARTS & set(p.relative_to(ROOT).parts) or p in SKIP_FILES:
                continue
            if any(str(p).startswith(str(pre)) for pre in SKIP_PREFIXES):
                continue
            yield p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True, help="new lowercase slug, e.g. sivro")
    ap.add_argument("--display", required=True, help="new display name, e.g. Sivro")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", a.slug):
        sys.exit("slug must be lowercase letters, digits or _, starting with a letter")
    cur = json.loads(BRANDING.read_text())
    old_slug, old_display = cur["slug"], cur["display"]
    if (old_slug, old_display) == (a.slug, a.display):
        print("Nothing to do: names are unchanged.")
        return 0

    # Word-bounded so that e.g. "rmap" inside another word is left alone.
    slug_re = re.compile(rf"(?<![A-Za-z0-9]){re.escape(old_slug)}(?![A-Za-z0-9])")
    changed = 0
    for p in text_files():
        if p == BRANDING:
            continue
        s = p.read_text(encoding="utf-8", errors="strict") if p.stat().st_size < 5_000_000 else None
        if s is None:
            continue
        t = s.replace(old_display, a.display)
        t = slug_re.sub(a.slug, t)
        if t != s:
            changed += 1
            print(("would update " if a.dry_run else "updated ") + str(p.relative_to(ROOT)))
            if not a.dry_run:
                p.write_text(t, encoding="utf-8")

    src_old, src_new = ROOT / "app" / "src" / old_slug, ROOT / "app" / "src" / a.slug
    if src_old.exists():
        print(("would move " if a.dry_run else "moved ") + f"app/src/{old_slug} -> app/src/{a.slug}")
        if not a.dry_run:
            src_old.rename(src_new)
    if not a.dry_run:
        BRANDING.write_text(json.dumps({"slug": a.slug, "display": a.display}, indent=2) + "\n")
    print(f"{changed} files {'would change' if a.dry_run else 'changed'}: {old_slug}/{old_display} -> {a.slug}/{a.display}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
