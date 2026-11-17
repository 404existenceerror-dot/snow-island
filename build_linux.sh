#!/bin/bash
# Builds dist/SnowIsland-linux-<arch>, a single file people can download and run.
# Run start.sh once first so .venv exists.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -x "$PY" ] || { echo "Run start.sh once first so the libraries get installed."; exit 1; }

ARCH="$(uname -m)"
"$PY" -m pip install --disable-pip-version-check -q pyinstaller
"$PY" -m PyInstaller --noconfirm --clean --onefile --windowed \
  --name "SnowIsland-linux-$ARCH" snow_island.py
echo "Done: dist/SnowIsland-linux-$ARCH"
