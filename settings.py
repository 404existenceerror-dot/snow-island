"""Settings stored as JSON in %APPDATA%\\SnowIsland\\settings.json."""
import copy
import json
import os

from PySide6.QtCore import QObject, QTimer, Signal

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SnowIsland")
PATH = os.path.join(APP_DIR, "settings.json")

DEFAULTS = {
    # Dynamic island
    "island_color": "#000000",
    "accent_color": "#7dd3fc",
    "text_color": "#ffffff",
    "island_opacity": 0.97,
    "island_scale": 1.0,
    "island_offset_y": 8,
    "island_offset_x": 0,
    "island_width": 1.0,
    "island_position": "top-center",  # top-/bottom- left/center/right, or custom (dragged)
    "island_x": -1,  # custom position: pill center, in screen coordinates
    "island_y": -1,
    "island_locked": False,
    "corner_roundness": 1.0,
    "clock_24h": True,
    "show_seconds": False,
    "show_date": True,
    "show_media": True,
    "show_system": True,
    "show_battery": True,
    "peek_on_track_change": True,
    "scroll_volume": True,
    "hide_in_fullscreen": True,
    "start_with_windows": False,
    "timer_step_min": 5,
    # Winter mode
    "winter_enabled": True,
    "snow_amount": 160,
    "snow_size": 1.0,
    "snow_speed": 1.0,
    "wind": 0.15,
    "max_pile": 16,
    "accumulation": 1.5,
    "snowball_mode": "desktop",  # desktop / everywhere / off
    "piles_only_on_desktop": True,
    "snow_over_apps": True,
    "ground_snow": True,
    "fps": 30,
    "tractor_speed": 1.0,
    "tractor_color": "#e8452c",
    "icon_piles": True,
    "mouse_brush": True,
    "auto_plow_min": 0,
    "scarf_color": "#e11d48",
}


class Settings(QObject):
    changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.data = copy.deepcopy(DEFAULTS)
        try:
            with open(PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in DEFAULTS:
                    self.data[k] = v
        except Exception:
            pass
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self.save)

    def __getitem__(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def get(self, key):
        return self[key]

    def set(self, key, value):
        if self.data.get(key) == value:
            return
        self.data[key] = value
        self._save_timer.start()
        self.changed.emit(key)

    def reset(self):
        self.data = copy.deepcopy(DEFAULTS)
        self.save()
        for k in DEFAULTS:
            self.changed.emit(k)

    def save(self):
        try:
            os.makedirs(APP_DIR, exist_ok=True)
            with open(PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass
