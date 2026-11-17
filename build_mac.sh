#!/bin/bash
# Builds "dist/Snow Island.app" and a zip of it for the GitHub Releases page.
# Run start.command once first so .venv exists.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -x "$PY" ] || { echo "Run start.command once first so the libraries get installed."; exit 1; }

"$PY" -m pip install --disable-pip-version-check -q pyinstaller pillow
"$PY" -m PyInstaller --noconfirm --clean --windowed \
  --name "Snow Island" --icon assets/icon.png \
  --osx-bundle-identifier com.snowisland.app \
  snow_island.py

APP="dist/Snow Island.app"
PLIST="$APP/Contents/Info.plist"
# menu-bar app (no Dock icon), and the text macOS shows when asking to control Finder/Spotify/Music
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST" 2>/dev/null ||
  /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :NSAppleEventsUsageDescription string Snow Island reads where your desktop icons are (Finder) and what song is playing (Spotify, Music)." "$PLIST" 2>/dev/null || true
codesign --force --deep --sign - "$APP"

ARCH="$(uname -m)"
(cd dist && ditto -c -k --keepParent "Snow Island.app" "SnowIsland-mac-$ARCH.zip")
echo "Done: $APP and dist/SnowIsland-mac-$ARCH.zip"
