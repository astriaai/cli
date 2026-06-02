#!/bin/sh
# Astria CLI installer.
#
#   curl -fsSL https://raw.githubusercontent.com/astriaai/cli/main/install.sh | sh
#
# Options (pass after `sh -s --`):
#   --prefix=DIR   install under DIR/bin         (default: Homebrew bin on PATH, else ~/.local)
#   --ref=REF      install a branch or tag       (default: main)
#   --sudo         use sudo when DIR/bin is not writable
set -eu

REPO="astriaai/cli"
REF="main"
if [ -n "${ASTRIA_INSTALL_PREFIX:-}" ]; then
  PREFIX="$ASTRIA_INSTALL_PREFIX"
else
  PREFIX="$HOME/.local"
  if command -v brew >/dev/null 2>&1 && BREW_PREFIX="$(brew --prefix 2>/dev/null)"; then
    case ":${PATH:-}:" in
      *":$BREW_PREFIX/bin:"*)
        if [ -w "$BREW_PREFIX/bin" ]; then
          PREFIX="$BREW_PREFIX"
        fi
        ;;
    esac
  fi
fi
USE_SUDO="false"

for arg in "$@"; do
  case "$arg" in
    --prefix=*) PREFIX="${arg#*=}" ;;
    --ref=*)    REF="${arg#*=}" ;;
    --sudo)     USE_SUDO="true" ;;
    -h|--help)  echo "usage: install.sh [--prefix=DIR] [--ref=REF] [--sudo]"; exit 0 ;;
    *) echo "astria-install: unknown option '$arg'" >&2; exit 1 ;;
  esac
done

command -v python3 >/dev/null 2>&1 || { echo "astria-install: python3 is required" >&2; exit 1; }
command -v curl    >/dev/null 2>&1 || { echo "astria-install: curl is required" >&2; exit 1; }

BIN_DIR="$PREFIX/bin"
SUDO=""
if ! mkdir -p "$BIN_DIR" 2>/dev/null || [ ! -w "$BIN_DIR" ]; then
  if [ "$USE_SUDO" = "true" ]; then
    SUDO="sudo"
    echo "astria-install: $BIN_DIR needs elevated permissions; using sudo."
  else
    echo "astria-install: $BIN_DIR is not writable." >&2
    echo "astria-install: use --prefix=\"\$HOME/.local\" or rerun with --sudo for a system install." >&2
    exit 1
  fi
fi

URL="https://raw.githubusercontent.com/$REPO/$REF/astria"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

echo "Downloading astria ($REF)..."
curl -fsSL "$URL" -o "$TMP"
python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())' "$TMP" \
  || { echo "astria-install: downloaded file is not valid Python (network error / 404?)" >&2; exit 1; }

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
