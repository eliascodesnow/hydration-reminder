import queue
import random
import threading
import time
import tkinter as tk
from datetime import datetime, time as dtime

from animation import WaterPopup
from brightness import adjust_brightness
from config import load_config
from messages import pick_reminder
from sound import SoundPlayer
from stats import Stats
from voice import speak


def _parse(t):
    return dtime.fromisoformat(t)


class HydrationApp:
    def __init__(self):
        self.cfg = load_config()
        self.stats = Stats(goal=int(self.cfg["daily_goal"]))
        self.sound = SoundPlayer(self.cfg["sound_enabled"], self.cfg["sound_volume"])

        self.root = tk.Tk()
        self.root.withdraw()  # no visible main window, just used for the event loop
        try:
            self.scale = max(1.0, min(2.5, self.root.winfo_fpixels("1i") / 96.0))
        except Exception:
            self.scale = 1.0

        self.task_queue = queue.Queue()
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._popup = None
        self._retries = 0
        interval = self._interval()
        self._next_due = time.monotonic() + (0 if self.cfg.get("remind_on_start", True) else interval)

        threading.Thread(target=self._reminder_loop, daemon=True).start()
        threading.Thread(target=self._brightness_loop, daemon=True).start()

        self._poll_queue()

        # tray icon is optional; if pystray/Pillow aren't installed, app still works,
        # you'd just close it via Task Manager or Ctrl+C in the console instead.
        try:
            from tray_icon import start_tray
            start_tray(self)
        except Exception as e:
            print(f"[tray] Tray icon unavailable ({e}). Run from console and Ctrl+C to quit.")

    # ------------------------------------------------------------ scheduling
    def _interval(self):
        return float(self.cfg["interval_hours"]) * 3600

    def _set_next(self, seconds):
        with self._lock:
            self._next_due = time.monotonic() + seconds

    def _in_quiet_hours(self):
        if not self.cfg.get("quiet_hours", True):
            return False
        now = datetime.now().time()
        start, end = _parse(self.cfg["quiet_start"]), _parse(self.cfg["quiet_end"])
        if start <= end:
            return start <= now < end
        return now >= start or now < end  # window crosses midnight

    def _reminder_loop(self):
        while not self.stop_event.wait(1.0):
            with self._lock:
                due = time.monotonic() >= self._next_due
            if not due:
                continue
            if self._in_quiet_hours():
                self._set_next(300)       # re-check in 5 minutes
                continue
            self._set_next(self._interval())   # provisional; the popup outcome adjusts it
            self.task_queue.put(("show_popup", False))

    def _brightness_loop(self):
        check_seconds = self.cfg.get("brightness_check_minutes", 15) * 60
        while not self.stop_event.is_set():
            adjust_brightness(self.cfg)
            self.stop_event.wait(check_seconds)

    # ------------------------------------------------------- main-thread work
    def _poll_queue(self):
        try:
            while True:
                task = self.task_queue.get_nowait()
                name = task[0]
                if name == "show_popup":
                    self._show_popup()
                elif name == "log_glass":
                    self.log_glass()
                elif name == "quit":
                    self.shutdown()
                    return
        except queue.Empty:
            pass
        if not self.stop_event.is_set():
            self.root.after(300, self._poll_queue)

    def _show_popup(self):
        if self._popup is not None:
            return
        progress = self.stats.progress()
        rem = pick_reminder(progress, self.stats.recent_ids, name=self.cfg.get("user_name", ""))
        self.stats.remember(rem.id)
        try:
            self._popup = WaterPopup(
                self.root, self.cfg, rem, progress, scale=self.scale,
                on_pour_start=self.sound.play_pour,
                on_pour_end=lambda: self._speak(rem),
                on_drink=self._on_drink,
                on_result=self._on_result,
            )
        except Exception as e:
            print(f"[popup] Could not show popup: {e}")
            self._popup = None

    def _speak(self, rem):
        if self.cfg.get("voice_enabled", True):
            rate = int(self.cfg.get("voice_rate", 170)) + random.randint(-8, 8)
            speak(rem.speech, rate=rate, voice_name=self.cfg.get("voice_name", ""))

    def _on_drink(self):
        progress = self.stats.add_glass()
        self.sound.play_chime()
        return progress

    def _on_result(self, result):
        self._popup = None
        if result == "drank":
            self._retries = 0
            self._set_next(self._interval())
        elif result == "snooze":
            self._set_next(float(self.cfg.get("snooze_minutes", 10)) * 60)
        elif result == "timeout" and self._retries < int(self.cfg.get("max_retries", 2)):
            self._retries += 1
            self._set_next(float(self.cfg.get("missed_retry_minutes", 15)) * 60)
        else:
            self._retries = 0
            self._set_next(self._interval())

    # ------------------------------------------------- thread-safe tray hooks
    def request_popup(self):
        self.task_queue.put(("show_popup", True))

    def request_log_glass(self):
        self.task_queue.put(("log_glass",))

    def request_quit(self):
        self.task_queue.put(("quit",))

    def log_glass(self):
        self.stats.add_glass()
        self._retries = 0
        self._set_next(self._interval())

    def run(self):
        self.root.mainloop()

    def shutdown(self):
        self.stop_event.set()
        self.root.quit()
