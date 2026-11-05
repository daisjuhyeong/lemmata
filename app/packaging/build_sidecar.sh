#!/usr/bin/env bash
# Build the one-file sidecar `lemmata-server` with PyInstaller. Prints its absolute path on the last line.
# Uses uv if present (isolated venv in packaging/.venv), else python3 -m venv. Works on macOS arm64 and Linux.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$(dirname "$HERE")"
VENV="$HERE/.venv"
if command -v uv >/dev/null 2>&1; then
  [ -d "$VENV" ] || uv venv --python ">=3.10" "$VENV" >&2
  uv pip install --python "$VENV/bin/python" --quiet pyinstaller >&2
else
  PY="${PYTHON:-python3}"
  [ -d "$VENV" ] || "$PY" -m venv "$VENV"
  "$VENV/bin/pip" install --quiet pyinstaller >&2
fi
rm -rf "$HERE/build" "$HERE/dist"
"$VENV/bin/python" -m PyInstaller --noconfirm --clean --distpath "$HERE/dist" --workpath "$HERE/build" "$HERE/lemmata-server.spec" >&2
OUT="$HERE/dist/lemmata-server"
[ -x "$OUT" ] || { echo "build failed: $OUT missing" >&2; exit 1; }
echo "$OUT"
