"""Picks the system helpers for the current OS. All three modules expose the same names:
DesktopIcons, root_at, root_class_under_cursor, left_button_state, keep_topmost,
make_no_activate, topmost_windows_over, foreground_is_fullscreen, CpuMeter,
memory_percent, battery, already_running, app_setup, press_key and the VK_* constants."""
import sys

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

if IS_MAC:
    from macapi import *  # noqa: F401,F403
elif IS_WINDOWS:
    from winapi import *  # noqa: F401,F403
elif IS_LINUX:
    from linuxapi import *  # noqa: F401,F403
else:
    raise SystemExit("Snow Island runs on Windows 10/11, macOS and Linux.")
