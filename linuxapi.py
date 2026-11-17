"""Linux versions of the helpers in winapi.py (same names, same meaning).

Works on X11 desktops (and through XWayland on Wayland, with limits: windows of native
Wayland apps can't be seen, so snow piles don't hide behind them). Uses python-xlib and
psutil. X11 coordinates are physical pixels, same as the Windows interface."""
import fcntl
import os
import re
import subprocess
import threading
import time
from urllib.parse import unquote, urlparse

import psutil

try:
    from Xlib import X, display as xdisplay
    from Xlib.error import XError
except Exception:  # pragma: no cover
    xdisplay = None
    XError = Exception

MY_PID = os.getpid()
WAYLAND = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))

DESKTOP_CLASSES = ("Desktop",)
DOCK_CLASS = "Dock"
WINDOW_CLASS = "Window"

VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF
VK_MEDIA_NEXT, VK_MEDIA_PREV, VK_MEDIA_PLAY_PAUSE = 0xB0, 0xB1, 0xB3


def app_setup():
    pass


# ---------------------------------------------------------------- X connection
class _X:
    d = None
    root = None
    atoms = {}

    @classmethod
    def ok(cls):
        if cls.d is None and xdisplay is not None and os.environ.get("DISPLAY"):
            try:
                cls.d = xdisplay.Display()
                cls.root = cls.d.screen().root
            except Exception:
                cls.d = None
        return cls.d is not None

    @classmethod
    def atom(cls, name):
        a = cls.atoms.get(name)
        if a is None:
            a = cls.atoms[name] = cls.d.intern_atom(name)
        return a

    @classmethod
    def prop(cls, win, name):
        try:
            p = win.get_full_property(cls.atom(name), X.AnyPropertyType)
            return p.value if p is not None else None
        except XError:
            return None


# ---------------------------------------------------------------- single instance
_lock_file = None


def already_running(name="SnowIsland_SingleInstance_v1"):
    global _lock_file
    base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    _lock_file = open(os.path.join(base, f"{name}-{os.getuid()}.lock"), "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except OSError:
        return True


# ---------------------------------------------------------------- window tweaks
def make_no_activate(wid):
    pass  # Qt's Tool + WindowDoesNotAcceptFocus flags already do this on X11


def keep_topmost(wid):
    if not wid or not _X.ok():
        return
    try:
        _X.d.create_resource_object("window", int(wid)).configure(stack_mode=X.Above)
        _X.d.flush()
    except Exception:
        pass


# ---------------------------------------------------------------- on-screen windows
_cache = {"t": 0.0, "wins": []}


def _windows(max_age=0.1):
    """Visible top-level windows of other apps, top to bottom:
    (id, kind, above, fullscreen, pid, (l, t, r, b)) in physical pixels."""
    now = time.monotonic()
    if now - _cache["t"] < max_age:
        return _cache["wins"]
    out = []
    if _X.ok():
        try:
            ids = _X.prop(_X.root, "_NET_CLIENT_LIST_STACKING") or _X.prop(_X.root, "_NET_CLIENT_LIST") or []
            hidden = _X.atom("_NET_WM_STATE_HIDDEN")
            above_a = _X.atom("_NET_WM_STATE_ABOVE")
            full_a = _X.atom("_NET_WM_STATE_FULLSCREEN")
            t_desktop = _X.atom("_NET_WM_WINDOW_TYPE_DESKTOP")
            t_dock = _X.atom("_NET_WM_WINDOW_TYPE_DOCK")
            for wid in reversed(list(ids)):
                try:
                    w = _X.d.create_resource_object("window", wid)
                    pid = _X.prop(w, "_NET_WM_PID")
                    pid = int(pid[0]) if pid is not None and len(pid) else 0
                    if pid == MY_PID:
                        continue
                    if w.get_attributes().map_state != X.IsViewable:
                        continue  # minimized or on another workspace
                    state = set(_X.prop(w, "_NET_WM_STATE") or [])
                    if hidden in state:
                        continue
                    types = set(_X.prop(w, "_NET_WM_WINDOW_TYPE") or [])
                    kind = "Desktop" if t_desktop in types else DOCK_CLASS if t_dock in types else WINDOW_CLASS
                    g = w.get_geometry()
                    pos = w.translate_coords(_X.root, 0, 0)
                    x, y = -pos.x, -pos.y
                    fe = _X.prop(w, "_NET_FRAME_EXTENTS")
                    fl, fr, ft, fb = (list(fe) + [0, 0, 0, 0])[:4] if fe is not None else (0, 0, 0, 0)
                    rect = (x - fl, y - ft, x + g.width + fr, y + g.height + fb)
                    if g.width <= 2 or g.height <= 2:
                        continue
                    out.append((int(wid), kind, above_a in state, full_a in state, pid, rect))
                except XError:
                    continue
        except Exception:
            _X.d = None  # reconnect next time
    _cache["t"], _cache["wins"] = now, out
    return out


def root_at(x, y):
    """(window id, kind) of what's visible at a physical point; kind is 'Desktop' when no
    app window covers it."""
    for wid, kind, _a, _f, _p, (l, t, r, b) in _windows():
        if l <= x < r and t <= y < b:
            return wid, kind
    return 0, DESKTOP_CLASSES[0]


def _pointer():
    if not _X.ok():
        return None
    try:
        return _X.root.query_pointer()
    except Exception:
        return None


def root_class_under_cursor():
    p = _pointer()
    if p is None:
        return 0, WINDOW_CLASS
    return root_at(p.root_x, p.root_y)


# ---------------------------------------------------------------- input
def left_button_state():
    """Returns (is_down, was_pressed_since_last_check). X11 can't report clicks that
    happened between two checks, so very quick clicks may be missed."""
    p = _pointer()
    if p is None:
        return False, False
    return bool(p.mask & X.Button1Mask), False


def _run(args):
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def press_key(vk, times=1):
    """Volume keys change the system volume (PulseAudio/PipeWire, or ALSA)."""
    step = 5 * times
    if vk in (VK_VOLUME_UP, VK_VOLUME_DOWN):
        sign = "+" if vk == VK_VOLUME_UP else "-"
        if not _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{sign}{step}%"]):
            _run(["amixer", "-q", "set", "Master", f"{step}%{sign}"])
    elif vk == VK_VOLUME_MUTE:
        if not _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]):
            _run(["amixer", "-q", "set", "Master", "toggle"])


# ---------------------------------------------------------------- foreground state
def foreground_info():
    if not _X.ok():
        return 0, ""
    a = _X.prop(_X.root, "_NET_ACTIVE_WINDOW")
    return (int(a[0]) if a is not None and len(a) else 0), ""


def foreground_is_fullscreen():
    active, _ = foreground_info()
    return any(w[0] == active and w[3] for w in _windows(0.3)) if active else False


def topmost_windows_over(left, top, right, bottom, own, screen_area):
    """Other apps' always-on-top windows over the given physical rect (e.g. a recorder's bar)."""
    found = []
    for wid, kind, above, _f, _p, (l, t, r, b) in _windows(0.3):
        if not above or kind != WINDOW_CLASS or wid in own:
            continue
        if (r - l) * (b - t) > screen_area * 0.6:
            continue
        if r <= left or l >= right or b <= top or t >= bottom:
            continue
        found.append((wid, kind, (l, t, r, b)))
    return found


# ---------------------------------------------------------------- system stats
class CpuMeter:
    def __init__(self):
        psutil.cpu_percent(None)

    def percent(self):
        return int(round(psutil.cpu_percent(None)))


def memory_percent():
    return int(round(psutil.virtual_memory().percent))


def battery():
    try:
        b = psutil.sensors_battery()
    except Exception:
        return None
    if b is None:
        return None
    return int(round(b.percent)), bool(b.power_plugged)


# ---------------------------------------------------------------- desktop icons
ICON = 48  # typical desktop icon size in pixels
POSITION_KEYS = ("metadata::nemo-icon-position", "metadata::caja-icon-position",
                 "metadata::desktop-icon-position", "metadata::nautilus-icon-position")


def desktop_dir():
    try:
        r = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=2)
        path = r.stdout.strip()
        if r.returncode == 0 and path and os.path.isdir(path):
            return path
    except Exception:
        pass
    return os.path.expanduser("~/Desktop")


def parse_gio_positions(text):
    """`gio info -a metadata::*` output for several files -> list of (x, y) icon positions."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        for key in POSITION_KEYS:
            if line.startswith(key + ":"):
                m = re.match(r"(-?\d+)\s*,\s*(-?\d+)", line[len(key) + 1:].strip())
                if m:
                    out.append((int(m.group(1)), int(m.group(2))))
                break
    return out


class DesktopIcons:
    """Desktop icon positions saved by the file manager that draws the desktop (Nemo on
    Cinnamon, Caja on MATE, the GNOME 'Desktop Icons' extension). Other desktops don't share
    them, and then snow simply doesn't pile on icons. Refreshed on a background thread."""

    INTERVAL = 4.0

    def __init__(self):
        self._rects = []
        self._thread = None

    def refresh(self):
        folder = desktop_dir()
        try:
            names = [n for n in os.listdir(folder) if not n.startswith(".")][:300]
        except OSError:
            names = []
        if not names:
            self._rects = []
            return []
        try:
            r = subprocess.run(["gio", "info", "-a", "metadata::*"] + [os.path.join(folder, n) for n in names],
                               capture_output=True, text=True, timeout=8)
            pts = parse_gio_positions(r.stdout)
        except Exception:
            pts = []
        self._rects = [(x, y, x + ICON, y + ICON) for x, y in pts]
        return self._rects

    def _loop(self):
        while True:
            try:
                self.refresh()
            except Exception:
                self._rects = []
            time.sleep(self.INTERVAL)

    def rects(self):
        """List of (left, top, right, bottom) in physical pixels."""
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return list(self._rects)


def file_url_bytes(url):
    """Reads album art only when the player saved it as a local file (no downloads)."""
    try:
        u = urlparse(url)
        if u.scheme != "file":
            return None
        with open(unquote(u.path), "rb") as f:
            return f.read(4_000_000)
    except Exception:
        return None


def x11_ok():
    """True when Snow Island can talk to the X11 display (needed to see other windows)."""
    return _X.ok()
