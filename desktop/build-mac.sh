#!/usr/bin/env bash
# Build Lemmata.app and Lemmata.dmg on an Apple-silicon Mac. Run from anywhere: ./desktop/build-mac.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
die() { echo "error: $*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || die "this script builds the macOS app; run it on the Mac."
[ "$(uname -m)" = "arm64" ] || echo "warning: arm64 is the only supported target for now (this Mac is $(uname -m))." >&2

echo "==> Checking tools"
xcode-select -p >/dev/null 2>&1 || die "Xcode Command Line Tools missing. Run: xcode-select --install   then re-run this script."
if ! command -v cargo >/dev/null 2>&1; then
  [ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
fi
command -v cargo >/dev/null 2>&1 || die "Rust missing. Install: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh   then open a new Terminal."
if command -v uv >/dev/null 2>&1; then :; else
  PY="${PYTHON:-python3}"
  command -v "$PY" >/dev/null 2>&1 || die "Python >= 3.10 (or uv) missing. Install uv: brew install uv"
  "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || die "Python >= 3.10 needed (or install uv: brew install uv)."
fi

echo "==> Building the sidecar (PyInstaller)"
SIDECAR="$("$ROOT/app/packaging/build_sidecar.sh" | tail -n 1)"
[ -x "$SIDECAR" ] || die "sidecar build did not produce an executable: $SIDECAR"

TRIPLE="$(rustc -vV | sed -n 's/host: //p')"
mkdir -p "$HERE/src-tauri/binaries"
cp "$SIDECAR" "$HERE/src-tauri/binaries/lemmata-server-$TRIPLE"
chmod +x "$HERE/src-tauri/binaries/lemmata-server-$TRIPLE"
echo "    sidecar: binaries/lemmata-server-$TRIPLE"

# keep the launcher's copy of the icon in sync with the designer's file
cp "$HERE/icons/lemmata-icon.svg" "$HERE/launcher/lemmata-icon.svg"

if ! cargo tauri --version >/dev/null 2>&1; then
  echo "==> Installing tauri-cli v2 (a few minutes the first time)"
  cargo install tauri-cli --version "^2" --locked
fi

echo "==> Building Lemmata (first build downloads and compiles Rust crates: 5-10 minutes)"
cd "$HERE/src-tauri"
cargo tauri build --bundles app,dmg

OUT="$HERE/src-tauri/target/release/bundle"
echo
echo "Done."
echo "  App: $(ls -d "$OUT"/macos/*.app 2>/dev/null | head -n 1)"
echo "  DMG: $(ls "$OUT"/dmg/*.dmg 2>/dev/null | head -n 1)"
echo "Apps built on this Mac are not quarantined and open normally. To use the DMG on another Mac see desktop/README.md (Gatekeeper)."
