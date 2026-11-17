"""The Dynamic Island: a pill at the top of the screen that grows when you hover it."""
import datetime
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QWidget

import art
import winapi

MENU_STYLE = """
QMenu { background:#1c1c1f; color:#f2f2f2; border:1px solid #333; border-radius:10px; padding:6px; }
QMenu::item { padding:7px 22px 7px 14px; border-radius:6px; }
QMenu::item:selected { background:#2f3b48; }
QMenu::separator { height:1px; background:#333; margin:5px 8px; }
QMenu::indicator { width:14px; height:14px; margin-left:4px; }
"""


def _font(px, weight=QFont.Normal):
    f = QFont("Segoe UI Variable Display")
    if not f.exactMatch():
        f = QFont("Segoe UI")
    f.setPixelSize(max(6, int(px)))
    f.setWeight(weight)
    return f


def _fmt_secs(s):
    s = max(0, int(s))
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"


class DynamicIsland(QWidget):
    def __init__(self, settings, media, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setWindowTitle("Snow Island")
        self.settings = settings
        self.media = media
        self.app = app

        self.media_info = {"available": False}
        self.media_key = None
        self.art_pm = None
        self.cpu = winapi.CpuMeter()
        self.stats = {"cpu": 0, "ram": winapi.memory_percent(), "bat": winapi.battery()}

        self.hovered = False
        self.peek_until = 0.0
        self.peek_kind = None
        self.peek_text = ""
        self.timer_end = None
        self.timer_total = 0
        self.hits = []
        self.drag = None
        self.dragging = False
        self.halign, self.valign, self.anchor_x = "center", "top", 0.0
        self.pill = QRectF()
        self.t0 = time.perf_counter()
        self.last = self.t0

        s = self._s()
        self.cw, self.ch = 160 * s, 36 * s

        self.collapse_timer = QTimer(self, singleShot=True, interval=380, timeout=self._collapse)
        self.frame = QTimer(self, timeout=self.tick)
        self.frame.start(16)
        self.stats_timer = QTimer(self, interval=2000, timeout=self._update_stats)
        self.stats_timer.start()

        media.updated.connect(self.on_media)
        settings.changed.connect(self.on_settings)
        self.apply_geometry()

    # ------------------------------------------------------------ helpers
    def _s(self):
        return float(self.settings["island_scale"])

    def _wf(self):
        return float(self.settings["island_width"])

    def placement(self):
        """Returns (horizontal align, anchor x, vertical align, anchor edge y) in screen coords.
        The pill grows away from its anchor: down from the top, up from the bottom."""
        scr = QApplication.primaryScreen()
        geo, avail = scr.geometry(), scr.availableGeometry()
        s = self._s()
        pos = str(self.settings["island_position"])
        if pos == "custom" and float(self.settings["island_x"]) >= 0:
            cx, cy = float(self.settings["island_x"]), float(self.settings["island_y"])
            valign = "top" if cy < geo.center().y() else "bottom"
            edge = cy - 18 * s if valign == "top" else cy + 18 * s
            return "center", cx, valign, edge
        vert, _, horiz = pos.partition("-")
        if vert not in ("top", "bottom") or horiz not in ("left", "center", "right"):
            vert, horiz = "top", "center"
        oy, ox = float(self.settings["island_offset_y"]), float(self.settings["island_offset_x"])
        edge = geo.top() + oy if vert == "top" else avail.bottom() + 1 - oy
        if horiz == "left":
            ax = geo.left() + 12 + ox
        elif horiz == "right":
            ax = geo.right() + 1 - 12 + ox
        else:
            ax = geo.center().x() + ox
        return horiz, ax, vert, edge

    def apply_geometry(self):
        s = self._s()
        W, H = int(510 * s * max(1.0, self._wf()) + 40), int(270 * s + 30)
        geo = QApplication.primaryScreen().geometry()
        halign, ax, valign, edge = self.placement()
        if halign == "left":
            x = ax - 20
        elif halign == "right":
            x = ax - W + 20
        else:
            x = ax - W / 2
        x = min(max(x, geo.left()), geo.right() + 1 - W)
        y = edge - 4 if valign == "top" else edge - H + 4
        y = min(max(y, geo.top()), geo.bottom() + 1 - H)
        self.halign, self.valign, self.anchor_x = halign, valign, ax
        self.setGeometry(int(x), int(y), W, H)
        self.update()

    def pill_screen_rect(self):
        r = self.pill
        return QRectF(r.x() + self.x(), r.y() + self.y(), r.width(), r.height())

    def showEvent(self, e):
        super().showEvent(e)
        winapi.make_no_activate(int(self.winId()))

    def on_settings(self, key):
        if key in ("island_scale", "island_offset_y", "island_offset_x", "island_width",
                   "island_position", "island_x", "island_y"):
            self.apply_geometry()
        self.update()

    def _update_stats(self):
        self.stats = {"cpu": self.cpu.percent(), "ram": winapi.memory_percent(), "bat": winapi.battery()}

    def on_media(self, info):
        self.media_info = info
        key = info.get("key")
        if key != self.media_key:
            first = self.media_key is None
            self.media_key = key
            self.art_pm = None
            data = info.get("thumb")
            if data:
                img = QImage.fromData(data)
                if not img.isNull():
                    self.art_pm = QPixmap.fromImage(img.scaled(160, 160, Qt.KeepAspectRatioByExpanding,
                                                               Qt.SmoothTransformation))
            if (not first and info.get("available") and info.get("playing")
                    and self.settings["peek_on_track_change"] and self.settings["show_media"]):
                self.peek("track", 3.5)

    def peek(self, kind, secs, text=""):
        self.peek_kind = kind
        self.peek_text = text
        self.peek_until = time.time() + secs

    def playing(self):
        m = self.media_info
        return bool(self.settings["show_media"] and m.get("available") and m.get("playing"))

    def state(self):
        if self.dragging:
            return "compact"
        if self.hovered:
            return "expanded"
        if time.time() < self.peek_until:
            return "peek"
        return "compact"

    def target_size(self, st):
        s = self._s()
        if st == "compact":
            w = 150
            if self.playing():
                w = 236
            if self.timer_end:
                w = max(w, 210) + (40 if self.playing() else 0)
            return w * s * self._wf(), 36 * s
        if st == "peek":
            return 370 * s * self._wf(), 72 * s
        h = 18 + 50 + 14 + 36 + 18
        if self.settings["show_media"]:
            h += 66 + 12
        return 470 * s * max(1.0, self._wf()), h * s

    def time_str(self, seconds=None):
        now = datetime.datetime.now()
        sec = self.settings["show_seconds"] if seconds is None else seconds
        if self.settings["clock_24h"]:
            return now.strftime("%H:%M:%S" if sec else "%H:%M")
        return now.strftime("%I:%M:%S %p" if sec else "%I:%M %p").lstrip("0")

    def media_pos(self):
        m = self.media_info
        pos = m.get("pos", 0.0)
        if m.get("playing"):
            pos += time.time() - m.get("pos_ts", time.time())
        dur = m.get("dur", 0.0)
        return (min(pos, dur) if dur else pos), dur

    # ------------------------------------------------------------ loop
    def tick(self):
        now = time.perf_counter()
        dt = min(0.05, now - self.last)
        self.last = now
        tw, th = self.target_size(self.state())
        k = min(1.0, dt * 13)
        self.cw += (tw - self.cw) * k
        self.ch += (th - self.ch) * k
        if abs(tw - self.cw) < 0.4:
            self.cw = tw
        if abs(th - self.ch) < 0.4:
            self.ch = th
        if self.timer_end and time.time() >= self.timer_end:
            self.timer_end = None
            self.peek("timer", 6, "Timer done!")
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
        animating = self.cw != tw or self.ch != th
        busy = animating or self.hovered or self.playing() or self.state() == "peek"
        self.frame.setInterval(16 if animating else (33 if busy else 250))
        self.update()

    def _collapse(self):
        self.hovered = False

    # ------------------------------------------------------------ painting
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = self._s()
        w, h = self.cw, self.ch
        ax = self.anchor_x - self.x()
        if self.halign == "left":
            px = ax
        elif self.halign == "right":
            px = ax - w
        else:
            px = ax - w / 2
        px = min(max(px, 6), self.width() - w - 6)
        py = 4 if self.valign == "top" else self.height() - h - 4
        r = QRectF(px, py, w, h)
        self.pill = QRectF(r)
        rad = min(h / 2, (20 + 18 * float(self.settings["corner_roundness"])) * s)

        # soft shadow
        p.setPen(Qt.NoPen)
        for i in range(1, 7):
            p.setBrush(QColor(0, 0, 0, max(0, 22 - i * 3)))
            p.drawRoundedRect(r.adjusted(-i, -i + 3, i, i + 3), rad + i, rad + i)

        bg = QColor(self.settings["island_color"])
        bg.setAlphaF(float(self.settings["island_opacity"]))
        p.setBrush(bg)
        p.drawRoundedRect(r, rad, rad)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), rad, rad)

        clip = QPainterPath()
        clip.addRoundedRect(r, rad, rad)
        p.setClipPath(clip)

        st = self.state()
        tw, th = self.target_size(st)
        closeness = 1 - min(1.0, (abs(tw - self.cw) + abs(th - self.ch)) / (40 * s))
        p.setOpacity(max(0.0, closeness) ** 1.5)
        self.hits = []
        if st == "compact":
            self.paint_compact(p, r, s)
        elif st == "peek":
            self.paint_peek(p, r, s)
        else:
            self.paint_expanded(p, r, s)
        p.end()

    def _text_color(self, alpha=255):
        c = QColor(self.settings["text_color"])
        c.setAlpha(alpha)
        return c

    def _accent(self, alpha=255):
        c = QColor(self.settings["accent_color"])
        c.setAlpha(alpha)
        return c

    def _art(self, p, rect, radius):
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        p.save()
        p.setClipPath(path, Qt.IntersectClip)
        if self.art_pm:
            p.drawPixmap(rect, self.art_pm, QRectF(self.art_pm.rect()))
        else:
            p.fillRect(rect, QColor(255, 255, 255, 25))
            if self.media_info.get("is_spotify"):
                art.spotify_icon(p, rect.center().x(), rect.center().y(), rect.width() * 0.3)
            else:
                art.play(p, rect.center().x(), rect.center().y(), rect.width() * 0.25, self._text_color(160))
        p.restore()

    def _eq(self, p, x, cy, height, s, color):
        t = time.perf_counter() - self.t0
        bw = 3 * s
        for i in range(4):
            amp = 0.3 + 0.7 * abs(math.sin(t * (5.1 + i * 1.7) + i * 1.3))
            bh = height * amp
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x + i * (bw + 2.2 * s), cy - bh / 2, bw, bh), bw / 2, bw / 2)
        return 4 * bw + 3 * 2.2 * s

    def paint_compact(self, p, r, s):
        cy = r.center().y()
        p.setFont(_font(14 * s, QFont.DemiBold))
        p.setPen(self._text_color())
        playing = self.playing()
        if playing:
            self._art(p, QRectF(r.left() + 7 * s, cy - 11 * s, 22 * s, 22 * s), 6 * s)
        p.drawText(r, Qt.AlignCenter, self.time_str(False))
        right = r.right() - 14 * s
        if self.timer_end:
            p.setFont(_font(12.5 * s, QFont.DemiBold))
            txt = _fmt_secs(self.timer_end - time.time())
            fm = QFontMetricsF(p.font())
            tx = right - fm.horizontalAdvance(txt) - (34 * s if playing else 0)
            p.setPen(QColor("#fbbf24"))
            p.drawText(QPointF(tx, cy + fm.ascent() / 2 - 1), txt)
        if playing:
            self._eq(p, right - 20 * s, cy, 14 * s, s, self._accent())
        elif not self.timer_end and self.settings["winter_enabled"]:
            art.snowflake(p, right - 4 * s, cy, 6 * s, self._accent(200), 1.2 * s)

    def paint_peek(self, p, r, s):
        cy = r.center().y()
        if self.peek_kind == "track" and self.media_info.get("available"):
            ar = QRectF(r.left() + 12 * s, cy - 24 * s, 48 * s, 48 * s)
            self._art(p, ar, 11 * s)
            tx = ar.right() + 12 * s
            tw = r.right() - 52 * s - tx
            p.setFont(_font(14 * s, QFont.DemiBold))
            fm = QFontMetricsF(p.font())
            p.setPen(self._text_color())
            p.drawText(QPointF(tx, cy - 3 * s), fm.elidedText(self.media_info.get("title", ""), Qt.ElideRight, tw))
            p.setFont(_font(12 * s))
            fm = QFontMetricsF(p.font())
            p.setPen(self._text_color(150))
            p.drawText(QPointF(tx, cy + 15 * s), fm.elidedText(self.media_info.get("artist", ""), Qt.ElideRight, tw))
            self._eq(p, r.right() - 40 * s, cy, 20 * s, s, self._accent())
        else:
            if self.peek_kind == "timer":
                art.timer_icon(p, r.left() + 34 * s, cy, 14 * s, "#fbbf24")
            elif self.peek_kind == "snow":
                art.snowflake(p, r.left() + 34 * s, cy, 13 * s, self._accent(), 2 * s)
            elif self.peek_kind == "snowman":
                art.snowman(p, r.left() + 34 * s, cy + 22 * s, [11 * s, 8 * s, 6 * s], True,
                            self.settings["scarf_color"], outline=False)
            elif self.peek_kind == "plow":
                art.tractor(p, r.left() + 38 * s, cy + 13 * s, 30 * s, 1, 0, True,
                            self.settings["tractor_color"], shadow=False)
            p.setFont(_font(16 * s, QFont.DemiBold))
            p.setPen(self._text_color())
            p.drawText(r.adjusted(60 * s, 0, -16 * s, 0), Qt.AlignVCenter | Qt.AlignLeft, self.peek_text)

    def paint_expanded(self, p, r, s):
        pad = 18 * s
        x0 = r.left() + pad
        inner_w = r.width() - 2 * pad
        y = r.top() + pad * 0.75

        # ---- clock + date
        p.setPen(self._text_color())
        p.setFont(_font(30 * s, QFont.DemiBold))
        fm = QFontMetricsF(p.font())
        p.drawText(QPointF(x0, y + fm.ascent() - 2 * s), self.time_str())
        if self.settings["show_date"]:
            p.setFont(_font(12 * s))
            p.setPen(self._text_color(150))
            p.drawText(QPointF(x0 + 1, y + 50 * s), datetime.datetime.now().strftime("%A, %d %B"))

        # ---- system chips (right side)
        chips = []
        if self.settings["show_battery"] and self.stats.get("bat"):
            chips.append(("bat", f"{self.stats['bat'][0]}%"))
        if self.settings["show_system"]:
            chips.append(("txt", f"CPU {self.stats['cpu']}%"))
            chips.append(("txt", f"RAM {self.stats['ram']}%"))
        p.setFont(_font(11 * s, QFont.DemiBold))
        fm = QFontMetricsF(p.font())
        cx = r.right() - pad
        cy = y + 6 * s
        for kind, txt in reversed(chips):
            tw = fm.horizontalAdvance(txt) + (26 * s if kind == "bat" else 16 * s)
            rect = QRectF(cx - tw, cy, tw, 22 * s)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 22))
            p.drawRoundedRect(rect, 11 * s, 11 * s)
            tx = rect.left() + 8 * s
            if kind == "bat":
                pct, charging = self.stats["bat"]
                art.battery(p, QRectF(tx, rect.center().y() - 4.5 * s, 15 * s, 9 * s), pct, charging,
                            self._text_color(200))
                tx += 19 * s
            p.setPen(self._text_color(210))
            p.drawText(QPointF(tx, rect.center().y() + fm.ascent() / 2 - 1.5 * s), txt)
            cx = rect.left() - 6 * s
        y += 50 * s + 14 * s

        # ---- media card
        if self.settings["show_media"]:
            self.paint_media(p, QRectF(x0, y, inner_w, 66 * s), s)
            y += 66 * s + 12 * s

        # ---- buttons
        self.paint_buttons(p, QRectF(x0, y, inner_w, 36 * s), s)

    def paint_media(self, p, rect, s):
        m = self.media_info
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 14))
        p.drawRoundedRect(rect, 16 * s, 16 * s)
        cy = rect.center().y()
        if not m.get("available"):
            art.spotify_icon(p, rect.left() + 32 * s, cy, 17 * s)
            p.setFont(_font(13 * s, QFont.DemiBold))
            p.setPen(self._text_color())
            p.drawText(QPointF(rect.left() + 60 * s, cy - 3 * s), "Nothing playing")
            p.setFont(_font(11.5 * s))
            p.setPen(self._text_color(140))
            p.drawText(QPointF(rect.left() + 60 * s, cy + 14 * s), "Play something in Spotify")
            b = QRectF(rect.right() - 118 * s, cy - 15 * s, 106 * s, 30 * s)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#1DB954"))
            p.drawRoundedRect(b, 15 * s, 15 * s)
            p.setFont(_font(12 * s, QFont.DemiBold))
            p.setPen(QColor("#000000"))
            p.drawText(b, Qt.AlignCenter, "Open Spotify")
            self.hits.append((b, "open_spotify"))
            return

        ar = QRectF(rect.left() + 6 * s, rect.top() + 6 * s, rect.height() - 12 * s, rect.height() - 12 * s)
        self._art(p, ar, 12 * s)
        ctrl_w = 112 * s
        tx = ar.right() + 12 * s
        tw = rect.right() - ctrl_w - tx - 6 * s
        p.setFont(_font(13.5 * s, QFont.DemiBold))
        fm = QFontMetricsF(p.font())
        p.setPen(self._text_color())
        p.drawText(QPointF(tx, rect.top() + 22 * s), fm.elidedText(m.get("title", ""), Qt.ElideRight, tw))
        p.setFont(_font(11.5 * s))
        fm = QFontMetricsF(p.font())
        p.setPen(self._text_color(150))
        p.drawText(QPointF(tx, rect.top() + 39 * s), fm.elidedText(m.get("artist", ""), Qt.ElideRight, tw))
        pos, dur = self.media_pos()
        if dur > 0:
            bar = QRectF(tx, rect.top() + 49 * s, tw, 4 * s)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 40))
            p.drawRoundedRect(bar, 2 * s, 2 * s)
            fill = QRectF(bar)
            fill.setWidth(max(4 * s, bar.width() * min(1.0, pos / dur)))
            p.setBrush(self._accent())
            p.drawRoundedRect(fill, 2 * s, 2 * s)
            p.setFont(_font(9.5 * s))
            p.setPen(self._text_color(120))
            p.drawText(QRectF(bar.left(), bar.bottom() + 1, bar.width(), 12 * s), Qt.AlignLeft, _fmt_secs(pos))
            p.drawText(QRectF(bar.left(), bar.bottom() + 1, bar.width(), 12 * s), Qt.AlignRight, _fmt_secs(dur))

        # controls
        bx = rect.right() - ctrl_w
        for i, act in enumerate(("prev", "toggle", "next")):
            c = QPointF(bx + 18 * s + i * 38 * s, cy)
            rr = 17 * s if act == "toggle" else 14 * s
            hit = QRectF(c.x() - 18 * s, c.y() - 18 * s, 36 * s, 36 * s)
            if act == "toggle":
                p.setPen(Qt.NoPen)
                p.setBrush(self._text_color())
                p.drawEllipse(c, rr, rr)
                if m.get("playing"):
                    art.pause(p, c.x(), c.y(), 9 * s, "#000000")
                else:
                    art.play(p, c.x() + 1.5 * s, c.y(), 10 * s, "#000000")
            else:
                art.skip(p, c.x(), c.y(), 9 * s, self._text_color(), forward=(act == "next"))
            self.hits.append((hit, act))

    def paint_buttons(self, p, rect, s):
        winter = self.settings["winter_enabled"]
        timer_label = _fmt_secs(self.timer_end - time.time()) if self.timer_end else "Timer"
        buttons = [("winter", "Snow", winter), ("plow", "Truck", False),
                   ("timer", timer_label, bool(self.timer_end)), ("spotify", "Spotify", False),
                   ("settings", "Settings", False)]
        gap = 6 * s
        p.setFont(_font(11 * s, QFont.DemiBold))
        fm = QFontMetricsF(p.font())
        natural = [16 * s + (5 * s + fm.horizontalAdvance(lbl) if lbl else 0) + 16 * s for _a, lbl, _ in buttons]
        extra = max(0.0, (rect.width() - gap * (len(buttons) - 1) - sum(natural)) / len(buttons))
        x = rect.left()
        for act, label, active in buttons:
            bw = natural.pop(0) + extra
            b = QRectF(x, rect.top(), bw, rect.height())
            x += bw + gap
            p.setPen(Qt.NoPen)
            p.setBrush(self._accent(60) if active else QColor(255, 255, 255, 22))
            p.drawRoundedRect(b, b.height() / 2, b.height() / 2)
            tw = fm.horizontalAdvance(label)
            icon_w = 16 * s
            total = icon_w + (5 * s + tw if label else 0)
            ix = b.center().x() - total / 2 + icon_w / 2
            iy = b.center().y()
            col = self._accent() if active else self._text_color(230)
            if act == "winter":
                art.snowflake(p, ix, iy, 7 * s, col, 1.4 * s)
            elif act == "plow":
                art.tractor(p, ix - 1 * s, iy + 6 * s, 15 * s, 1, 0, True, self.settings["tractor_color"],
                            shadow=False)
            elif act == "timer":
                art.timer_icon(p, ix, iy, 7 * s, "#fbbf24" if active else col)
            elif act == "spotify":
                art.spotify_icon(p, ix, iy, 7.5 * s)
            elif act == "settings":
                art.gear(p, QRectF(ix - 8 * s, iy - 8 * s, 16 * s, 16 * s), col)
                p.setFont(_font(11 * s, QFont.DemiBold))
            p.setPen(self._text_color(235))
            p.drawText(QPointF(ix + icon_w / 2 + 5 * s, iy + fm.ascent() / 2 - 1.5 * s), label)
            self.hits.append((b, act))

    # ------------------------------------------------------------ input
    def enterEvent(self, e):
        self.collapse_timer.stop()
        self.hovered = True
        self.frame.setInterval(16)

    def leaveEvent(self, e):
        self.collapse_timer.start()

    def mousePressEvent(self, e):
        pos = e.position()
        if e.button() == Qt.LeftButton:
            for rect, act in self.hits:
                if rect.contains(pos):
                    self.do(act)
                    return
            if not self.pill.contains(pos):
                return
            # start a possible drag (a click without moving just opens the island)
            s = self._s()
            c = self.pill_screen_rect().center()
            cy = (self.y() + 4 + 18 * s) if self.valign == "top" else (self.y() + self.height() - 4 - 18 * s)
            self.drag = {"start": e.globalPosition(), "cx": c.x(), "cy": cy}
        elif e.button() == Qt.RightButton:
            for rect, act in self.hits:
                if act == "timer" and rect.contains(pos) and self.timer_end:
                    self.timer_end = None
                    return
            self.context_menu(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if not self.drag or not (e.buttons() & Qt.LeftButton):
            return
        d = e.globalPosition() - self.drag["start"]
        if not self.dragging:
            if self.settings["island_locked"] or abs(d.x()) + abs(d.y()) < 6:
                return
            self.dragging = True
        geo = QApplication.primaryScreen().geometry()
        cx = min(max(self.drag["cx"] + d.x(), geo.left() + 20), geo.right() - 20)
        cy = min(max(self.drag["cy"] + d.y(), geo.top() + 10), geo.bottom() - 10)
        self.settings.set("island_x", int(cx))
        self.settings.set("island_y", int(cy))
        self.settings.set("island_position", "custom")

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.drag:
            return
        if self.dragging:
            # snap back to the classic spot when dropped near the top center
            geo = QApplication.primaryScreen().geometry()
            cx, cy = float(self.settings["island_x"]), float(self.settings["island_y"])
            if abs(cx - geo.center().x()) < 40 and cy - geo.top() < 70:
                self.settings.set("island_offset_x", 0)
                self.settings.set("island_position", "top-center")
        else:
            self.hovered = True
        self.drag = None
        self.dragging = False

    def wheelEvent(self, e):
        if not self.settings["scroll_volume"]:
            return
        d = e.angleDelta().y()
        if d:
            winapi.press_key(winapi.VK_VOLUME_UP if d > 0 else winapi.VK_VOLUME_DOWN, 1)

    def do(self, act):
        if act in ("toggle", "next", "prev"):
            self.media.command(act)
        elif act in ("open_spotify", "spotify"):
            self.app.open_spotify()
        elif act == "winter":
            self.app.toggle_winter()
        elif act == "plow":
            self.app.plow()
        elif act == "timer":
            step = int(self.settings["timer_step_min"]) * 60
            if self.timer_end:
                self.timer_end += step
            else:
                self.timer_end = time.time() + step
        elif act == "settings":
            self.app.open_settings()

    def reset_position(self):
        self.settings.set("island_offset_x", 0)
        self.settings.set("island_offset_y", 8)
        self.settings.set("island_position", "top-center")

    def context_menu(self, pos):
        m = QMenu()
        m.setStyleSheet(MENU_STYLE)
        a = m.addAction("Winter mode")
        a.setCheckable(True)
        a.setChecked(bool(self.settings["winter_enabled"]))
        a.triggered.connect(self.app.toggle_winter)
        m.addAction("Send the snow truck", self.app.plow)
        m.addAction("Melt all snowmen", self.app.melt_snowmen)
        m.addSeparator()
        if self.timer_end:
            m.addAction("Cancel timer", lambda: setattr(self, "timer_end", None))
        m.addAction("Settings…", self.app.open_settings)
        lock = m.addAction("Lock position")
        lock.setCheckable(True)
        lock.setChecked(bool(self.settings["island_locked"]))
        lock.triggered.connect(lambda v: self.settings.set("island_locked", bool(v)))
        m.addAction("Move back to top center", self.reset_position)
        m.addAction("Hide island", self.app.toggle_island)
        m.addSeparator()
        m.addAction("Report a bug…", self.app.report_bug)
        m.addAction("Suggest a feature…", self.app.suggest_feature)
        m.addSeparator()
        m.addAction("Quit", self.app.quit)
        m.exec(pos)
