"""Snow Island – a Dynamic Island + winter mode for Windows 11.

Runs fully locally. Start it with start.bat (or: .venv\\Scripts\\pythonw.exe snow_island.py).
"""
import os
import sys

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

import art
import winapi
from island import MENU_STYLE, DynamicIsland
from media import MediaWatcher
from settings import Settings
from settings_dialog import SettingsDialog
from winter import WinterOverlay

__version__ = "1.0.0"
HERE = os.path.dirname(os.path.abspath(__file__))
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def make_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#0b0b0e"))
    p.drawRoundedRect(QRectF(2, 14, 60, 36), 18, 18)
    art.snowflake(p, 32, 32, 12, QColor("#7dd3fc"), 3.2)
    p.end()
    return QIcon(pm)


class App:
    def __init__(self, qapp):
        self.qapp = qapp
        self.settings = Settings()
        self.media = MediaWatcher()
        self.icons = winapi.DesktopIcons()
        self.dialog = None
        self.island_hidden = False

        self.overlay = WinterOverlay(self.settings, self.icons, self.own_hwnds)
        self.island = DynamicIsland(self.settings, self.media, self)
        self.overlay.on_event = self.on_overlay_event

        self.tray = QSystemTrayIcon(make_icon())
        self.tray.setToolTip(f"Snow Island {__version__}")
        menu = QMenu()
        menu.setStyleSheet(MENU_STYLE)
        self.act_winter = QAction("Winter mode", menu, checkable=True)
        self.act_winter.triggered.connect(self.toggle_winter)
        menu.addAction(self.act_winter)
        menu.addAction("Send the snow truck", self.plow)
        menu.addAction("Melt all snowmen", self.melt_snowmen)
        menu.addSeparator()
        menu.addAction("Show / hide island", self.toggle_island)
        menu.addAction("Settings…", self.open_settings)
        menu.addSeparator()
        menu.addAction("Quit", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.open_settings() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()
        self._menu = menu

        self.settings.changed.connect(self.on_settings)
        self.act_winter.setChecked(bool(self.settings["winter_enabled"]))

        self.island.show()
        self.overlay.set_enabled(bool(self.settings["winter_enabled"]))
        self.raise_island()

        self.watch = QTimer(interval=400, timeout=self.watchdog)
        self.watch.start()

    def own_hwnds(self):
        hs = {int(self.island.winId()), int(self.overlay.winId())}
        if self.dialog is not None:
            hs.add(int(self.dialog.winId()))
        return hs

    def raise_island(self):
        if self.island.isVisible():
            winapi.keep_topmost(int(self.island.winId()))

    def island_blocked(self):
        """True when another app's always-on-top window (e.g. a screen recorder's Stop bar)
        sits where the island is, so the island gets out of its way."""
        scr = QApplication.primaryScreen()
        dpr = scr.devicePixelRatio()
        g = scr.geometry()
        r = self.island.pill_screen_rect().adjusted(-16, -14, 16, 14)
        if r.width() <= 32:
            return False
        rect = (int(r.left() * dpr), int(r.top() * dpr), int(r.right() * dpr), int(r.bottom() * dpr))
        area = g.width() * g.height() * dpr * dpr
        return bool(winapi.topmost_windows_over(*rect, self.own_hwnds(), area))

    def watchdog(self):
        full = self.settings["hide_in_fullscreen"] and winapi.foreground_is_fullscreen()
        want_island = not full and not self.island_hidden and not self.island_blocked()
        if want_island and not self.island.isVisible():
            self.island.show()
        elif not want_island and self.island.isVisible():
            self.island.hide()
        want_snow = not full and (self.settings["winter_enabled"] or self.overlay.tractor is not None)
        if full and self.overlay.isVisible():
            self.overlay.hide()
            self.overlay.timer.stop()
        elif want_snow and not self.overlay.isVisible():
            self.overlay._update_running()
        if self.overlay.isVisible():
            winapi.keep_topmost(int(self.overlay.winId()))
        self.raise_island()

    # ------------------------------------------------------------ actions
    def on_settings(self, key):
        if key == "winter_enabled":
            on = bool(self.settings["winter_enabled"])
            self.act_winter.setChecked(on)
            self.overlay.set_enabled(on)
            self.island.peek("snow", 2.0, "Winter mode on" if on else "Winter mode off")
            self.raise_island()
        elif key == "start_with_windows":
            self.set_autostart(bool(self.settings["start_with_windows"]))

    def toggle_winter(self, *_):
        self.settings.set("winter_enabled", not self.settings["winter_enabled"])

    def plow(self):
        if self.overlay.start_tractor():
            self.island.peek("plow", 2.5, "Snow truck on the way!")
        self.raise_island()

    def melt_snowmen(self):
        self.overlay.melt_snowmen()

    def on_overlay_event(self, kind):
        if kind == "snowman":
            self.island.peek("snowman", 3, "Snowman built!")

    def open_spotify(self):
        try:
            os.startfile("spotify:")
        except OSError:
            self.island.peek("msg", 3, "Spotify isn't installed")

    def toggle_island(self):
        self.island_hidden = not self.island_hidden
        self.watchdog()

    def open_settings(self):
        if self.dialog is None:
            self.dialog = SettingsDialog(self.settings)
            self.dialog.setWindowIcon(make_icon())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def set_autostart(self, on):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                if on:
                    if getattr(sys, "frozen", False):  # packaged SnowIsland.exe
                        cmd = f'"{sys.executable}"'
                    else:
                        exe = sys.executable
                        pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
                        if os.path.exists(pyw):
                            exe = pyw
                        cmd = f'"{exe}" "{os.path.join(HERE, "snow_island.py")}"'
                    winreg.SetValueEx(k, "SnowIsland", 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(k, "SnowIsland")
                    except FileNotFoundError:
                        pass
        except OSError:
            pass

    def quit(self):
        self.settings.save()
        self.tray.hide()
        self.qapp.quit()


def diagnose():
    """`SnowIsland.exe --diagnose` (or `python snow_island.py --diagnose`): writes a small report
    to %APPDATA%\\SnowIsland\\diagnose.txt that users can attach to bug reports."""
    import asyncio
    import platform
    from settings import APP_DIR
    import media
    lines = [f"Snow Island {__version__}", f"Windows: {platform.platform()}",
             f"Python: {platform.python_version()}  frozen: {getattr(sys, 'frozen', False)}",
             f"Media library available: {media.HAVE_WINRT}"]
    if media.HAVE_WINRT:
        async def sessions():
            mgr = await media.MediaManager.request_async()
            out = []
            for s in mgr.get_sessions():
                p = await s.try_get_media_properties_async()
                out.append(f"  {s.source_app_user_model_id}: status {int(s.get_playback_info().playback_status)}"
                           f", has title: {bool(p.title)}, has cover: {p.thumbnail is not None}")
            return out
        try:
            lines += ["Media sessions:"] + (asyncio.run(sessions()) or ["  (none)"])
        except Exception as e:
            lines.append(f"Media error: {e!r}")
    lines.append(f"Desktop icons found: {len(winapi.DesktopIcons().rects())}")
    lines.append(f"Battery: {winapi.battery()}")
    os.makedirs(APP_DIR, exist_ok=True)
    path = os.path.join(APP_DIR, "diagnose.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    try:
        os.startfile(path)
    except OSError:
        pass


def main():
    if "--diagnose" in sys.argv:
        diagnose()
        return
    if winapi.already_running():
        return
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setApplicationName("Snow Island")
    qapp.setWindowIcon(make_icon())
    app = App(qapp)  # noqa: F841 (kept alive for the app's lifetime)
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
