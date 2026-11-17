"""Small Windows helpers built on ctypes (no extra packages needed)."""
import ctypes
import ctypes.wintypes as wt

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def _sig(fn, res, *args):
    fn.restype = res
    fn.argtypes = list(args)
    return fn


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT),
                ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", wt.BYTE), ("BatteryFlag", wt.BYTE),
                ("BatteryLifePercent", wt.BYTE), ("SystemStatusFlag", wt.BYTE),
                ("BatteryLifeTime", wt.DWORD), ("BatteryFullLifeTime", wt.DWORD)]


FindWindowW = _sig(user32.FindWindowW, wt.HWND, wt.LPCWSTR, wt.LPCWSTR)
FindWindowExW = _sig(user32.FindWindowExW, wt.HWND, wt.HWND, wt.HWND, wt.LPCWSTR, wt.LPCWSTR)
EnumWindows = _sig(user32.EnumWindows, wt.BOOL, WNDENUMPROC, wt.LPARAM)
GetClassNameW = _sig(user32.GetClassNameW, ctypes.c_int, wt.HWND, wt.LPWSTR, ctypes.c_int)
IsWindow = _sig(user32.IsWindow, wt.BOOL, wt.HWND)
IsWindowVisible = _sig(user32.IsWindowVisible, wt.BOOL, wt.HWND)
SendMessageTimeoutW = _sig(user32.SendMessageTimeoutW, LRESULT, wt.HWND, wt.UINT, wt.WPARAM,
                           wt.LPARAM, wt.UINT, wt.UINT, ctypes.POINTER(ctypes.c_size_t))
GetWindowThreadProcessId = _sig(user32.GetWindowThreadProcessId, wt.DWORD, wt.HWND,
                                ctypes.POINTER(wt.DWORD))
MapWindowPoints = _sig(user32.MapWindowPoints, ctypes.c_int, wt.HWND, wt.HWND,
                       ctypes.POINTER(wt.POINT), wt.UINT)
GetForegroundWindow = _sig(user32.GetForegroundWindow, wt.HWND)
WindowFromPoint = _sig(user32.WindowFromPoint, wt.HWND, wt.POINT)
GetAncestor = _sig(user32.GetAncestor, wt.HWND, wt.HWND, wt.UINT)
GetCursorPos = _sig(user32.GetCursorPos, wt.BOOL, ctypes.POINTER(wt.POINT))
GetAsyncKeyState = _sig(user32.GetAsyncKeyState, ctypes.c_short, ctypes.c_int)
GetWindowRect = _sig(user32.GetWindowRect, wt.BOOL, wt.HWND, ctypes.POINTER(wt.RECT))
MonitorFromWindow = _sig(user32.MonitorFromWindow, wt.HMONITOR, wt.HWND, wt.DWORD)
GetMonitorInfoW = _sig(user32.GetMonitorInfoW, wt.BOOL, wt.HMONITOR, ctypes.POINTER(MONITORINFO))
GetWindowLongPtrW = _sig(user32.GetWindowLongPtrW, ctypes.c_ssize_t, wt.HWND, ctypes.c_int)
SetWindowLongPtrW = _sig(user32.SetWindowLongPtrW, ctypes.c_ssize_t, wt.HWND, ctypes.c_int,
                         ctypes.c_ssize_t)
SetWindowPos = _sig(user32.SetWindowPos, wt.BOOL, wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                    ctypes.c_int, ctypes.c_int, wt.UINT)
keybd_event = _sig(user32.keybd_event, None, wt.BYTE, wt.BYTE, wt.DWORD, ctypes.c_size_t)

OpenProcess = _sig(kernel32.OpenProcess, wt.HANDLE, wt.DWORD, wt.BOOL, wt.DWORD)
CloseHandle = _sig(kernel32.CloseHandle, wt.BOOL, wt.HANDLE)
VirtualAllocEx = _sig(kernel32.VirtualAllocEx, ctypes.c_void_p, wt.HANDLE, ctypes.c_void_p,
                      ctypes.c_size_t, wt.DWORD, wt.DWORD)
VirtualFreeEx = _sig(kernel32.VirtualFreeEx, wt.BOOL, wt.HANDLE, ctypes.c_void_p,
                     ctypes.c_size_t, wt.DWORD)
WriteProcessMemory = _sig(kernel32.WriteProcessMemory, wt.BOOL, wt.HANDLE, ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
ReadProcessMemory = _sig(kernel32.ReadProcessMemory, wt.BOOL, wt.HANDLE, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
GetSystemTimes = _sig(kernel32.GetSystemTimes, wt.BOOL, ctypes.POINTER(wt.FILETIME),
                      ctypes.POINTER(wt.FILETIME), ctypes.POINTER(wt.FILETIME))
GlobalMemoryStatusEx = _sig(kernel32.GlobalMemoryStatusEx, wt.BOOL, ctypes.POINTER(MEMORYSTATUSEX))
GetSystemPowerStatus = _sig(kernel32.GetSystemPowerStatus, wt.BOOL,
                            ctypes.POINTER(SYSTEM_POWER_STATUS))
CreateMutexW = _sig(kernel32.CreateMutexW, wt.HANDLE, ctypes.c_void_p, wt.BOOL, wt.LPCWSTR)

DESKTOP_CLASSES = ("Progman", "WorkerW")
SHELL_UI_CLASSES = ("Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Windows.UI.Core.CoreWindow",
                    "NotifyIconOverflowWindow", "TopLevelWindowForOverflowXamlIsland",
                    "XamlExplorerHostIslandWindow", "#32768")


def class_name(hwnd):
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, buf, 256)
    return buf.value


def root_of(hwnd):
    return GetAncestor(hwnd, 2) if hwnd else None  # GA_ROOT


def hwnd_val(h):
    return int(h or 0)


# ---------------------------------------------------------------- single instance
_mutex = None


def already_running(name="SnowIsland_SingleInstance_v1"):
    global _mutex
    _mutex = CreateMutexW(None, False, name)
    return ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS


# ---------------------------------------------------------------- window tweaks
def make_no_activate(hwnd):
    GWL_EXSTYLE = -20
    ex = GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    ex |= 0x08000000 | 0x00000080  # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
    SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)


def keep_topmost(hwnd):
    HWND_TOPMOST = wt.HWND(-1 & 0xFFFFFFFFFFFFFFFF)
    SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # NOSIZE|NOMOVE|NOACTIVATE


# ---------------------------------------------------------------- input
def cursor_pos_physical():
    pt = wt.POINT()
    GetCursorPos(ctypes.byref(pt))
    return pt


def left_button_state():
    """Returns (is_down, was_pressed_since_last_check)."""
    s = GetAsyncKeyState(0x01)
    return bool(s & 0x8000), bool(s & 0x0001)


def root_class_under_cursor():
    pt = cursor_pos_physical()
    h = WindowFromPoint(pt)
    r = root_of(h)
    return hwnd_val(r), class_name(r)


def root_at(x, y):
    """(root hwnd, root class) of the window at a physical screen point."""
    r = root_of(WindowFromPoint(wt.POINT(int(x), int(y))))
    return hwnd_val(r), class_name(r)


def press_key(vk, times=1):
    for _ in range(times):
        keybd_event(vk, 0, 0, 0)
        keybd_event(vk, 0, 2, 0)


VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF
VK_MEDIA_NEXT, VK_MEDIA_PREV, VK_MEDIA_PLAY_PAUSE = 0xB0, 0xB1, 0xB3


# ---------------------------------------------------------------- foreground state
def foreground_info():
    fg = GetForegroundWindow()
    return hwnd_val(fg), class_name(fg)


def foreground_is_fullscreen():
    fg = GetForegroundWindow()
    if not fg:
        return False
    cls = class_name(fg)
    if cls in DESKTOP_CLASSES or cls in SHELL_UI_CLASSES:
        return False
    r = wt.RECT()
    GetWindowRect(fg, ctypes.byref(r))
    mon = MonitorFromWindow(fg, 2)
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not GetMonitorInfoW(mon, ctypes.byref(mi)):
        return False
    m = mi.rcMonitor
    return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom


# ---------------------------------------------------------------- other apps' always-on-top windows
dwmapi = ctypes.WinDLL("dwmapi")
DwmGetWindowAttribute = _sig(dwmapi.DwmGetWindowAttribute, ctypes.c_long, wt.HWND, wt.DWORD,
                             ctypes.c_void_p, wt.DWORD)
IGNORE_TOPMOST_CLASSES = SHELL_UI_CLASSES + DESKTOP_CLASSES + ("Progman",)


def _cloaked(hwnd):
    v = wt.DWORD()
    if DwmGetWindowAttribute(hwnd, 14, ctypes.byref(v), ctypes.sizeof(v)) == 0:  # DWMWA_CLOAKED
        return v.value != 0
    return False


def topmost_windows_over(left, top, right, bottom, own, screen_area):
    """Other apps' visible always-on-top windows that overlap the given physical rect
    (for example a screen recorder's Stop toolbar). Huge invisible overlays are ignored."""
    found = []

    def cb(hwnd, _lp):
        h = hwnd_val(hwnd)
        if h in own or not IsWindowVisible(hwnd):
            return True
        if not (GetWindowLongPtrW(hwnd, -20) & 0x00000008):  # WS_EX_TOPMOST
            return True
        r = wt.RECT()
        GetWindowRect(hwnd, ctypes.byref(r))
        w, hgt = r.right - r.left, r.bottom - r.top
        if w <= 2 or hgt <= 2 or w * hgt > screen_area * 0.6:
            return True
        if r.right <= left or r.left >= right or r.bottom <= top or r.top >= bottom:
            return True
        cls = class_name(hwnd)
        if cls in IGNORE_TOPMOST_CLASSES or _cloaked(hwnd):
            return True
        found.append((h, cls, (r.left, r.top, r.right, r.bottom)))
        return True

    proc = WNDENUMPROC(cb)
    EnumWindows(proc, 0)
    return found


# ---------------------------------------------------------------- system stats
def _ft(ft):
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


class CpuMeter:
    def __init__(self):
        self.prev = self._times()

    def _times(self):
        i, k, u = wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
        GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
        return _ft(i), _ft(k), _ft(u)

    def percent(self):
        cur = self._times()
        di, dk, du = (c - p for c, p in zip(cur, self.prev))
        self.prev = cur
        total = dk + du
        if total <= 0:
            return 0
        return max(0, min(100, round(100 * (1 - di / total))))


def memory_percent():
    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    GlobalMemoryStatusEx(ctypes.byref(m))
    return int(m.dwMemoryLoad)


def battery():
    """Returns (percent, charging) or None when there is no battery."""
    s = SYSTEM_POWER_STATUS()
    if not GetSystemPowerStatus(ctypes.byref(s)):
        return None
    if s.BatteryFlag & 128 or s.BatteryLifePercent == 255:
        return None
    return int(s.BatteryLifePercent), s.ACLineStatus == 1


# ---------------------------------------------------------------- desktop icons
LVM_GETITEMCOUNT = 0x1004
LVM_GETITEMRECT = 0x100E
LVIR_ICON = 1


class DesktopIcons:
    """Reads the screen rectangles of the icons on the Windows desktop."""

    def __init__(self):
        self.lv = None
        self.hproc = None
        self.remote = None

    def _find_listview(self):
        progman = FindWindowW("Progman", None)
        defview = FindWindowExW(progman, None, "SHELLDLL_DefView", None) if progman else None
        if not defview:
            found = []

            def cb(hwnd, _lp):
                dv = FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
                if dv:
                    found.append(dv)
                    return False
                return True

            proc = WNDENUMPROC(cb)
            EnumWindows(proc, 0)
            defview = found[0] if found else None
        if not defview:
            return None
        return FindWindowExW(defview, None, "SysListView32", None)

    def _close(self):
        if self.hproc:
            if self.remote:
                VirtualFreeEx(self.hproc, self.remote, 0, 0x8000)
            CloseHandle(self.hproc)
        self.hproc = self.remote = None
        self.lv = None

    def _ensure(self):
        if self.lv and IsWindow(self.lv):
            return True
        self._close()
        lv = self._find_listview()
        if not lv:
            return False
        pid = wt.DWORD()
        GetWindowThreadProcessId(lv, ctypes.byref(pid))
        h = OpenProcess(0x0008 | 0x0010 | 0x0020 | 0x0400, False, pid.value)
        if not h:
            return False
        remote = VirtualAllocEx(h, None, 4096, 0x1000 | 0x2000, 0x04)
        if not remote:
            CloseHandle(h)
            return False
        self.lv, self.hproc, self.remote = lv, h, remote
        return True

    def _send(self, msg, wparam, lparam):
        res = ctypes.c_size_t()
        ok = SendMessageTimeoutW(self.lv, msg, wparam, lparam, 0x0002, 300, ctypes.byref(res))
        return res.value if ok else 0

    def rects(self):
        """List of (left, top, right, bottom) in physical screen pixels."""
        try:
            if not self._ensure() or not IsWindowVisible(self.lv):
                return []
            count = self._send(LVM_GETITEMCOUNT, 0, 0)
            out = []
            for i in range(min(count, 400)):
                r = wt.RECT(LVIR_ICON, 0, 0, 0)
                WriteProcessMemory(self.hproc, self.remote, ctypes.byref(r), ctypes.sizeof(r), None)
                if not self._send(LVM_GETITEMRECT, i, self.remote):
                    continue
                ReadProcessMemory(self.hproc, self.remote, ctypes.byref(r), ctypes.sizeof(r), None)
                pts = (wt.POINT * 2)(wt.POINT(r.left, r.top), wt.POINT(r.right, r.bottom))
                MapWindowPoints(self.lv, None, pts, 2)
                out.append((pts[0].x, pts[0].y, pts[1].x, pts[1].y))
            return out
        except Exception:
            self._close()
            return []

    def __del__(self):
        try:
            self._close()
        except Exception:
            pass
