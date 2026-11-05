# Lemmata (localhost demo)

A researcher's guide that tracks paper, code and runs as a dependency graph. Everything runs on your machine; nothing is uploaded. Python 3.10+ and `git` are the only requirements (standard library only).

## Run
```
uv run --project app lemmata demo           # builds the synthetic sample, scans it, serves http://127.0.0.1:8765
PYTHONPATH=app/src python3 -m lemmata demo  # zero-install fallback
pip install -e app && lemmata demo          # or install the console script
```
`uv` needs the network once (to fetch the build backend); after that everything is offline.

| Command | What it does |
|---|---|
| `lemmata demo [--dir ~/lemmata-demo] [--keep] [--port 8765] [--no-open] [--online]` | rebuild the sample (only into a folder carrying `.lemmata-sample`), scan, serve |
| `lemmata open <dir> [--paper DIR] [--code DIR]` | write `.lemmata/project.json` if missing, scan, serve |
| `lemmata serve <dir>` | scan and serve an already opened project |
| `lemmata scan <dir>` | scan and print a one-line summary |
| `lemmata checkpoint <dir> [--at repo=rev] [--note TEXT]` | set your "Last known good" |
| any of the above with `--fixtures[=sample\|large]` | run the UI on `tests/fixtures` data instead of the engine (`large` is about 300 nodes) |

The server binds 127.0.0.1 only, checks Host and Origin, caps request bodies at 64 KB and serves only files under `src/lemmata/web/`.

## Your own paper and code
```
lemmata open ~/work/alarm-analyzer-eval --paper ~/Downloads/www27-overleaf   # unzipped Overleaf source
lemmata open ~/work/alarm-analyzer-eval                                      # code only also works
```
The tool only reads your repos (read-only git) and writes inside `.lemmata/` in the project folder, which ignores itself in git.

## Changing the name
"Lemmata" / `lemmata` is a working name. When the real name is chosen, one command renames the package, CLI, hub folder, UI and wiki:
```
python3 app/scripts/rename.py --slug newname --display "Newname" --dry-run   # preview
python3 app/scripts/rename.py --slug newname --display "Newname"
```

## Tests
```
PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p "test_*.py"   # 33 tests
python3 app/tests/fixtures/build_fixtures.py    # regenerate tests/fixtures/api/*.json
```

## UI
Plain HTML, CSS and JS in `src/lemmata/web/`, no build step. Cytoscape.js 3.34.4 (MIT) is vendored in `web/vendor/` (see its README). The "Export HTML report" button writes one self-contained file that opens offline and is read-only.
