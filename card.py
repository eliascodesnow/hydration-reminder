"""Composes one popup frame: gradient card + 3D scene + text + progress drops + buttons.

Pure Pillow/numpy (no tkinter), so it can be previewed and tested headlessly.
All layout numbers below are for a 420x600 card at scale 1.0; `scale` adapts it
for high-DPI screens.
"""
import math
import os
from datetime import datetime

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

from messages import done_message
from scene3d import Scene

W0, H0, SCENE_H0 = 420, 600, 330
PAD0 = 26
RADIUS0 = 26
KEY = (1, 2, 3)  # colour that becomes transparent outside the rounded corners (Windows)

_FONT_FILES = {
    False: ["segoeui.ttf", "SegoeUI.ttf", "Inter-Regular.ttf", "DejaVuSans.ttf", "arial.ttf"],
    True: ["segoeuib.ttf", "seguisb.ttf", "Inter-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
}


def _font(size, bold=False):
    for name in _FONT_FILES[bold]:
        try:
            return ImageFont.truetype(name, int(size))
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=int(size))
    except Exception:
        return ImageFont.load_default()


def _wrap(text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if font.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _lighten(c, k):
    return tuple(int(v + (255 - v) * k) for v in c)


def _drop_points(cx, cy, size, n=44):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = math.sin(t) * (math.sin(t / 2) ** 1.15)
        y = math.cos(t)
        pts.append((cx + x * size * 0.82, cy - y * size))
    return pts


def ease_out(u):
    u = max(0.0, min(1.0, u))
    return 1 - (1 - u) ** 3


class CardRenderer:
    def __init__(self, theme, reminder, progress, duration_sec, scale=1.0, seed=None, quality=2):
        self.k = scale
        self.W, self.H = int(round(W0 * scale)), int(round(H0 * scale))
        self.scene_h = int(round(SCENE_H0 * scale))
        self.pad = int(round(PAD0 * scale))
        self.theme = theme
        self.reminder = reminder
        self.progress = dict(progress)
        self.duration = duration_sec
        self.state = "ask"           # "ask" -> "done"
        self.t_done = None
        self.hover = None            # None | "drink" | "snooze" | "close"
        self.t_text = 0.55           # when the text starts to fade in

        self.base = self._make_base()
        self.scene = Scene(self.W, self.scene_h, self.base.crop((0, 0, self.W, self.scene_h)),
                           theme, ss=quality, seed=seed)

        self.mask = self._rounded_mask()
        self.key_img = Image.new("RGB", (self.W, self.H), KEY)

        self._layout_buttons()
        self._build_ask_layers()

    # -------------------------------------------------------------- helpers
    def u(self, v):
        return int(round(v * self.k))

    def _make_base(self):
        W, H = self.W, self.H
        top = np.array(self.theme["top"], float)
        bot = np.array(self.theme["bottom"], float)
        y = np.linspace(0, 1, H)[:, None, None] ** 0.8
        arr = (top * (1 - y) + bot * y) * np.ones((H, W, 3))
        # soft glow behind the glass
        gx, gy = W * 0.63, self.scene_h * 0.55
        xx, yy = np.meshgrid(np.arange(W), np.arange(H))
        dist = np.sqrt(((xx - gx) / (W * 0.55)) ** 2 + ((yy - gy) / (self.scene_h * 0.65)) ** 2)
        glow = np.clip(1 - dist, 0, 1)[..., None] ** 2
        arr = arr + (np.array(self.theme["glow"], float) - arr) * glow * 0.22
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    def _rounded_mask(self):
        s = 4
        m = Image.new("L", (self.W * s, self.H * s), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, self.W * s - 1, self.H * s - 1], radius=self.u(RADIUS0) * s, fill=255)
        return m.resize((self.W, self.H), Image.LANCZOS)

    def make_square(self):
        """Use square corners (for platforms without per-pixel window transparency)."""
        self.mask = Image.new("L", (self.W, self.H), 255)

    def _layout_buttons(self):
        W, H, pad, u = self.W, self.H, self.pad, self.u
        y0, y1 = u(504), u(504) + u(46)
        gap = u(12)
        snooze_w = u(124)
        self.btn_drink = (pad, y0, W - pad - snooze_w - gap, y1)
        self.btn_snooze = (W - pad - snooze_w, y0, W - pad, y1)
        self.btn_close = (W - u(54), u(8), W - u(8), u(54))

    # --------------------------------------------------------- static layers
    def _new_layer(self):
        s = 2
        img = Image.new("RGBA", (self.W * s, self.H * s), (0, 0, 0, 0))
        return img, ImageDraw.Draw(img), s

    def _finish_layer(self, img):
        return img.resize((self.W, self.H), Image.LANCZOS)

    def _spaced(self, d, xy, text, font, fill, spacing):
        x, y = xy
        for ch in text:
            d.text((x, y), ch, font=font, fill=fill)
            x += font.getlength(ch) + spacing

    def _text_layer(self, category, headline, body, now=None):
        img, d, s = self._new_layer()
        pad, u = self.pad * s, self.u
        acc = self.theme["accent"]
        stamp = (now or datetime.now()).strftime("%I:%M %p").lstrip("0")
        self._spaced(d, (pad, u(344) * s), f"{category.upper()}  \u00b7  {stamp}", _font(u(11) * s, True), acc + (255,), u(1.6) * s)

        fh = _font(u(25) * s, True)
        y = u(366) * s
        for line in _wrap(headline, fh, (self.W - 2 * self.pad) * s):
            d.text((pad, y), line, font=fh, fill=(246, 251, 255, 255))
            y += int(u(31) * s)

        fb = _font(u(14.5) * s)
        y += u(4) * s
        for line in _wrap(body, fb, (self.W - 2 * self.pad) * s)[:3]:
            d.text((pad, y), line, font=fb, fill=(184, 211, 232, 255))
            y += int(u(21) * s)
        return self._finish_layer(img)

    def _progress_layer(self):
        img, d, s = self._new_layer()
        p, u = self.progress, self.u
        goal, got = p["goal"], p["glasses"]
        n = min(goal, 12)
        shown = min(got, n)
        size = u(9.5) * s
        step = u(23) * s
        x = self.pad * s + size
        cy = u(466) * s
        acc = self.theme["accent"]
        for i in range(n):
            pts = _drop_points(x + i * step, cy, size)
            if i < shown:
                d.polygon(pts, fill=acc + (255,))
                hl = _drop_points(x + i * step - size * 0.22, cy + size * 0.12, size * 0.34)
                d.polygon(hl, fill=(255, 255, 255, 120))
            else:
                d.polygon(pts, fill=(255, 255, 255, 18), outline=(255, 255, 255, 80))
        label = f"{got} of {goal} today"
        f = _font(u(12.5) * s, True)
        tw = f.getlength(label)
        d.text(((self.W - self.pad) * s - tw, cy - u(9) * s), label, font=f, fill=(206, 228, 244, 255))
        return self._finish_layer(img)

    def _button_layer(self, hover):
        img, d, s = self._new_layer()
        u = self.u
        # primary
        x0, y0, x1, y1 = [v * s for v in self.btn_drink]
        acc = self.theme["accent"]
        c1 = _lighten(acc, 0.10 + (0.18 if hover == "drink" else 0))
        c2 = tuple(int(v * 0.74) for v in c1)
        grad = Image.new("RGBA", (x1 - x0, y1 - y0))
        gd = ImageDraw.Draw(grad)
        for yy in range(y1 - y0):
            t = yy / max(1, y1 - y0 - 1)
            gd.line([(0, yy), (x1 - x0, yy)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)) + (255,))
        m = Image.new("L", grad.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, grad.size[0] - 1, grad.size[1] - 1], radius=(y1 - y0) // 2, fill=255)
        img.paste(grad, (x0, y0), m)
        f = _font(u(15) * s, True)
        label = "I drank some"
        tw = f.getlength(label)
        icon = u(8) * s
        total = tw + icon * 2 + u(10) * s
        cx = (x0 + x1) / 2 - total / 2
        cy = (y0 + y1) / 2
        d.polygon(_drop_points(cx + icon, cy + u(1) * s, icon), fill=(6, 40, 80, 255))
        d.text((cx + icon * 2 + u(10) * s, cy), label, font=f, fill=(6, 40, 80, 255), anchor="lm")

        # secondary
        x0, y0, x1, y1 = [v * s for v in self.btn_snooze]
        fill_a = 46 if hover == "snooze" else 22
        d.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) // 2, fill=(255, 255, 255, fill_a),
                            outline=(255, 255, 255, 90 if hover == "snooze" else 55), width=s)
        f2 = _font(u(14) * s, True)
        d.text(((x0 + x1) / 2, (y0 + y1) / 2), "Snooze", font=f2, fill=(226, 240, 252, 255), anchor="mm")
        return self._finish_layer(img)

    def _done_layer(self):
        """Confirmation pill shown where the buttons were, after logging a glass."""
        img, d, s = self._new_layer()
        u = self.u
        x0, y0 = self.btn_drink[0] * s, self.btn_drink[1] * s
        x1, y1 = self.btn_snooze[2] * s, self.btn_snooze[3] * s
        acc = self.theme["accent"]
        d.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) // 2, fill=acc + (46,), outline=acc + (150,), width=s)
        cx, cy = x0 + u(34) * s, (y0 + y1) / 2
        r = u(11) * s
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=acc + (255,))
        a = u(5) * s
        d.line([(cx - a, cy), (cx - a * 0.25, cy + a * 0.75), (cx + a, cy - a * 0.7)],
               fill=(6, 40, 80, 255), width=int(2.2 * s), joint="curve")
        d.text((cx + r + u(12) * s, cy), "Glass logged. See you next time.", font=_font(u(14.5) * s, True),
               fill=(232, 245, 255, 255), anchor="lm")
        return self._finish_layer(img)

    def _chrome_layer(self, hover):
        img, d, s = self._new_layer()
        x0, y0, x1, y1 = [v * s for v in self.btn_close]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        r = self.u(13) * s
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 40 if hover == "close" else 16))
        a = self.u(5) * s
        col = (255, 255, 255, 235 if hover == "close" else 160)
        d.line([(cx - a, cy - a), (cx + a, cy + a)], fill=col, width=int(1.6 * s))
        d.line([(cx - a, cy + a), (cx + a, cy - a)], fill=col, width=int(1.6 * s))
        return self._finish_layer(img)

    def _build_ask_layers(self):
        r = self.reminder
        self.layer_text = self._text_layer(r.category, r.headline, r.body)
        self.layer_progress = self._progress_layer()
        self.layers_buttons = {h: self._button_layer(h) for h in (None, "drink", "snooze")}
        self.layers_chrome = {h: self._chrome_layer(h) for h in (None, "close")}

    # ---------------------------------------------------------------- events
    def hit_test(self, x, y):
        def inside(r):
            return r[0] <= x <= r[2] and r[1] <= y <= r[3]
        if inside(self.btn_close):
            return "close"
        if self.state == "ask":
            if inside(self.btn_drink):
                return "drink"
            if inside(self.btn_snooze):
                return "snooze"
        return None

    def mark_done(self, t, progress):
        """Called when the user taps 'I drank some': swaps to the celebration state."""
        self.state = "done"
        self.t_done = t
        self.progress = dict(progress)
        head, body = done_message(progress["glasses"], progress["goal"], progress.get("streak", 0))
        self.layer_text = self._text_layer("Logged", head, body)
        self.layer_progress = self._progress_layer()
        self.layer_done = self._done_layer()
        self.t_text = t + 0.05
        self.scene.celebrate(t)

    # ---------------------------------------------------------------- render
    @staticmethod
    def _paste_fade(frame, layer, k, dy=0):
        if k <= 0:
            return
        if k >= 0.999 and dy == 0:
            frame.paste(layer, (0, 0), layer)
            return
        alpha = layer.getchannel("A").point(lambda v: int(v * k))
        frame.paste(layer, (0, int(dy)), alpha)

    def render(self, t, remaining=1.0):
        frame = self.base.copy()
        frame.paste(self.scene.render(t), (0, 0))

        reveal = ease_out((t - self.t_text) / 0.55)
        reveal_p = ease_out((t - self.t_text - 0.25) / 0.5)
        reveal_b = ease_out((t - self.t_text - 0.45) / 0.5)
        self._paste_fade(frame, self.layer_text, reveal, (1 - reveal) * self.u(10))
        self._paste_fade(frame, self.layer_progress, reveal_p, (1 - reveal_p) * self.u(8))
        if self.state == "ask":
            self._paste_fade(frame, self.layers_buttons[self.hover if self.hover in ("drink", "snooze") else None],
                             reveal_b, (1 - reveal_b) * self.u(8))
            # countdown bar
            d = ImageDraw.Draw(frame, "RGBA")
            x0, x1, y = self.pad, self.W - self.pad, self.H - self.u(22)
            h = max(2, self.u(3))
            d.rounded_rectangle([x0, y, x1, y + h], radius=h // 2, fill=(255, 255, 255, 30))
            if remaining > 0.01:
                d.rounded_rectangle([x0, y, x0 + (x1 - x0) * remaining, y + h], radius=h // 2,
                                    fill=self.theme["accent"] + (190,))
        if self.state == "done":
            self._paste_fade(frame, self.layer_done, reveal_b, (1 - reveal_b) * self.u(8))
        self._paste_fade(frame, self.layers_chrome[self.hover if self.hover == "close" else None], 1.0)

        # subtle border and rounded corners
        d = ImageDraw.Draw(frame, "RGBA")
        out = Image.composite(frame, self.key_img, self.mask)
        return out
