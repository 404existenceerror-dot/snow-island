"""Customization window. Every change applies instantly and is saved automatically."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QHBoxLayout,
                               QLabel, QPushButton, QSlider, QTabWidget, QVBoxLayout, QWidget)

MAC = sys.platform == "darwin"
BAR = "Dock" if MAC else "taskbar"

STYLE = """
QDialog, QWidget { background:#141417; color:#ececf1; font-family:'Segoe UI', 'Helvetica Neue'; font-size:13px; }
QTabWidget::pane { border:1px solid #2a2a30; border-radius:10px; top:-1px; }
QTabBar::tab { background:#1d1d22; padding:8px 18px; border-top-left-radius:8px; border-top-right-radius:8px;
               margin-right:3px; color:#a8a8b3; }
QTabBar::tab:selected { background:#26262d; color:#ffffff; }
QLabel#title { font-size:20px; font-weight:600; }
QLabel#hint { color:#8b8b96; font-size:12px; }
QPushButton { background:#26262d; border:1px solid #33333b; border-radius:8px; padding:7px 14px; }
QPushButton:hover { background:#30303a; }
QComboBox { background:#26262d; border:1px solid #33333b; border-radius:8px; padding:5px 10px; }
QComboBox QAbstractItemView { background:#1d1d22; selection-background-color:#2f3b48; }
QSlider::groove:horizontal { height:4px; background:#33333b; border-radius:2px; }
QSlider::sub-page:horizontal { background:#7dd3fc; border-radius:2px; }
QSlider::handle:horizontal { background:#ffffff; width:16px; height:16px; margin:-6px 0; border-radius:8px; }
QCheckBox::indicator { width:18px; height:18px; }
"""


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None, on_feedback=None):
        super().__init__(parent)
        self.settings = settings
        self.refreshers = []
        self.setWindowTitle("Snow Island – Settings")
        self.setStyleSheet(STYLE)
        self.resize(500, 640)

        root = QVBoxLayout(self)
        t = QLabel("Snow Island")
        t.setObjectName("title")
        root.addWidget(t)
        h = QLabel("Changes apply right away and are saved automatically.")
        h.setObjectName("hint")
        root.addWidget(h)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # ---------------- Island
        f = self._tab(tabs, "Island")
        self._color(f, "island_color", "Island color")
        self._color(f, "accent_color", "Accent color")
        self._color(f, "text_color", "Text color")
        self._combo(f, "island_position", "Position",
                    [("top-center", "Top center"), ("top-left", "Top left"), ("top-right", "Top right"),
                     ("bottom-center", "Bottom center"), ("bottom-left", "Bottom left"),
                     ("bottom-right", "Bottom right"), ("custom", "Where I dragged it")])
        self._slider(f, "island_offset_y", "Distance from edge", 0, 200, 1, "{} px")
        self._slider(f, "island_offset_x", "Move sideways", -800, 800, 1, "{} px")
        self._slider(f, "island_scale", "Size", 60, 180, 100, "{:.0%}")
        self._slider(f, "island_width", "Width", 70, 180, 100, "{:.0%}")
        self._check(f, "island_locked", "Lock position (no dragging)")
        hint = QLabel("Tip: drag the island with the mouse to put it anywhere. Drop it near the top "
                      "center to snap it back.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        f.addRow(hint)
        self._slider(f, "island_opacity", "Opacity", 30, 100, 100, "{:.0%}")
        self._slider(f, "corner_roundness", "Corner roundness", 0, 100, 100, "{:.0%}")
        self._check(f, "clock_24h", "24-hour clock")
        self._check(f, "show_seconds", "Show seconds when expanded")
        self._check(f, "show_date", "Show date")

        # ---------------- Widgets
        f = self._tab(tabs, "Widgets")
        self._check(f, "show_media", "Music player (Spotify and other apps)")
        self._check(f, "peek_on_track_change", "Pop out when the song changes")
        self._check(f, "show_battery", "Battery")
        self._check(f, "show_system", "CPU and RAM usage")
        self._check(f, "scroll_volume", "Scroll on the island to change volume")
        self._slider(f, "timer_step_min", "Timer button adds", 1, 30, 1, "{} min")
        self._check(f, "hide_in_fullscreen", "Hide during fullscreen apps and games")
        self._check(f, "start_with_windows", "Start when I log in" if MAC else "Start with Windows")

        # ---------------- Winter
        f = self._tab(tabs, "Winter")
        self._check(f, "winter_enabled", "Winter mode")
        self._slider(f, "snow_amount", "Amount of snow", 20, 600, 1, "{} flakes")
        self._slider(f, "snow_size", "Flake size", 50, 220, 100, "{:.0%}")
        self._slider(f, "snow_speed", "Fall speed", 30, 250, 100, "{:.0%}")
        self._slider(f, "wind", "Wind", -150, 150, 100, "{:+.2f}")
        self._slider(f, "accumulation", "How fast snow piles up", 20, 800, 100, "{:.1f}×")
        self._slider(f, "max_pile", "Max pile height", 4, 40, 1, "{} px")
        self._combo(f, "snowball_mode", "Snowballs on click",
                    [("desktop", "Only on the desktop"), ("everywhere", "Everywhere"), ("off", "Off")])
        self._check(f, "icon_piles", "Snow piles up on desktop icons")
        self._check(f, "mouse_brush", "Flick the mouse over an icon to brush its snow off")
        self._check(f, "ground_snow", f"Snow piles up on the {BAR}")
        self._check(f, "piles_only_on_desktop", "Hide piles and snowmen behind open windows")
        self._check(f, "snow_over_apps", "Keep snowing over open apps")
        self._slider(f, "fps", "Animation smoothness", 15, 60, 1, "{} fps")
        self._slider(f, "tractor_speed", "Snow truck speed", 50, 300, 100, "{:.0%}")
        self._slider(f, "auto_plow_min", "Truck comes by itself every", 0, 60, 1, "{} min")
        self._color(f, "tractor_color", "Snow truck color")
        self._color(f, "scarf_color", "Snowman scarf color")
        h2 = QLabel("Set the truck timer to 0 to only call it yourself. Snowman: press and hold on the "
                    f"{BAR} snow and drag sideways to roll a big ball, then let go. Roll two more, lift "
                    "each one up and drop it on top.")
        h2.setObjectName("hint")
        h2.setWordWrap(True)
        f.addRow(h2)

        # keep the controls in sync when the island is dragged around
        settings.changed.connect(self._external_change)

        row = QHBoxLayout()
        reset = QPushButton("Reset to defaults")
        reset.clicked.connect(self._reset)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(reset)
        if on_feedback:
            fb = QPushButton("Report a bug / feedback")
            fb.clicked.connect(on_feedback)
            row.addWidget(fb)
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)

    # ---------------------------------------------------------------- builders
    def _tab(self, tabs, name):
        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(16, 16, 16, 16)
        f.setVerticalSpacing(12)
        f.setLabelAlignment(Qt.AlignLeft)
        tabs.addTab(w, name)
        return f

    def _check(self, form, key, label):
        cb = QCheckBox(label)
        cb.setChecked(bool(self.settings[key]))
        cb.toggled.connect(lambda v: self.settings.set(key, bool(v)))
        self.refreshers.append(lambda: cb.setChecked(bool(self.settings[key])))
        form.addRow(cb)

    def _slider(self, form, key, label, lo, hi, div, fmt):
        row = QHBoxLayout()
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        val = QLabel()
        val.setMinimumWidth(78)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        def show(v):
            val.setText(fmt.format(v / div if div != 1 else v))

        def changed(v):
            show(v)
            self.settings.set(key, v / div if div != 1 else int(v))

        def refresh():
            s.blockSignals(True)
            s.setValue(int(round(float(self.settings[key]) * div)))
            s.blockSignals(False)
            show(s.value())

        refresh()
        s.valueChanged.connect(changed)
        self.refreshers.append(refresh)
        row.addWidget(s, 1)
        row.addWidget(val)
        form.addRow(label, row)

    def _combo(self, form, key, label, options):
        c = QComboBox()
        for v, text in options:
            c.addItem(text, v)

        def refresh():
            c.blockSignals(True)
            i = c.findData(self.settings[key])
            c.setCurrentIndex(max(0, i))
            c.blockSignals(False)

        refresh()
        c.currentIndexChanged.connect(lambda _i: self.settings.set(key, c.currentData()))
        self.refreshers.append(refresh)
        form.addRow(label, c)

    def _color(self, form, key, label):
        b = QPushButton()
        b.setFixedWidth(120)

        def refresh():
            col = self.settings[key]
            txt = "#000" if QColor(col).lightness() > 140 else "#fff"
            b.setText(col)
            b.setStyleSheet(f"background:{col}; color:{txt}; border:1px solid #444; border-radius:8px;")

        def pick():
            col = QColorDialog.getColor(QColor(self.settings[key]), self, label)
            if col.isValid():
                self.settings.set(key, col.name())
                refresh()

        refresh()
        b.clicked.connect(pick)
        self.refreshers.append(refresh)
        form.addRow(label, b)

    def _external_change(self, key):
        if key in ("island_position", "island_offset_x", "island_offset_y", "island_locked",
                   "winter_enabled"):
            for r in self.refreshers:
                r()

    def _reset(self):
        self.settings.reset()
        for r in self.refreshers:
            r()
