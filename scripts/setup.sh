#!/usr/bin/env sh
# Bootstrap the daemon host (Linux, WSL or macOS): install uv if missing, then
# run setup, start the daemon and run the doctor.
# Usage: sh scripts/setup.sh [--no-start]
set -eu

cd "$(dirname "$0")/.."

start=1
for arg in "$@"; do
  case "$arg" in
    --no-start) start=0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found, installing (https://docs.astral.sh/uv/)"
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    echo "need curl or wget to install uv" >&2
    exit 1
  fi
  # The installer puts uv in ~/.local/bin (or $XDG_BIN_HOME); make it visible now.
  PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$HOME/.cargo/bin:$PATH"
  export PATH
  command -v uv >/dev/null 2>&1 || { echo "uv installed but not on PATH; open a new shell" >&2; exit 1; }
fi
uv --version

uv run --script bin/laya_setup.py
if [ "$start" -eq 1 ]; then
  uv run --script bin/laya_daemon.py start
  uv run --script bin/laya_doctor.py
else
  echo "next: uv run --script bin/laya_daemon.py start && uv run --script bin/laya_doctor.py"
fi
