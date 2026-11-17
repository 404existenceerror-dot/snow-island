"""Checks the text parsing used on Linux (MPRIS answers from dbus-send, desktop icon positions
from gio). Runs on any OS: python tests/test_linux_parsers.py"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if not sys.platform.startswith("linux"):  # let linuxapi import elsewhere for these text tests
    for name in ("psutil", "fcntl"):
        sys.modules.setdefault(name, types.ModuleType(name))

import linuxapi  # noqa: E402
import media  # noqa: E402

SPOTIFY = '''method return time=1700000000.1 sender=:1.42 -> destination=:1.99 serial=5 reply_serial=2
   array [
      dict entry(
         string "PlaybackStatus"
         variant             string "Playing"
      )
      dict entry(
         string "Metadata"
         variant             array [
               dict entry(
                  string "mpris:trackid"
                  variant                      object path "/com/spotify/track/abc"
               )
               dict entry(
                  string "mpris:length"
                  variant                      uint64 215000000
               )
               dict entry(
                  string "mpris:artUrl"
                  variant                      string "file:///tmp/cover%20art.png"
               )
               dict entry(
                  string "xesam:album"
                  variant                      string "Winter"
               )
               dict entry(
                  string "xesam:artist"
                  variant                      array [
                        string "Artist One"
                        string "Artist "Two""
                     ]
               )
               dict entry(
                  string "xesam:title"
                  variant                      string "Let it "snow""
               )
            ]
      )
      dict entry(
         string "Position"
         variant             int64 12500000
      )
   ]
'''
st = media.parse_mpris(SPOTIFY)
assert st["status"] == "Playing", st
assert st["title"] == 'Let it "snow"', st
assert st["artist"] == 'Artist One, Artist "Two"', st
assert st["album"] == "Winter" and st["art"] == "file:///tmp/cover%20art.png", st
assert st["length"] == 215.0 and st["position"] == 12.5, st
assert media.parse_mpris("") == {} and media.parse_mpris(None) == {}

NAMES = '''method return time=1 sender=org.freedesktop.DBus -> destination=:1.5 serial=3 reply_serial=2
   array [
      string "org.freedesktop.DBus"
      string "org.mpris.MediaPlayer2.spotify"
      string "org.mpris.MediaPlayer2.firefox.instance_1_23"
   ]
'''
import re  # noqa: E402
assert re.findall(r'string "(org\.mpris\.MediaPlayer2\.[^"]+)"', NAMES) == [
    "org.mpris.MediaPlayer2.spotify", "org.mpris.MediaPlayer2.firefox.instance_1_23"]

GIO = '''display name: Photos
uri: file:///home/u/Desktop/Photos
attributes:
  standard::type: 2
  metadata::nemo-icon-position: 64,128
display name: notes.txt
uri: file:///home/u/Desktop/notes.txt
attributes:
  metadata::desktop-icon-position: 300, 40
display name: other
uri: file:///home/u/Desktop/other
attributes:
  metadata::emblems: []
'''
assert linuxapi.parse_gio_positions(GIO) == [(64, 128), (300, 40)], linuxapi.parse_gio_positions(GIO)
assert linuxapi.file_url_bytes("https://example.com/a.png") is None

print("linux parser tests passed")
