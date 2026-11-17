"""Winter mode: a transparent, click-through overlay with falling snow that piles up on
desktop icons and the taskbar, snowballs and snowmen you make with the mouse, and a
snow-vacuum truck that drives along the taskbar and sucks the snow off your icons."""
import collections
import math
import random
import time

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QCursor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient, QRegion)
from PySide6.QtWidgets import QApplication, QWidget

import art
import osapi as winapi

GRAVITY = 1700.0
BUCKET = 64
SETTLE = 0.22  # wait this long after the desktop appears (window animations) before showing snow


def _approach(a, target, dt):
    rate = 7.0 if target > a else 20.0  # fade in gently, fade out fast
    a += (target - a) * min(1.0, dt * rate)
    return target if abs(target - a) < 0.01 else a
MAX_SNOWMEN = 8
SNOWMAN_MIN_BASE = 13.0


# ====================================================================== snow piles
class Pile:
    """A height map of snow sitting on a flat surface from x0 to x1 at height `base`."""

    def __init__(self, x0, x1, base, maxh, bin_w=3.0, edge_slope=0.8):
        self.x0, self.x1, self.base = x0, x1, base
        self.n = max(3, int((x1 - x0) / bin_w))
        self.bw = (x1 - x0) / self.n
        self.h = [0.0] * self.n
        self.visible = True
        self.vis_since = -10.0
        self.alpha = 1.0
        self.edge_slope = edge_slope
        self.set_max(maxh)

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2

    def set_max(self, maxh):
        self.maxh = maxh
        self.cap = []
        for i in range(self.n):
            d = min(i + 0.5, self.n - i - 0.5) * self.bw
            self.cap.append(min(maxh, 1.0 + d * self.edge_slope))
        self.h = [min(a, c) for a, c in zip(self.h, self.cap)]

    def index(self, x):
        return min(self.n - 1, max(0, int((x - self.x0) / self.bw)))

    def surface(self, x):
        return self.base - self.h[self.index(x)]

    def total(self):
        return sum(self.h)

    def clear(self):
        self.h = [0.0] * self.n

    def add(self, x, amt, spread=2):
        i = self.index(x)
        best = None
        for j in (i, i - 1, i + 1, i - 2, i + 2, i - 3, i + 3):
            if 0 <= j < self.n and self.h[j] < self.cap[j] - 0.05:
                best = j
                break
        if best is None:
            return False
        for k in range(best - spread, best + spread + 1):
            if 0 <= k < self.n:
                w = 1.0 - abs(k - best) / (spread + 1)
                self.h[k] = min(self.cap[k], self.h[k] + amt * w)
        return True

    def deposit(self, x, radius, amt):
        self.add(x, amt, max(1, int(radius / self.bw)))

    def take(self, x_lo, x_hi, amount):
        got = 0.0
        for i in range(self.index(x_lo), self.index(x_hi) + 1):
            t = min(self.h[i], amount)
            self.h[i] -= t
            got += t
        return got

    def clear_between(self, a, b):
        lo, hi = (a, b) if a < b else (b, a)
        if hi < self.x0 or lo > self.x1:
            return 0.0
        got = 0.0
        for i in range(self.index(lo), self.index(hi) + 1):
            c = self.x0 + (i + 0.5) * self.bw
            if lo <= c <= hi and self.h[i] > 0:
                got += self.h[i]
                self.h[i] = 0.0
        return got

    def relax(self):
        h, cap = self.h, self.cap
        for i in range(self.n - 1):
            d = h[i] - h[i + 1]
            if d > 1.6 or d < -1.6:
                m = d * 0.25
                h[i] -= m
                h[i + 1] = min(cap[i + 1], h[i + 1] + m)

    def path(self):
        pts = [QPointF(self.x0, self.base - self.h[0] * 0.5)]
        for i in range(self.n):
            pts.append(QPointF(self.x0 + (i + 0.5) * self.bw, self.base - self.h[i]))
        pts.append(QPointF(self.x1, self.base - self.h[-1] * 0.5))
        path = QPainterPath(QPointF(self.x0, self.base))
        path.lineTo(pts[0])
        for i in range(1, len(pts) - 1):
            path.quadTo(pts[i], (pts[i] + pts[i + 1]) / 2)
        path.lineTo(pts[-1])
        path.lineTo(QPointF(self.x1, self.base))
        path.closeSubpath()
        return path


# ====================================================================== moving things
class Flake:
    __slots__ = ("x", "y", "r", "vy", "sway", "phase", "freq", "img")


class Ball:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.r = 5.0
        self.holding = True
        self.rot = 0.0
        self.hist = collections.deque()
        self.dead = False
        self.rolling = False  # being rolled along the taskbar snow


class Snowman:
    def __init__(self, x, base, r):
        self.x, self.base = x, base
        self.radii = [r]
        self.complete = False

    def top(self):
        return art.snowman_centers(self.base, self.radii)[-1]

    def height(self):
        cy, r = self.top()
        return self.base - (cy - r)


class Tractor:
    def __init__(self, x, y, target_x, size, speed, color):
        self.x, self.y = x, y
        self.target_x = target_x
        self.dir = 1 if target_x > x else -1
        self.size = size
        self.u = size / 16.0
        self.speed = speed
        self.color = color
        self.wheel = 0.0
        self.load = 0.0
        self.t = 0.0
        self.puff_t = 0.0

    def nozzle(self):
        return self.x + self.dir * 1.0 * self.u, self.y - 22.0 * self.u


# ====================================================================== overlay window
class WinterOverlay(QWidget):
    def __init__(self, settings, icons, own_hwnds):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setWindowTitle("Snow Island – Winter")
        self.settings = settings
        self.icons = icons
        self.own_hwnds = own_hwnds  # callable -> set of our window handles

        self.flakes = []
        self.piles = {}
        self.buckets = {}
        self.ground = None
        self.balls = []
        self.snowmen = []
        self.pending_press = None  # time a hold on the taskbar snow started
        self.particles = []  # [x, y, vx, vy, life, maxlife, r]
        self.puffs = []  # [x, y, r, life]
        self.suck = []  # [x, y, vx, vy, age]
        self.beams = []  # (x0, x1, y) of piles being vacuumed this frame
        self.tractor = None
        self.enabled = False
        self.desktop_visible = True
        self.ground_vis = []
        self.ground_since = []
        self.ground_alpha = []
        self.flake_region = None
        self.was_down = False
        self.last_cursor = None
        self.t = 0.0
        self.last = time.perf_counter()
        self.last_plow = time.time()
        self.frame_no = 0
        self.blank = False
        self.on_event = None  # callable(kind) for the island to show messages

        self._place()
        self._make_sprites()

        self.timer = QTimer(self, timeout=self.tick)
        self.icon_timer = QTimer(self, interval=1500, timeout=self.refresh_icons)
        self.fg_timer = QTimer(self, interval=100, timeout=self.check_visibility)
        self.region_tick = 0
        settings.changed.connect(self.on_settings)

    def _event(self, kind):
        if self.on_event:
            self.on_event(kind)

    # ------------------------------------------------------------ setup
    def _place(self):
        scr = QApplication.primaryScreen()
        self.setGeometry(scr.geometry())
        self.dpr = scr.devicePixelRatio()
        avail = scr.availableGeometry()
        self.ground_y = avail.bottom() + 1 - scr.geometry().top()
        self._make_ground()

    def _make_ground(self):
        old = self.ground
        mh = float(self.settings["max_pile"]) * 1.3
        self.ground = Pile(0, self.width(), self.ground_y, mh, bin_w=4.0, edge_slope=2.0)
        if old and old.n == self.ground.n:
            self.ground.h = [min(a, c) for a, c in zip(old.h, self.ground.cap)]

    def _make_sprites(self):
        self.sprites = []
        size = float(self.settings["snow_size"])
        for k in range(10):
            r = (1.0 + k * 0.32) * size
            alpha = 150 + k * 10
            d = int(math.ceil(r * 2 + 2))
            pm = QPixmap(int(d * self.dpr), int(d * self.dpr))
            pm.setDevicePixelRatio(self.dpr)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            g = QRadialGradient(QPointF(d / 2, d / 2), r + 0.8)
            g.setColorAt(0.0, QColor(255, 255, 255, alpha))
            g.setColorAt(0.55, QColor(255, 255, 255, int(alpha * 0.85)))
            g.setColorAt(1.0, QColor(235, 245, 255, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(QPointF(d / 2, d / 2), r + 0.8, r + 0.8)
            p.end()
            self.sprites.append((r, pm, d / 2))
        for k in range(3):
            r = (5.0 + k * 1.5) * size
            d = int(math.ceil(r * 2 + 4))
            pm = QPixmap(int(d * self.dpr), int(d * self.dpr))
            pm.setDevicePixelRatio(self.dpr)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            art.snowflake(p, d / 2, d / 2, r, QColor(255, 255, 255, 215), max(1.0, r * 0.18))
            p.end()
            self.sprites.append((r * 0.5, pm, d / 2))

    def _new_flake(self, top=False):
        f = Flake()
        if random.random() < 0.06:
            idx = 10 + random.randrange(3)
        else:
            idx = min(9, int(random.random() ** 1.6 * 10))
        r, pm, half = self.sprites[idx]
        f.img = (pm, half)
        f.r = r
        f.x = random.uniform(-150, self.width() + 150)
        f.y = random.uniform(-self.height(), 0) if top else random.uniform(-40, -8)
        f.vy = (28 + 16 * r) * float(self.settings["snow_speed"]) * random.uniform(0.85, 1.15)
        f.sway = random.uniform(8, 28)
        f.phase = random.uniform(0, math.tau)
        f.freq = random.uniform(0.6, 1.6)
        return f

    def _fill_flakes(self, initial=False):
        target = int(self.settings["snow_amount"])
        while len(self.flakes) < target:
            self.flakes.append(self._new_flake(top=initial))
        del self.flakes[target:]

    def on_settings(self, key):
        if key == "fps" and self.timer.isActive():
            self.timer.setInterval(int(1000 / max(10, int(self.settings["fps"]))))
        elif key == "snow_amount":
            self._fill_flakes(initial=True)
        elif key in ("snow_size", "snow_speed"):
            self._make_sprites()
            self.flakes = []
            self._fill_flakes(initial=True)
        elif key == "max_pile":
            for p in self.piles.values():
                p.set_max(float(self.settings["max_pile"]))
            self._make_ground()
        elif key == "icon_piles" and not self.settings["icon_piles"]:
            for p in self.piles.values():
                p.clear()

    # ------------------------------------------------------------ on / off
    def set_enabled(self, on):
        self.enabled = on
        if on:
            self._place()
            self._fill_flakes(initial=True)
            self.refresh_icons()
        else:
            self.flakes, self.balls, self.snowmen = [], [], []
            for p in self.piles.values():
                p.clear()
            self.ground.clear()
        self._update_running()

    def _update_running(self):
        active = self.enabled or self.tractor is not None
        if active and not self.isVisible():
            self.last = time.perf_counter()
            self.timer.start(int(1000 / max(10, int(self.settings["fps"]))))
            self.icon_timer.start()
            self.fg_timer.start()
            self.show()
            self.check_visibility()
        elif not active and self.isVisible():
            self.timer.stop()
            self.icon_timer.stop()
            self.fg_timer.stop()
            self.hide()
        if self.isVisible():
            winapi.keep_topmost(int(self.winId()))

    # ------------------------------------------------------------ desktop icons
    def refresh_icons(self):
        rects = self.icons.rects()
        dpr = self.dpr
        new = {}
        maxh = float(self.settings["max_pile"])
        W, H = self.width(), self.height()
        for (l, t, r, b) in rects:
            l, t, r, b = l / dpr, t / dpr, r / dpr, b / dpr
            if r < 0 or l > W or b < 0 or t > H:
                continue
            key = (round(l), round(t), round(r), round(b))
            if key in self.piles:
                new[key] = self.piles[key]
                continue
            w, h = r - l, b - t
            icon = min(w, h) * 0.86
            cx = (l + r) / 2
            new[key] = Pile(cx - icon * 0.46, cx + icon * 0.46, t + h * 0.12, maxh)
        # snow from icons that moved or vanished falls off
        for key, pile in self.piles.items():
            if key not in new and pile.total() > 2:
                self._crumble(pile)
        self.piles = new
        self.buckets = {}
        for p in new.values():
            for b in range(int(p.x0) // BUCKET, int(p.x1) // BUCKET + 1):
                self.buckets.setdefault(b, []).append(p)

    def _crumble(self, pile):
        for _ in range(min(40, int(pile.total() / 3))):
            x = random.uniform(pile.x0, pile.x1)
            self._particle(x, pile.base - random.uniform(0, pile.maxh * 0.6),
                           random.uniform(-30, 30), random.uniform(-40, 20), 1.2)

    def _particle(self, x, y, vx, vy, life, r=None):
        self.particles.append([x, y, vx, vy, life, life, r or random.uniform(1.2, 2.8)])

    def _desktop_at(self, x, y, own):
        """True if the desktop (not an app window) is what's visible at logical x, y."""
        root, cls = winapi.root_at(x * self.dpr, y * self.dpr)
        if root in own:
            return None
        return cls in winapi.DESKTOP_CLASSES

    def check_visibility(self):
        own = self.own_hwnds()
        now = self.t
        for p in self.piles.values():
            v = self._desktop_at(p.cx, p.base + 6, own)
            if v is None:
                continue
            if v and not p.visible:
                p.vis_since = now
            p.visible = v
        seg = []
        for x in range(0, self.width(), BUCKET):
            v = self._desktop_at(x + BUCKET / 2, self.ground_y - 4, own)
            seg.append(True if v is None else v)
        if len(seg) != len(self.ground_vis):
            self.ground_since = [-10.0] * len(seg)
            self.ground_alpha = [1.0 if v else 0.0 for v in seg]
        else:
            for k, v in enumerate(seg):
                if v and not self.ground_vis[k]:
                    self.ground_since[k] = now
        self.ground_vis = seg
        self.region_tick += 1
        if not self.settings["snow_over_apps"] and self.region_tick % 3 == 0:
            region = QRegion()
            cell = 72
            for y in range(0, self.height(), cell):
                for x in range(0, self.width(), cell):
                    v = self._desktop_at(x + cell / 2, y + cell / 2, own)
                    if v or v is None:
                        region = region.united(QRect(x, y, cell, cell))
            self.flake_region = region
        elif self.settings["snow_over_apps"]:
            self.flake_region = None
        self.desktop_visible = any(seg) or any(p.visible for p in self.piles.values())

    def ground_visible_at(self, x):
        return self.ground_alpha_at(x) > 0.5

    def ground_alpha_at(self, x):
        if not self.settings["piles_only_on_desktop"] or not self.ground_alpha:
            return 1.0
        k = min(len(self.ground_alpha) - 1, max(0, int(x) // BUCKET))
        return self.ground_alpha[k]

    def _fade(self, dt):
        """Smoothly fade piles in once the desktop has settled, and out fast when covered."""
        hide = bool(self.settings["piles_only_on_desktop"])
        t = self.t
        for p in self.piles.values():
            target = 1.0 if not hide or (p.visible and t - p.vis_since >= SETTLE) else 0.0
            p.alpha = _approach(p.alpha, target, dt)
        for k, vis in enumerate(self.ground_vis):
            target = 1.0 if not hide or (vis and t - self.ground_since[k] >= SETTLE) else 0.0
            self.ground_alpha[k] = _approach(self.ground_alpha[k], target, dt)

    def show_flakes(self):
        if not self.enabled:
            return False
        return self.flake_region is None or not self.flake_region.isEmpty()

    # ------------------------------------------------------------ simulation
    def tick(self):
        now = time.perf_counter()
        dt = min(0.05, now - self.last)
        self.last = now
        self.t += dt
        self.frame_no += 1
        cursor = self.mapFromGlobal(QCursor.pos())
        cx, cy = cursor.x(), cursor.y()

        if self.enabled:
            self._fade(dt)
            self._mouse(dt, cx, cy)
            self._flakes(dt)
            if self.frame_no % 3 == 0:
                for p in self.piles.values():
                    p.relax()
                self.ground.relax()
            if self.frame_no % 30 == 0:
                self._auto_plow()
        self._balls(dt)
        self._particles(dt)
        if self.tractor:
            self._tractor(dt)

        visible = self.enabled or self.balls or self.particles or self.tractor
        if visible:
            self.blank = False
            self.update()
        elif not self.blank:
            self.blank = True
            self.update()

    def _flakes(self, dt):
        wind = float(self.settings["wind"]) * 90
        acc = float(self.settings["accumulation"])
        ground = self.ground if self.settings["ground_snow"] else None
        buckets = self.buckets if self.settings["icon_piles"] else {}
        W, H = self.width(), self.height()
        t = self.t
        sin = math.sin
        for i, f in enumerate(self.flakes):
            oy = f.y
            f.y += f.vy * dt
            f.x += (wind + sin(t * f.freq + f.phase) * f.sway) * dt
            landed = False
            ps = buckets.get(int(f.x) // BUCKET)
            if ps:
                for p in ps:
                    if p.x0 <= f.x < p.x1:
                        sy = p.base - p.h[p.index(f.x)]
                        if oy <= sy <= f.y + f.r:
                            if p.add(f.x, f.r * 0.45 * acc):
                                landed = True
                            break
            if not landed and ground is not None and f.y >= ground.base - ground.h[ground.index(f.x)]:
                if 0 <= f.x < W:
                    ground.add(f.x, f.r * 0.3 * acc, 3)
                landed = True
            if landed or f.y > H + 10 or f.x < -200 or f.x > W + 200:
                self.flakes[i] = self._new_flake()

    def _auto_plow(self):
        mins = float(self.settings["auto_plow_min"])
        if mins <= 0 or self.tractor is not None:
            return
        if time.time() - self.last_plow < mins * 60:
            return
        snow = sum(p.total() for p in self.piles.values()) + self.ground.total() * 0.2
        if snow > 60:
            self.start_tractor()

    def _in_ground_zone(self, x, y):
        """The snowy strip along the top of the taskbar, plus the taskbar itself."""
        if not self.settings["ground_snow"]:
            return False
        return y >= self.ground.surface(x) - 28

    def _press_kind(self, cx, cy):
        """What a mouse press at (cx, cy) should do: 'ground', 'air' or None."""
        mode = self.settings["snowball_mode"]
        if mode == "off":
            return None
        root, cls = winapi.root_class_under_cursor()
        if root in self.own_hwnds():
            return None
        if self._in_ground_zone(cx, cy):
            if cy >= self.ground_y or cls in winapi.DESKTOP_CLASSES or mode == "everywhere":
                return "ground"
            return None
        if mode == "desktop" and cls not in winapi.DESKTOP_CLASSES:
            return None
        return "air"

    def _mouse(self, dt, cx, cy):
        down, pressed = winapi.left_button_state()
        if down and not self.was_down:
            kind = self._press_kind(cx, cy)
            if kind == "air":
                self.balls.append(Ball(cx, cy))
            elif kind == "ground":
                # wait a moment so normal taskbar clicks don't make snowballs
                self.pending_press = self.t
        elif not down and not self.was_down and pressed:
            if self._press_kind(cx, cy) == "air":  # very quick click between two frames
                b = Ball(cx, cy)
                b.r = 6.5
                self._release(b)
                self.balls.append(b)
        if down and self.pending_press is not None and self.t - self.pending_press >= 0.18:
            self.pending_press = None
            b = Ball(cx, self.ground_y)
            b.r = 7.0
            b.rolling = True
            self.balls.append(b)
        if not down:
            self.pending_press = None
        if not down and self.was_down:
            for b in self.balls:
                if b.holding:
                    if b.rolling:
                        self._drop_rolled(b)
                    else:
                        self._release(b)
        self.was_down = down

        # brush snow off icons by flicking the mouse over them
        if self.last_cursor and dt > 0 and not down and self.settings["mouse_brush"]:
            lx, ly = self.last_cursor
            vx, vy = (cx - lx) / dt, (cy - ly) / dt
            if math.hypot(vx, vy) > 450:
                for p in self._piles_near(cx, 16):
                    if (p.visible and p.x0 - 8 <= cx <= p.x1 + 8
                            and p.base - p.maxh - 14 <= cy <= p.base + 45):
                        got = p.take(cx - 16, cx + 16, 1e9)
                        for _ in range(min(18, int(got / 4) + (1 if got > 0.5 else 0))):
                            self._particle(random.uniform(cx - 14, cx + 14),
                                           p.base - random.uniform(0, p.maxh * 0.7),
                                           vx * 0.35 + random.uniform(-60, 60),
                                           random.uniform(-220, -40) + vy * 0.2, random.uniform(0.6, 1.0))
        self.last_cursor = (cx, cy)

        for b in self.balls:
            if not b.holding:
                continue
            # lift the ball off the ground by moving the mouse up; put it back down to keep rolling
            on_ground = cy >= self.ground_y - 40
            if b.rolling and not on_ground:
                b.rolling = False
            elif not b.rolling and on_ground and self._in_ground_zone(cx, cy):
                b.rolling = True
            if b.rolling:
                self._roll(b, dt, cx)
                continue
            b.x, b.y = cx, cy
            b.hist.append((self.t, cx, cy))
            while b.hist and self.t - b.hist[0][0] > 0.1:
                b.hist.popleft()
            rmax = 30 * float(self.settings["snow_size"])
            b.r = min(rmax, b.r + dt * 10)
            reach = b.r + 60
            for i, f in enumerate(self.flakes):
                dx, dy = b.x - f.x, b.y - f.y
                if -reach < dx < reach and -reach < dy < reach:
                    d = math.hypot(dx, dy)
                    if d < b.r:
                        b.r = min(rmax, b.r + 0.12)
                        self.flakes[i] = self._new_flake()
                    elif d < reach:
                        f.x += dx * dt * 5
                        f.y += dy * dt * 5
            for p in list(self._piles_near(b.x, b.r)) + [self.ground]:
                if abs(p.surface(b.x) - b.y) < b.r + 10:
                    got = p.take(b.x - b.r, b.x + b.r, dt * 25)
                    b.r = min(rmax, b.r + got * 0.02)
            b.rot += dt * 2

    def _roll(self, b, dt, cx):
        """Roll a snowball along the taskbar snow; it grows as it picks snow up."""
        g = self.ground
        rmax = 36.0
        cx = min(self.width() - b.r, max(b.r, cx))
        dx = cx - b.x
        b.x = cx
        if dx:
            got = g.take(b.x - b.r * 0.6, b.x + b.r * 0.6, abs(dx) * 0.12)
            b.r = min(rmax, b.r + got * 0.03 + (abs(dx) * 0.012 if got > 0 else 0))
            b.rot += dx / max(3.0, b.r)
            if got > 0 and random.random() < 0.5:
                self._particle(b.x - math.copysign(b.r, dx), self.ground_y - 2,
                               -math.copysign(random.uniform(20, 80), dx), random.uniform(-90, -20), 0.4)
        sink = min(b.r * 0.3, g.h[g.index(b.x)])
        b.y = self.ground_y - b.r + sink
        b.hist.clear()
        b.hist.append((self.t, b.x, b.y))

    def _drop_rolled(self, b):
        """Let go of a rolled ball: a big one becomes a snowman's body, a small one falls apart."""
        b.holding = False
        b.rolling = False
        if b.r >= SNOWMAN_MIN_BASE and self._room_for_snowman(b.x, b.r):
            self._new_snowman(b)
        else:
            b.dead = True
            self.ground.deposit(b.x, b.r, b.r * 0.35)
            self._puff(b.x, self.ground_y - 2, b.r, 6)

    def _piles_near(self, x, r):
        seen = set()
        for k in range(int(x - r) // BUCKET, int(x + r) // BUCKET + 1):
            for p in self.buckets.get(k, ()):
                if id(p) not in seen:
                    seen.add(id(p))
                    yield p

    def _release(self, b):
        b.holding = False
        # let go above an unfinished snowman -> drop straight onto it
        for sm in self.snowmen:
            if sm.complete:
                continue
            cy, r = sm.top()
            if abs(b.x - sm.x) < r + b.r + 25 and b.y < cy:
                b.x, b.vx, b.vy = sm.x, 0.0, 0.0
                return
        vx = vy = 0.0
        if len(b.hist) >= 2:
            t0, x0, y0 = b.hist[0]
            t1, x1, y1 = b.hist[-1]
            if t1 - t0 > 0.01:
                vx, vy = (x1 - x0) / (t1 - t0), (y1 - y0) / (t1 - t0)
        sp = math.hypot(vx, vy)
        if sp > 2600:
            vx, vy = vx * 2600 / sp, vy * 2600 / sp
        b.vx, b.vy = vx, vy

    def _balls(self, dt):
        W = self.width()
        for b in self.balls:
            if b.holding:
                continue
            oy = b.y
            b.vy += GRAVITY * dt
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.rot += b.vx * dt / max(3, b.r)
            if b.x < b.r:
                b.x, b.vx = b.r, abs(b.vx) * 0.55
            elif b.x > W - b.r:
                b.x, b.vx = W - b.r, -abs(b.vx) * 0.55
            if b.y < b.r and b.vy < 0:
                b.y, b.vy = b.r, -b.vy * 0.4
            if b.vy <= 0:
                continue
            # landing on a snowman that isn't finished yet -> stack it
            for sm in self.snowmen:
                if sm.complete:
                    continue
                cy, r = sm.top()
                top = cy - r * 0.55
                if abs(b.x - sm.x) < r * 0.9 + b.r * 0.3 and oy + b.r <= top + 4 and b.y + b.r >= top:
                    self._stack(sm, b)
                    break
            if b.dead:
                continue
            for p in self._piles_near(b.x, 0):
                if p.x0 <= b.x <= p.x1:
                    sy = p.surface(b.x)
                    if oy + b.r <= sy + 2 <= b.y + b.r + 2:
                        self._splat(b, p, sy)
                        break
            if not b.dead:
                sy = self.ground.surface(b.x)
                if b.y + b.r >= sy:
                    if b.r >= SNOWMAN_MIN_BASE and self._room_for_snowman(b.x, b.r):
                        self._new_snowman(b)
                    else:
                        self._splat(b, self.ground if self.settings["ground_snow"] else None, sy)
        self.balls = [b for b in self.balls if not b.dead]

    def _room_for_snowman(self, x, r):
        return all(abs(x - s.x) > s.radii[0] + r * 0.8 for s in self.snowmen)

    def _new_snowman(self, b):
        b.dead = True
        if len(self.snowmen) >= MAX_SNOWMEN:
            self._melt(self.snowmen.pop(0))
        x = min(self.width() - b.r, max(b.r, b.x))
        self.snowmen.append(Snowman(x, self.ground_y, min(b.r, 34.0)))
        self._puff(x, self.ground_y - 2, b.r, 10)

    def _stack(self, sm, b):
        b.dead = True
        below = sm.radii[-1]
        r = max(below * 0.5, min(b.r, below * 0.82))
        sm.radii.append(r)
        cy, _ = sm.top()
        self._puff(sm.x, cy + r * 0.6, r, 8)
        if len(sm.radii) >= 3:
            sm.complete = True
            self._event("snowman")

    def _puff(self, x, y, r, n):
        for _ in range(n):
            a = random.uniform(math.pi * 1.05, math.pi * 1.95)
            sp = random.uniform(40, 140)
            self._particle(x + random.uniform(-r, r) * 0.7, y, math.cos(a) * sp, math.sin(a) * sp,
                           random.uniform(0.4, 0.8))

    def _melt(self, sm):
        for cy, r in art.snowman_centers(sm.base, sm.radii):
            for _ in range(int(r)):
                a = random.uniform(0, math.tau)
                d = random.uniform(0, r)
                self._particle(sm.x + math.cos(a) * d, cy + math.sin(a) * d, random.uniform(-60, 60),
                               random.uniform(-150, 0), random.uniform(0.5, 1.1))

    def melt_snowmen(self):
        for sm in self.snowmen:
            self._melt(sm)
        self.snowmen = []

    def _splat(self, b, pile, sy):
        b.dead = True
        n = int(8 + b.r * 1.4)
        for _ in range(n):
            a = random.uniform(math.pi * 1.05, math.pi * 1.95)
            sp = random.uniform(60, 220) * (0.6 + b.r / 25)
            self._particle(b.x + random.uniform(-b.r, b.r) * 0.6, sy - 2,
                           math.cos(a) * sp + b.vx * 0.15, math.sin(a) * sp, random.uniform(0.5, 1.0))
        if pile is not None:
            pile.deposit(b.x, b.r * 1.3, b.r * 0.45)

    def _particles(self, dt):
        out = []
        g = GRAVITY * 0.6 * dt
        for p in self.particles:
            p[3] += g
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] -= dt
            if p[4] > 0:
                out.append(p)
        self.particles = out[-900:]

        puffs = []
        drift = self.tractor.dir * 10 * dt if self.tractor else 0
        for q in self.puffs:
            q[1] -= 26 * dt
            q[0] -= drift
            q[2] += 9 * dt
            q[3] -= dt
            if q[3] > 0:
                puffs.append(q)
        self.puffs = puffs

        if not self.tractor:
            self.suck = []
            return
        tx, ty = self.tractor.nozzle()
        keep = []
        damp = max(0.0, 1 - 5 * dt)
        for q in self.suck:
            q[4] += dt
            dx, dy = tx - q[0], ty - q[1]
            d = math.hypot(dx, dy) or 1.0
            q[2] = (q[2] + dx / d * 3200 * dt) * damp
            q[3] = (q[3] + dy / d * 3200 * dt) * damp
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            if d > 9 and q[4] < 2.0:
                keep.append(q)
        self.suck = keep[-700:]

    # ------------------------------------------------------------ snow-vacuum truck
    def start_tractor(self):
        if self.tractor is not None:
            return False
        if not self.isVisible():
            self._place()
        W = self.width()
        size = 54.0
        u = size / 16
        speed = 380 * float(self.settings["tractor_speed"])
        self.tractor = Tractor(-24 * u, self.ground_y, W + 30 * u, size, speed, self.settings["tractor_color"])
        self.last_plow = time.time()
        self._update_running()
        return True

    def _tractor(self, dt):
        tr = self.tractor
        tr.t += dt
        u = tr.u
        d = tr.dir
        blade = 12.2 * u
        old_b = tr.x + d * blade
        mv = min(tr.speed * dt, abs(tr.target_x - tr.x))
        tr.x += d * mv
        tr.wheel += d * mv / (4.6 * u)
        new_b = tr.x + d * blade

        # plow the taskbar snow with the blade
        got = self.ground.clear_between(old_b, new_b)
        if got > 0:
            tr.load += got
            if self.ground_visible_at(new_b):
                for _ in range(min(10, int(got / 6) + 1)):
                    self._particle(new_b + d * random.uniform(0, 6 * u), tr.y - random.uniform(1, 8) * u,
                                   d * random.uniform(60, 260), random.uniform(-320, -80),
                                   random.uniform(0.6, 1.1), random.uniform(1.3, 3.0))
        tr.load *= (1 - dt * 0.8)

        # vacuum the snow off every desktop icon the truck passes under
        nx, ny = tr.nozzle()
        hide_covered = bool(self.settings["piles_only_on_desktop"])
        self.beams = []
        for p in self.piles.values():
            if abs(p.cx - nx) < 75 and p.total() > 0.2:
                taken = p.take(p.x0, p.x1, 95 * dt)
                if p.visible or not hide_covered:
                    self.beams.append((p.x0, p.x1, p.base))
                    for _ in range(min(10, int(taken / 2) + 1)):
                        top = max(p.h) if p.h else 0
                        self.suck.append([random.uniform(p.x0, p.x1), p.base - random.uniform(0, top + 2),
                                          random.uniform(-80, 80), random.uniform(-160, -20), 0.0])
        # the blade knocks over any snowman it reaches and plows it away
        lo, hi = min(old_b, new_b), max(old_b, new_b)
        keep = []
        for sm in self.snowmen:
            if lo - sm.radii[0] <= sm.x <= hi + sm.radii[0]:
                for cy, r in art.snowman_centers(sm.base, sm.radii):
                    for _ in range(int(r * 1.2)):
                        a = random.uniform(0, math.tau)
                        dd = random.uniform(0, r)
                        self._particle(sm.x + math.cos(a) * dd, cy + math.sin(a) * dd,
                                       d * random.uniform(80, 320), random.uniform(-300, -40),
                                       random.uniform(0.6, 1.2), random.uniform(1.5, 3.2))
                tr.load += sum(sm.radii) * 2
            else:
                keep.append(sm)
        self.snowmen = keep
        tr.puff_t += dt
        if tr.puff_t > 0.12:
            tr.puff_t = 0
            self.puffs.append([tr.x - d * 4.6 * u, tr.y - 9.5 * u, 2.0, 0.9])

        if abs(tr.target_x - tr.x) < 0.5:
            self.tractor = None
            self.beams = []
            self._update_running()

    # ------------------------------------------------------------ painting
    def _draw_pile(self, p, pile, maxh, edge, alpha=None):
        if pile.total() < 0.5:
            return
        a = pile.alpha if alpha is None else alpha
        if a < 0.02:
            return
        g = QLinearGradient(0, pile.base - maxh, 0, pile.base)
        g.setColorAt(0, QColor(255, 255, 255, 250))
        g.setColorAt(1, QColor(214, 228, 245, 245))
        p.setOpacity(a)
        p.setBrush(g)
        p.setPen(edge)
        p.drawPath(pile.path())
        p.setOpacity(1.0)

    def _draw_ground(self, p, maxh, edge):
        g = self.ground
        if g.total() < 0.5:
            return
        alphas = self.ground_alpha if self.settings["piles_only_on_desktop"] and self.ground_alpha else None
        if alphas is None:
            self._draw_pile(p, g, maxh, edge, 1.0)
            return
        path = g.path()
        k, n = 0, len(alphas)
        while k < n:  # group neighbouring segments with the same opacity into one draw
            a = alphas[k]
            j = k
            while j + 1 < n and abs(alphas[j + 1] - a) < 0.02:
                j += 1
            if a >= 0.02:
                p.setClipRect(QRectF(k * BUCKET, 0, (j - k + 1) * BUCKET, self.height()))
                grad = QLinearGradient(0, g.base - maxh, 0, g.base)
                grad.setColorAt(0, QColor(255, 255, 255, 250))
                grad.setColorAt(1, QColor(214, 228, 245, 245))
                p.setOpacity(a)
                p.setBrush(grad)
                p.setPen(edge)
                p.drawPath(path)
            k = j + 1
        p.setClipping(False)
        p.setOpacity(1.0)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        if self.blank:
            p.end()
            return
        p.setRenderHint(QPainter.Antialiasing)
        maxh = float(self.settings["max_pile"])
        edge = QPen(QColor(150, 180, 215, 150), 1.0)

        if self.enabled:
            if self.settings["icon_piles"]:
                for pile in self.piles.values():
                    self._draw_pile(p, pile, maxh, edge)
            scarf = self.settings["scarf_color"]
            for sm in self.snowmen:
                a = self.ground_alpha_at(sm.x)
                if a >= 0.02:
                    p.setOpacity(a)
                    art.snowman(p, sm.x, sm.base, sm.radii, sm.complete, scarf)
                    p.setOpacity(1.0)
            if self.settings["ground_snow"]:
                self._draw_ground(p, maxh * 1.3, edge)

        if self.show_flakes():
            if self.flake_region is not None:
                p.setClipRegion(self.flake_region)
            for f in self.flakes:
                pm, half = f.img
                p.drawPixmap(QPointF(f.x - half, f.y - half), pm)
            p.setClipping(False)

        p.setPen(Qt.NoPen)
        for q in self.puffs:
            a = max(0, min(1, q[3] / 0.9))
            p.setBrush(QColor(120, 120, 128, int(110 * a)))
            p.drawEllipse(QPointF(q[0], q[1]), q[2], q[2])

        if self.tractor:
            tr = self.tractor
            nx, ny = tr.nozzle()
            for x0, x1, y in self.beams:
                cone = QPainterPath(QPointF(nx - 4, ny))
                cone.lineTo(QPointF(x0, y))
                cone.lineTo(QPointF(x1, y))
                cone.lineTo(QPointF(nx + 4, ny))
                cone.closeSubpath()
                g = QLinearGradient(0, ny, 0, y)
                g.setColorAt(0, QColor(180, 225, 255, 70))
                g.setColorAt(1, QColor(180, 225, 255, 18))
                p.setBrush(g)
                p.drawPath(cone)
            p.setBrush(QColor(255, 255, 255, 235))
            for q in self.suck:
                p.drawEllipse(QPointF(q[0], q[1]), 2.0, 2.0)
            art.tractor(p, tr.x, tr.y, tr.size, tr.dir, tr.wheel, int(tr.t * 4) % 2 == 0, tr.color,
                        mound=math.sqrt(max(0.0, tr.load)) * 0.55, bob=math.sin(tr.t * 22) * 0.35 * tr.u,
                        vacuum=True)

        for b in self.balls:
            g = QRadialGradient(QPointF(b.x - b.r * 0.35, b.y - b.r * 0.4), b.r * 1.4)
            g.setColorAt(0, QColor(255, 255, 255))
            g.setColorAt(0.6, QColor(236, 243, 252))
            g.setColorAt(1, QColor(176, 196, 222))
            p.setBrush(g)
            p.setPen(QPen(QColor(160, 182, 210, 200), 1))
            p.drawEllipse(QPointF(b.x, b.y), b.r, b.r)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(190, 208, 232, 170))
            for k in range(3):
                a = b.rot + k * 2.1
                p.drawEllipse(QPointF(b.x + math.cos(a) * b.r * 0.5, b.y + math.sin(a) * b.r * 0.5),
                              b.r * 0.12, b.r * 0.12)

        p.setPen(Qt.NoPen)
        for q in self.particles:
            a = max(0.0, min(1.0, q[4] / q[5]))
            p.setBrush(QColor(255, 255, 255, int(235 * a)))
            p.drawEllipse(QPointF(q[0], q[1]), q[6], q[6])
        p.end()
