import tkinter as tk
import threading
import queue

from config import load_config
from voice import speak
from brightness import adjust_brightness
from animation import WaterPopup


class HydrationApp:
    def __init__(self):
        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.withdraw()  # no visible main window, just used for the event loop

        self.task_queue = queue.Queue()
        self.stop_event = threading.Event()

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

    def _reminder_loop(self):
        interval = self.cfg["interval_hours"] * 3600
        while not self.stop_event.is_set():
            self.task_queue.put("show_popup")
            self.stop_event.wait(interval)

    def _brightness_loop(self):
        check_seconds = self.cfg.get("brightness_check_minutes", 15) * 60
        while not self.stop_event.is_set():
            adjust_brightness(self.cfg)
            self.stop_event.wait(check_seconds)

    def _poll_queue(self):
        try:
            while True:
                task = self.task_queue.get_nowait()
                if task == "show_popup":
                    self._show_popup()
        except queue.Empty:
            pass
        if not self.stop_event.is_set():
            self.root.after(500, self._poll_queue)

    def _show_popup(self):
        WaterPopup(self.root, duration_sec=self.cfg["popup_duration_sec"])
        if self.cfg.get("voice_enabled", True):
            speak("Time to drink some water.", rate=self.cfg.get("voice_rate", 170))

    def run(self):
        self.root.mainloop()

    def shutdown(self):
        self.stop_event.set()
        self.root.quit()
