"""The popup window: a thin tkinter shell around the 3D card renderer (card.py).

Features
* slides up + fades in, fades out on close
* real-time 3D pour animation (see scene3d.py), adaptive quality if the PC is slow
* pour sound and spoken reminder are triggered on the animation timeline
* pauses its auto-close countdown while the mouse is over it
* buttons: "I drank some" (logs a glass + celebration), "Snooze", and a close X
"""
import sys
import time
import tkinter as tk

from PIL import ImageTk

from card import CardRenderer
from themes import get_theme

KEY_HEX = "#010203"   # must match card.KEY = (1, 2, 3)


def work_area(root):
    """Usable screen rectangle (excludes the taskbar on Windows)."""
    try:
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
        if rect.right > rect.left:
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def _ease_out(u):
    u = max(0.0, min(1.0, u))
    return 1 - (1 - u) ** 3


class WaterPopup(tk.Toplevel):
    SLIDE = 34          # px the card slides up while fading in
    INTRO = 0.40        # seconds
    OUTRO = 0.25

    def __init__(self, master, cfg, reminder, progress, scale=1.0,
                 on_pour_start=None, on_pour_end=None, on_drink=None, on_result=None):
        super().__init__(master)
        self.cfg = cfg
        self.on_pour_start, self.on_pour_end = on_pour_start, on_pour_end
        self.on_drink, self.on_result = on_drink, on_result

        self.fps = max(10, min(60, int(cfg.get("animation_fps", 30))))
        self.duration = float(cfg.get("popup_duration_sec", 20))
        self.life = self.duration
        self.result = None
        self.closing_t = None
        self._hovering_window = False
        self._fired_start = self._fired_end = False
        self._ema_ms = 0.0
        self._alive = True

        theme = get_theme(cfg.get("theme", "auto"))
        quality = 1 if cfg.get("low_power_mode", False) else 2
        self.r = CardRenderer(theme, reminder, progress, self.duration, scale=scale, quality=quality)
        self.t_pour_start = self.r.scene.sound_start
        self.t_pour_end = self.r.scene.fill_end + 0.5

        # --- window chrome -------------------------------------------------
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=KEY_HEX)
        self._keyed = False
        try:
            self.attributes("-transparentcolor", KEY_HEX)
            self._keyed = True
        except tk.TclError:
            self.r.make_square()   # no per-pixel transparency on this OS: square corners
        try:
            self.attributes("-alpha", 0.0)
        except tk.TclError:
            pass

        W, H = self.r.W, self.r.H
        self.canvas = tk.Canvas(self, width=W, height=H, bg=KEY_HEX, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.img_item = self.canvas.create_image(0, 0, anchor="nw")

        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Enter>", lambda e: self._set_window_hover(True))
        self.canvas.bind("<Leave>", lambda e: self._set_window_hover(False))
        self.canvas.bind("<Button-1>", self._on_click)

        self._place(W, H)
        self.t0 = time.monotonic()
        self._last = self.t0
        self._tick()

    # ---------------------------------------------------------------- layout
    def _place(self, W, H):
        left, top, right, bottom = work_area(self)
        margin = int(24 * self.r.k)
        pos = str(self.cfg.get("popup_position", "bottom-right")).lower()
        x = right - W - margin
        y = bottom - H - margin
        if "left" in pos:
            x = left + margin
        if "top" in pos:
            y = top + margin
        if pos == "center":
            x, y = (left + right - W) // 2, (top + bottom - H) // 2
        self._x, self._y = x, y
        self.geometry(f"{W}x{H}+{x}+{y + self.SLIDE}")

    # ---------------------------------------------------------------- events
    def _set_window_hover(self, inside):
        self._hovering_window = inside
        if not inside:
            self.r.hover = None
            self.canvas.configure(cursor="arrow")

    def _on_motion(self, e):
        h = self.r.hit_test(e.x, e.y)
        if h != self.r.hover:
            self.r.hover = h
            self.canvas.configure(cursor="hand2" if h else "arrow")

    def _on_click(self, e):
        if self.closing_t is not None:
            return
        h = self.r.hit_test(e.x, e.y)
        if h == "drink":
            self._drink()
        elif h == "snooze":
            self.close("snooze")
        elif h == "close":
            self.close("dismissed")

    def _drink(self):
        progress = self.on_drink() if self.on_drink else dict(self.r.progress, glasses=self.r.progress["glasses"] + 1)
        t = time.monotonic() - self.t0
        self.r.mark_done(t, progress)
        self.result = "drank"
        self.life = 2.0            # linger briefly to enjoy the celebration
        self.duration = 2.0

    # ----------------------------------------------------------------- loop
    def _tick(self):
        if not self._alive:
            return
        t_start = time.monotonic()
        t = t_start - self.t0
        dt = min(0.1, t_start - self._last)
        self._last = t_start

        try:
            # timeline hooks: sound when the water starts landing, voice when the glass is full
            if not self._fired_start and t >= self.t_pour_start:
                self._fired_start = True
                if self.on_pour_start:
                    self.on_pour_start()
            if not self._fired_end and t >= self.t_pour_end:
                self._fired_end = True
                if self.on_pour_end and self.r.state == "ask" and self.closing_t is None:
                    self.on_pour_end()

            # auto-close countdown (paused while the mouse is over the card)
            if self.closing_t is None:
                if not (self._hovering_window and self.r.state == "ask"):
                    self.life -= dt
                if self.life <= 0:
                    self.close(self.result or "timeout")

            remaining = max(0.0, self.life / self.duration) if self.r.state == "ask" else 0.0
            frame = self.r.render(t, remaining)
            self._photo = ImageTk.PhotoImage(frame)
            self.canvas.itemconfigure(self.img_item, image=self._photo)

            # slide + fade in / fade out
            a = _ease_out(t / self.INTRO)
            y = self._y + int(self.SLIDE * (1 - a))
            if self.closing_t is not None:
                k = (time.monotonic() - self.closing_t) / self.OUTRO
                a *= max(0.0, 1.0 - k)
                y = self._y + int(self.SLIDE * 0.5 * min(1.0, k))
                if k >= 1.0:
                    self._finish()
                    return
            if a < 1.0 or self.closing_t is not None:
                self.geometry(f"+{self._x}+{y}")
            try:
                self.attributes("-alpha", max(0.0, min(1.0, a)) * 0.99)
            except tk.TclError:
                pass
        except Exception as e:  # never let an animation bug take the app down
            print(f"[popup] render error: {e}")
            self._finish()
            return

        # adaptive quality: drop supersampling if this machine can't keep up
        ms = (time.monotonic() - t_start) * 1000
        self._ema_ms = ms if self._ema_ms == 0 else self._ema_ms * 0.9 + ms * 0.1
        if self.r.scene.ss > 1 and t > 1.0 and self._ema_ms > 1000.0 / self.fps * 1.15:
            self.r.scene.set_quality(1)
        delay = max(1, int(1000 / self.fps - ms))
        self.after(delay, self._tick)

    # ---------------------------------------------------------------- close
    def close(self, result="dismissed"):
        if self.closing_t is not None:
            return
        self.result = self.result or result
        self.closing_t = time.monotonic()

    def _finish(self):
        if not self._alive:
            return
        self._alive = False
        try:
            self.destroy()
        finally:
            if self.on_result:
                self.on_result(self.result or "dismissed")
