"""macOS versions of the helpers in winapi.py (same names, same meaning).

Uses pyobjc (Quartz + AppKit) and psutil. "Physical" pixels in the shared interface are
Qt logical points times the screen's device pixel ratio, same as on Windows, so the rest
of the app doesn't need to know which OS it's on."""
import fcntl
import os
import re
import subprocess
import threading
import time

import psutil
import Quartz
from AppKit import NSApplication, NSWorkspace

try:
    import objc
except ImportError:  # pragma: no cover
    objc = None

MY_PID = os.getpid()

# "Classes" returned by root_at(), so winter.py can stay OS-neutral.
DESKTOP_CLASSES = ("Desktop",)
DOCK_CLASS = "Dock"
WINDOW_CLASS = "Window"
MENUBAR_CLASS = "MenuBar"

VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF
VK_MEDIA_NEXT, VK_MEDIA_PREV, VK_MEDIA_PLAY_PAUSE = 0xB0, 0xB1, 0xB3

STATUS_LEVEL = 25          # NSStatusWindowLevel: above the Dock (20) and the menu bar
SYSTEM_OWNERS = ("Window Server", "Dock", "Control Center", "SystemUIServer",
                 "Notification Center", "NotificationCenter", "Spotlight", "TextInputMenuAgent")


def _dpr():
    try:
        from PySide6.QtGui import QGuiApplication
        scr = QGuiApplication.primaryScreen()
        return scr.devicePixelRatio() if scr else 1.0
    except Exception:
        return 1.0


def app_setup():
    """No Dock icon or app menu: Snow Island lives in the menu bar like a utility."""
    try:
        NSApplication.sharedApplication().setActivationPolicy_(1)  # Accessory
    except Exception:
        pass


# ---------------------------------------------------------------- single instance
_lock_file = None


def already_running(name="SnowIsland_SingleInstance_v1"):
    global _lock_file
    path = os.path.join(os.environ.get("TMPDIR", "/tmp"), name + ".lock")
    _lock_file = open(path, "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except OSError:
        return True


# ---------------------------------------------------------------- window tweaks
def _nswindow(wid):
    if objc is None or not wid:
        return None
    try:
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.platformName() != "cocoa":  # e.g. offscreen tests: winId isn't an NSView
            return None
        view = objc.objc_object(c_void_p=int(wid))
        return view.window()
    except Exception:
        return None


def _prepare(win):
    try:
        # all Spaces, stays put in Mission Control, not in Cmd+Tab, over fullscreen apps
        win.setCollectionBehavior_((1 << 0) | (1 << 4) | (1 << 6) | (1 << 8))
        win.setHidesOnDeactivate_(False)
        win.setCanHide_(False)
    except Exception:
        pass


def make_no_activate(wid):
    win = _nswindow(wid)
    if win is None:
        return
    _prepare(win)
    try:
        win.setStyleMask_(win.styleMask() | (1 << 7))  # NSWindowStyleMaskNonactivatingPanel
    except Exception:
        pass


def keep_topmost(wid):
    win = _nswindow(wid)
    if win is None:
        return
    try:
        if win.level() != STATUS_LEVEL:
            _prepare(win)
            win.setLevel_(STATUS_LEVEL)
        win.orderFrontRegardless()
    except Exception:
        pass


# ---------------------------------------------------------------- on-screen windows
_cache = {"t": 0.0, "wins": []}


def _windows(max_age=0.08):
    """Other apps' on-screen windows, front to back: (number, layer, owner, pid, (l, t, r, b))
    in points. Cached briefly because the snow asks many times per frame."""
    now = time.monotonic()
    if now - _cache["t"] < max_age:
        return _cache["wins"]
    out = []
    try:
        info = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID) or []
        for w in info:
            pid = int(w.get("kCGWindowOwnerPID", 0))
            if pid == MY_PID or float(w.get("kCGWindowAlpha", 1.0)) <= 0.01:
                continue
            b = w.get("kCGWindowBounds") or {}
            x, y = float(b.get("X", 0)), float(b.get("Y", 0))
            wd, ht = float(b.get("Width", 0)), float(b.get("Height", 0))
            if wd <= 2 or ht <= 2:
                continue
            out.append((int(w.get("kCGWindowNumber", 0)), int(w.get("kCGWindowLayer", 0)),
                        str(w.get("kCGWindowOwnerName", "")), pid, (x, y, x + wd, y + ht)))
    except Exception:
        pass
    _cache["t"], _cache["wins"] = now, out
    return out


def _screen_rect():
    b = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
    return (b.origin.x, b.origin.y, b.origin.x + b.size.width, b.origin.y + b.size.height)


def _classify(layer, owner, rect, screen):
    if owner == "Dock" and layer >= 20:
        return DOCK_CLASS
    if layer >= 24 and owner in SYSTEM_OWNERS:
        return MENUBAR_CLASS
    return WINDOW_CLASS


def _at_points(x, y):
    screen = None
    for num, layer, owner, pid, (l, t, r, b) in _windows():
        if not (l <= x < r and t <= y < b):
            continue
        if layer > 0:
            # skip invisible full-screen helper layers some apps and the system keep around
            if screen is None:
                screen = _screen_rect()
            if (r - l) * (b - t) >= 0.95 * (screen[2] - screen[0]) * (screen[3] - screen[1]):
                continue
        return num, _classify(layer, owner, (l, t, r, b), screen)
    return 0, DESKTOP_CLASSES[0]


def root_at(x, y):
    """(window number, kind) of what's visible at a physical point; kind is 'Desktop' when
    no app window covers it."""
    d = _dpr()
    return _at_points(x / d, y / d)


def root_class_under_cursor():
    try:
        loc = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        return _at_points(loc.x, loc.y)
    except Exception:
        return 0, WINDOW_CLASS


# ---------------------------------------------------------------- input
_last_clicks = [None]


def left_button_state():
    """Returns (is_down, was_pressed_since_last_check)."""
    src = Quartz.kCGEventSourceStateCombinedSessionState
    try:
        down = bool(Quartz.CGEventSourceButtonState(src, Quartz.kCGMouseButtonLeft))
        n = Quartz.CGEventSourceCounterForEventType(src, Quartz.kCGEventLeftMouseDown)
    except Exception:
        return False, False
    pressed = _last_clicks[0] is not None and n != _last_clicks[0]
    _last_clicks[0] = n
    return down, pressed


def _osascript(script, wait=False, timeout=4):
    args = ["osascript", "-s", "s", "-e", script]
    if not wait:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def press_key(vk, times=1):
    """Volume keys change the system volume. Media keys are handled by media.py on macOS."""
    step = 6 * times
    if vk == VK_VOLUME_UP:
        _osascript(f"set volume output volume ((output volume of (get volume settings)) + {step})")
    elif vk == VK_VOLUME_DOWN:
        _osascript(f"set volume output volume ((output volume of (get volume settings)) - {step})")
    elif vk == VK_VOLUME_MUTE:
        _osascript("set volume output muted (not (output muted of (get volume settings)))")


# ---------------------------------------------------------------- foreground state
def foreground_info():
    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return int(app.processIdentifier()), str(app.localizedName())
    except Exception:
        return 0, ""


def foreground_is_fullscreen():
    pid, _ = foreground_info()
    if not pid or pid == MY_PID:
        return False
    try:
        s = _screen_rect()
    except Exception:
        return False
    for _n, layer, _o, wpid, (l, t, r, b) in _windows(0.3):
        if wpid == pid and layer == 0 and l <= s[0] and t <= s[1] and r >= s[2] and b >= s[3]:
            return True
    return False


def topmost_windows_over(left, top, right, bottom, own, screen_area):
    """Other apps' floating windows (layer above normal) over the given physical rect,
    for example a screen recorder's controls."""
    d = _dpr()
    left, top, right, bottom = left / d, top / d, right / d, bottom / d
    area = screen_area / (d * d)
    found = []
    for num, layer, owner, _pid, (l, t, r, b) in _windows(0.3):
        if layer <= 0 or layer >= 1000 or owner in SYSTEM_OWNERS:
            continue
        if (r - l) * (b - t) > area * 0.6:
            continue
        if r <= left or l >= right or b <= top or t >= bottom:
            continue
        found.append((num, owner, (l, t, r, b)))
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
    """Returns (percent, charging) or None when there is no battery."""
    try:
        b = psutil.sensors_battery()
    except Exception:
        return None
    if b is None:
        return None
    return int(round(b.percent)), bool(b.power_plugged)


# ---------------------------------------------------------------- desktop icons
ICONS_SCRIPT = """
tell application "Finder"
    set ps to desktop position of every item of desktop
    set sz to 64
    try
        set sz to icon size of icon view options of window of desktop
    end try
    return {sz, ps}
end tell
"""


def parse_icons(text):
    """'{64, {{100, 200}, {300, 400}}}' -> list of (l, t, r, b) in points, each icon image a
    square of the icon size centered on its Finder desktop position."""
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text)]
    if not nums:
        return []
    size, pts = max(16.0, nums[0]), nums[1:]
    half = size / 2
    return [(x - half, y - half, x + half, y + half) for x, y in zip(pts[0::2], pts[1::2])]


class DesktopIcons:
    """Reads where Finder shows the icons on the desktop. Asking Finder is slow-ish, so it
    happens on a background thread every few seconds and rects() returns the latest answer.
    The first time, macOS asks the user to allow Snow Island to control Finder."""

    INTERVAL = 3.0

    def __init__(self):
        self._rects = []
        self._thread = None

    def refresh(self):
        self._rects = parse_icons(_osascript(ICONS_SCRIPT, wait=True, timeout=8))
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
        d = _dpr()
        return [(l * d, t * d, r * d, b * d) for l, t, r, b in self._rects]
