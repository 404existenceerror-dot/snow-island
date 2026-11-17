#!/bin/bash
# Snow Island for macOS: double-click this file to start it from the source code.
# The first run creates a .venv folder and downloads the libraries (one time only).
cd "$(dirname "$0")" || exit 1

if [ ! -x ".venv/bin/python" ]; then
  PY=""
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 &&
       "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PY="$c"; break
    fi
  done
  if [ -z "$PY" ]; then
    echo "Snow Island needs Python 3.10 or newer: https://www.python.org/downloads/macos/"
    read -r -p "Press Enter to close."
    exit 1
  fi
  echo "First start: setting things up (about 1-2 minutes)..."
  "$PY" -m venv .venv || exit 1
  .venv/bin/python -m pip install --disable-pip-version-check -q --upgrade pip
  if ! .venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt; then
    echo "Installing the libraries failed. Check your internet connection and try again."
    rm -rf .venv
    read -r -p "Press Enter to close."
    exit 1
  fi
fi

nohup .venv/bin/python snow_island.py >/dev/null 2>&1 &
echo "Snow Island is running. Look for the snowflake in the menu bar. You can close this window."
