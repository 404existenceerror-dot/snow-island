"""Hand-drawn vector art: snowflakes, the snowplow tractor, and small UI icons."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPolygonF, QRadialGradient)


def snowflake(p: QPainter, cx, cy, r, color, width=1.6):
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    for k in range(6):
        a = k * math.pi / 3 - math.pi / 2
        dx, dy = math.cos(a), math.sin(a)
        p.drawLine(QPointF(cx, cy), QPointF(cx + dx * r, cy + dy * r))
        bx, by = cx + dx * r * 0.55, cy + dy * r * 0.55
        for s in (-1, 1):
            b = a + s * math.pi / 4
            p.drawLine(QPointF(bx, by), QPointF(bx + math.cos(b) * r * 0.32, by + math.sin(b) * r * 0.32))


def _wheel(p, cx, cy, r, angle, u):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1b1b1f"))
    p.drawEllipse(QPointF(cx, cy), r, r)
    # tread blocks
    p.setBrush(QColor("#2d2d33"))
    for k in range(10):
        a = angle + k * math.pi / 5
        p.drawEllipse(QPointF(cx + math.cos(a) * r * 0.88, cy + math.sin(a) * r * 0.88), r * 0.13, r * 0.13)
    p.setBrush(QColor("#f3c623"))
    p.drawEllipse(QPointF(cx, cy), r * 0.56, r * 0.56)
    p.setBrush(QColor("#c99a00"))
    p.drawEllipse(QPointF(cx, cy), r * 0.22, r * 0.22)
    pen = QPen(QColor("#9a7600"), max(1.0, u * 0.35))
    p.setPen(pen)
    for k in range(4):
        a = angle + k * math.pi / 2
        p.drawLine(QPointF(cx + math.cos(a) * r * 0.22, cy + math.sin(a) * r * 0.22),
                   QPointF(cx + math.cos(a) * r * 0.5, cy + math.sin(a) * r * 0.5))
    p.setPen(Qt.NoPen)


def tractor(p: QPainter, x, ground_y, size, direction=1, wheel_angle=0.0, beacon_on=True,
            body_color="#e8452c", mound=0.0, bob=0.0, shadow=True, vacuum=False):
    """Draws a snowplow tractor. (x, ground_y) is the point under the middle of the tractor."""
    u = size / 16.0
    body = QColor(body_color)
    dark = body.darker(140)
    light = body.lighter(125)
    p.save()
    p.translate(x, ground_y)
    if direction < 0:
        p.scale(-1, 1)
    if shadow:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(QRectF(-10 * u, -0.9 * u, 23 * u, 1.8 * u))
    p.translate(0, bob)

    # plow arms
    pen = QPen(QColor("#55565c"), 1.1 * u)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(6.0 * u, -4.2 * u), QPointF(9.3 * u, -3.6 * u))
    p.drawLine(QPointF(6.0 * u, -6.4 * u), QPointF(9.3 * u, -5.8 * u))
    p.setPen(Qt.NoPen)

    # chassis
    p.setBrush(QColor("#2f3036"))
    p.drawRoundedRect(QRectF(-8.6 * u, -5.6 * u, 15.6 * u, 2.2 * u), 0.6 * u, 0.6 * u)

    # cab
    p.setBrush(dark)
    p.drawRoundedRect(QRectF(-8.2 * u, -15.0 * u, 6.9 * u, 10.0 * u), 0.8 * u, 0.8 * u)
    win = QLinearGradient(0, -14 * u, 0, -9 * u)
    win.setColorAt(0, QColor("#d8f3ff"))
    win.setColorAt(1, QColor("#7cc6ea"))
    p.setBrush(win)
    p.drawRoundedRect(QRectF(-7.3 * u, -14.1 * u, 5.1 * u, 4.7 * u), 0.5 * u, 0.5 * u)
    p.setBrush(QColor(255, 255, 255, 110))
    # an explicit QPolygonF: passing a plain list here hits a PySide6 refcount bug (crash on Linux)
    p.drawPolygon(QPolygonF([QPointF(-6.9 * u, -13.7 * u), QPointF(-5.4 * u, -13.7 * u),
                             QPointF(-6.9 * u, -11.0 * u)]))
    p.setBrush(QColor("#2f3036"))
    p.drawRoundedRect(QRectF(-8.9 * u, -16.1 * u, 8.3 * u, 1.4 * u), 0.5 * u, 0.5 * u)

    # snow on the roof
    p.setBrush(QColor("#ffffff"))
    roof = QPainterPath()
    roof.moveTo(-8.9 * u, -16.0 * u)
    roof.cubicTo(-8.4 * u, -17.4 * u, -2.0 * u, -17.6 * u, -0.6 * u, -16.0 * u)
    roof.closeSubpath()
    p.drawPath(roof)

    # snow-vacuum pipe with a funnel on top (opening at local (1.0u, -22u))
    if vacuum:
        p.setBrush(QColor("#5b5e66"))
        p.drawRoundedRect(QRectF(0.3 * u, -19.6 * u, 1.5 * u, 11.2 * u), 0.6 * u, 0.6 * u)
        p.setBrush(QColor("#45484f"))
        for k in range(4):
            p.drawRect(QRectF(0.2 * u, (-17.6 + k * 2.3) * u, 1.7 * u, 0.5 * u))
        funnel = QPainterPath()
        funnel.moveTo(0.2 * u, -19.4 * u)
        funnel.lineTo(-1.2 * u, -22.0 * u)
        funnel.lineTo(3.2 * u, -22.0 * u)
        funnel.lineTo(1.9 * u, -19.4 * u)
        funnel.closeSubpath()
        p.setBrush(QColor("#f3c623"))
        p.drawPath(funnel)
        p.setBrush(QColor("#2a2a2e"))
        p.drawEllipse(QRectF(-1.2 * u, -22.6 * u, 4.4 * u, 1.2 * u))

    # hood
    hood = QLinearGradient(0, -8.6 * u, 0, -3.6 * u)
    hood.setColorAt(0, light)
    hood.setColorAt(1, body)
    p.setBrush(hood)
    p.drawRoundedRect(QRectF(-2.0 * u, -8.8 * u, 9.2 * u, 5.4 * u), 1.2 * u, 1.2 * u)
    p.setBrush(QColor(0, 0, 0, 60))
    for k in range(3):
        p.drawRoundedRect(QRectF((1.2 + k * 1.5) * u, -6.9 * u, 0.6 * u, 2.4 * u), 0.3 * u, 0.3 * u)
    # headlight
    p.setBrush(QColor("#fff7c2"))
    p.drawEllipse(QPointF(6.7 * u, -7.4 * u), 0.7 * u, 0.7 * u)

    # exhaust pipe
    p.setBrush(QColor("#3a3b40"))
    p.drawRect(QRectF(4.1 * u, -12.4 * u, 0.9 * u, 4.0 * u))
    p.drawRect(QRectF(3.9 * u, -12.8 * u, 1.3 * u, 0.6 * u))

    # wheels
    _wheel(p, -5.0 * u, -4.6 * u, 4.6 * u, wheel_angle, u)
    _wheel(p, 4.6 * u, -2.9 * u, 2.9 * u, wheel_angle * 4.6 / 2.9, u)

    # blade
    blade = QPainterPath()
    blade.moveTo(9.0 * u, 0.3 * u)
    blade.lineTo(9.0 * u, -9.4 * u)
    blade.quadTo(13.4 * u, -6.6 * u, 12.4 * u, 0.3 * u)
    blade.closeSubpath()
    g = QLinearGradient(9 * u, 0, 13 * u, 0)
    g.setColorAt(0, QColor("#ffcf33"))
    g.setColorAt(1, QColor("#e08a00"))
    p.setBrush(g)
    p.setPen(QPen(QColor("#6b4700"), 0.35 * u))
    p.drawPath(blade)
    p.setPen(QPen(QColor(30, 30, 30, 170), 0.7 * u))
    for k in range(3):
        y = (-7.5 + k * 2.6) * u
        p.drawLine(QPointF(9.4 * u, y + 1.0 * u), QPointF(10.6 * u, y))
    p.setPen(Qt.NoPen)

    # pushed snow mound in front of blade
    if mound > 0.3:
        m = min(mound, 8.0) * u
        p.setBrush(QColor("#ffffff"))
        p.setPen(QPen(QColor(170, 195, 225, 160), 0.3 * u))
        mp = QPainterPath()
        mp.moveTo(11.6 * u, 0.3 * u)
        mp.cubicTo(11.6 * u, -m * 1.25, 12.0 * u + m * 1.6, -m * 0.9, 12.0 * u + m * 1.9, 0.3 * u)
        mp.closeSubpath()
        p.drawPath(mp)
        p.setPen(Qt.NoPen)

    # beacon
    p.setBrush(QColor("#2f3036"))
    p.drawRect(QRectF(-5.3 * u, -16.9 * u, 1.6 * u, 0.9 * u))
    if beacon_on:
        glow = QRadialGradient(QPointF(-4.5 * u, -17.6 * u), 3.5 * u)
        glow.setColorAt(0, QColor(255, 170, 0, 170))
        glow.setColorAt(1, QColor(255, 170, 0, 0))
        p.setBrush(glow)
        p.drawEllipse(QPointF(-4.5 * u, -17.6 * u), 3.5 * u, 3.5 * u)
        p.setBrush(QColor("#ffb300"))
    else:
        p.setBrush(QColor("#a86a00"))
    p.drawEllipse(QPointF(-4.5 * u, -17.6 * u), 0.9 * u, 0.9 * u)
    p.restore()


def snowman_centers(base, radii):
    out, y = [], base
    for r in radii:
        cy = y - r
        out.append((cy, r))
        y = cy - r * 0.62
    return out


def snowman(p: QPainter, x, base, radii, complete, scarf="#e11d48", outline=True):
    """Draws a snowman made of stacked balls; decorations appear once it is complete."""
    if not radii:
        return
    centers = snowman_centers(base, radii)
    p.save()
    # stick arms (behind the body)
    if complete and len(centers) >= 2:
        cy, r = centers[1]
        pen = QPen(QColor("#6b4423"), max(1.2, r * 0.13))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        for s in (-1, 1):
            sx, sy = x + s * r * 0.8, cy - r * 0.1
            ex, ey = x + s * r * 2.0, cy - r * 0.9
            p.drawLine(QPointF(sx, sy), QPointF(ex, ey))
            mx, my = sx + (ex - sx) * 0.65, sy + (ey - sy) * 0.65
            p.drawLine(QPointF(mx, my), QPointF(mx + s * r * 0.35, my - r * 0.05))
            p.drawLine(QPointF(ex, ey), QPointF(ex + s * r * 0.08, ey - r * 0.35))
    # balls
    for cy, r in centers:
        g = QRadialGradient(QPointF(x - r * 0.35, cy - r * 0.4), r * 1.5)
        g.setColorAt(0, QColor(255, 255, 255))
        g.setColorAt(0.65, QColor(238, 244, 252))
        g.setColorAt(1, QColor(184, 202, 226))
        p.setBrush(g)
        p.setPen(QPen(QColor(150, 175, 208, 200), 1.0) if outline else Qt.NoPen)
        p.drawEllipse(QPointF(x, cy), r, r)
    p.setPen(Qt.NoPen)
    if complete and len(centers) >= 3:
        (bcy, br), (mcy, mr), (hcy, hr) = centers[0], centers[1], centers[2]
        coal = QColor("#1f1f24")
        p.setBrush(coal)
        for k in range(3):
            p.drawEllipse(QPointF(x, mcy - mr * 0.45 + k * mr * 0.42), mr * 0.09, mr * 0.09)
        # scarf
        sc = QColor(scarf)
        p.setBrush(sc)
        neck = hcy + hr * 0.82
        p.drawRoundedRect(QRectF(x - hr * 0.95, neck - hr * 0.2, hr * 1.9, hr * 0.38), hr * 0.18, hr * 0.18)
        tail = QPainterPath()
        tail.moveTo(x + hr * 0.35, neck)
        tail.lineTo(x + hr * 0.75, neck + hr * 0.95)
        tail.lineTo(x + hr * 0.38, neck + hr * 1.0)
        tail.lineTo(x + hr * 0.1, neck)
        tail.closeSubpath()
        p.drawPath(tail)
        p.setBrush(sc.darker(130))
        p.drawRect(QRectF(x - hr * 0.5, neck - hr * 0.2, hr * 0.12, hr * 0.38))
        p.drawRect(QRectF(x + hr * 0.2, neck - hr * 0.2, hr * 0.12, hr * 0.38))
        # face
        p.setBrush(coal)
        for s in (-1, 1):
            p.drawEllipse(QPointF(x + s * hr * 0.33, hcy - hr * 0.2), hr * 0.11, hr * 0.11)
        for k in range(5):
            a = math.pi * (0.25 + k * 0.125)
            p.drawEllipse(QPointF(x + math.cos(a) * hr * 0.45, hcy + math.sin(a) * hr * 0.45 - hr * 0.02),
                          hr * 0.06, hr * 0.06)
        p.setBrush(QColor("#f97316"))
        nose = QPainterPath()
        nose.moveTo(x, hcy - hr * 0.06)
        nose.lineTo(x + hr * 0.95, hcy + hr * 0.08)
        nose.lineTo(x, hcy + hr * 0.16)
        nose.closeSubpath()
        p.drawPath(nose)
        # top hat
        p.setBrush(QColor("#18181b"))
        brim_y = hcy - hr * 0.72
        p.drawRoundedRect(QRectF(x - hr * 0.85, brim_y - hr * 0.1, hr * 1.7, hr * 0.2), hr * 0.08, hr * 0.08)
        p.drawRect(QRectF(x - hr * 0.55, brim_y - hr * 1.0, hr * 1.1, hr * 0.95))
        p.setBrush(sc)
        p.drawRect(QRectF(x - hr * 0.55, brim_y - hr * 0.32, hr * 1.1, hr * 0.2))
    p.restore()


# ------------------------------------------------------------------ small UI icons
def play(p, cx, cy, r, color):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    path = QPainterPath()
    path.moveTo(cx - r * 0.45, cy - r * 0.62)
    path.lineTo(cx + r * 0.65, cy)
    path.lineTo(cx - r * 0.45, cy + r * 0.62)
    path.closeSubpath()
    p.drawPath(path)


def pause(p, cx, cy, r, color):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    w, h = r * 0.32, r * 1.2
    p.drawRoundedRect(QRectF(cx - r * 0.45, cy - h / 2, w, h), w * 0.3, w * 0.3)
    p.drawRoundedRect(QRectF(cx + r * 0.13, cy - h / 2, w, h), w * 0.3, w * 0.3)


def skip(p, cx, cy, r, color, forward=True):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    d = 1 if forward else -1
    for off in (-0.5, 0.15):
        path = QPainterPath()
        x0 = cx + d * off * r
        path.moveTo(x0 - d * r * 0.0, cy - r * 0.5)
        path.lineTo(x0 + d * r * 0.62, cy)
        path.lineTo(x0, cy + r * 0.5)
        path.closeSubpath()
        p.drawPath(path)
    bx = cx + d * r * 0.78
    p.drawRect(QRectF(bx - r * 0.07, cy - r * 0.5, r * 0.14, r))


def timer_icon(p, cx, cy, r, color):
    pen = QPen(QColor(color), max(1.2, r * 0.16))
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(cx, cy + r * 0.1), r * 0.82, r * 0.82)
    p.drawLine(QPointF(cx, cy + r * 0.1), QPointF(cx, cy - r * 0.4))
    p.drawLine(QPointF(cx, cy + r * 0.1), QPointF(cx + r * 0.35, cy + r * 0.3))
    p.drawLine(QPointF(cx - r * 0.25, cy - r * 0.95), QPointF(cx + r * 0.25, cy - r * 0.95))


def spotify_icon(p, cx, cy, r):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1DB954"))
    p.drawEllipse(QPointF(cx, cy), r, r)
    pen = QPen(QColor("#000000"), r * 0.17)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    for k, (w, y) in enumerate(((1.15, -0.28), (0.95, 0.05), (0.72, 0.34))):
        rect = QRectF(cx - r * w * 0.62, cy + y * r, r * w * 1.24, r * 0.9)
        p.drawArc(rect, 30 * 16, 120 * 16)


_ICON_FONT = None


def _icon_font():
    """Windows 11 ships 'Segoe Fluent Icons', Windows 10 'Segoe MDL2 Assets' (same glyph codes)."""
    global _ICON_FONT
    if _ICON_FONT is None:
        from PySide6.QtGui import QFontDatabase
        fams = set(QFontDatabase.families())
        _ICON_FONT = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in fams), "")
    return _ICON_FONT


def gear(p, rect: QRectF, color):
    fam = _icon_font()
    if not fam:  # no icon font: draw a simple cog instead
        c = rect.center()
        r = rect.width() * 0.32
        pen = QPen(QColor(color), max(1.2, r * 0.45))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        for k in range(8):
            a = k * math.pi / 4
            p.drawLine(QPointF(c.x() + math.cos(a) * r, c.y() + math.sin(a) * r),
                       QPointF(c.x() + math.cos(a) * r * 1.35, c.y() + math.sin(a) * r * 1.35))
        p.setPen(QPen(QColor(color), max(1.2, r * 0.35)))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, r, r)
        return
    f = QFont(fam)
    f.setPixelSize(int(rect.height() * 0.9))
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(rect, Qt.AlignCenter, "")


def battery(p, rect: QRectF, pct, charging, color):
    p.setPen(QPen(QColor(color), 1.2))
    p.setBrush(Qt.NoBrush)
    body = QRectF(rect.left(), rect.top(), rect.width() - 2.5, rect.height())
    p.drawRoundedRect(body, 2.5, 2.5)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(body.right() + 0.6, rect.center().y() - rect.height() * 0.18, 1.8,
                             rect.height() * 0.36), 0.8, 0.8)
    fill = QColor("#4ade80") if charging else (QColor("#f87171") if pct <= 20 else QColor(color))
    p.setBrush(fill)
    inner = body.adjusted(2, 2, -2, -2)
    inner.setWidth(max(1.0, inner.width() * pct / 100))
    p.drawRoundedRect(inner, 1.2, 1.2)
