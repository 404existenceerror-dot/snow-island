"""Checks the text parsing used on macOS (AppleScript answers from Finder, Spotify and Music).
Runs on any OS: python tests/test_mac_parsers.py"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform != "darwin":  # let macapi import on Windows/Linux for these pure-text tests
    for name in ("Quartz", "AppKit", "psutil", "fcntl"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["AppKit"].NSApplication = sys.modules["AppKit"].NSWorkspace = None

import macapi  # noqa: E402
import media  # noqa: E402

# Finder: icon size, then each icon's center
r = macapi.parse_icons("{64, {{100, 200}, {300, 400.5}}}")
assert r == [(68.0, 168.0, 132.0, 232.0), (268.0, 368.5, 332.0, 432.5)], r
assert macapi.parse_icons("{48, {}}") == []
assert macapi.parse_icons("") == []

S = media.SEP
# Spotify: duration in milliseconds, maybe a comma as decimal separator
i = media.parse_mac_state("Spotify", S.join(["playing", "Song, with comma", "Artist", "Album", "12,5", "215000"]))
assert i["available"] and i["playing"] and i["is_spotify"], i
assert i["title"] == "Song, with comma" and i["pos"] == 12.5 and i["dur"] == 215.0, i

# Music: duration in seconds
i = media.parse_mac_state("Music", S.join(["paused", "T", "A", "B", "3.0", "180.25"]))
assert not i["playing"] and i["dur"] == 180.25 and not i["is_spotify"], i
assert media.parse_mac_state("Music", "stopped") == {"available": False}

assert media.parse_raw_data("«data PNGf89504E47»") == b"\x89PNG"
assert media.parse_raw_data("") is None and media.parse_raw_data(None) is None

print("mac parser tests passed")
