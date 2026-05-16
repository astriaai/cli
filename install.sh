#!/bin/sh
# Astria CLI installer.
#
#   curl -fsSL https://raw.githubusercontent.com/astriaai/cli/main/install.sh | sh
#
# Options (pass after `sh -s --`):
#   --prefix=DIR   install under DIR/bin         (default: /usr/local)
#   --ref=REF      install a branch or tag       (default: main)
set -eu

REPO="astriaai/cli"
REF="main"
PREFIX="/usr/local"

for arg in "$@"; do
  case "$arg" in
    --prefix=*) PREFIX="${arg#*=}" ;;
    --ref=*)    REF="${arg#*=}" ;;
    -h|--help)  echo "usage: install.sh [--prefix=DIR] [--ref=REF]"; exit 0 ;;
    *) echo "astria-install: unknown option '$arg'" >&2; exit 1 ;;
  esac
done

command -v python3 >/dev/null 2>&1 || { echo "astria-install: python3 is required" >&2; exit 1; }
command -v curl    >/dev/null 2>&1 || { echo "astria-install: curl is required" >&2; exit 1; }

BIN_DIR="$PREFIX/bin"
URL="https://raw.githubusercontent.com/$REPO/$REF/astria"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

echo "Downloading astria ($REF)..."
curl -fsSL "$URL" -o "$TMP"
python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())' "$TMP" \
  || { echo "astria-install: downloaded file is not valid Python (network error / 404?)" >&2; exit 1; }

SUDO=""
if ! mkdir -p "$BIN_DIR" 2>/dev/null || [ ! -w "$BIN_DIR" ]; then
  SUDO="sudo"
  echo "astria-install: $BIN_DIR needs elevated permissions; using sudo."
fi
$SUDO mkdir -p "$BIN_DIR"
$SUDO cp "$TMP" "$BIN_DIR/astria"
$SUDO chmod 0755 "$BIN_DIR/astria"

echo "Installed: $BIN_DIR/astria"
"$BIN_DIR/astria" --version || true

case ":${PATH:-}:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Note: $BIN_DIR is not on your PATH — add it, e.g.  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
echo
echo "Next: run  astria login"
