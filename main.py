"""Hydration Reminder - entry point.

Run with:
    python main.py          (shows console output/logs)
    pythonw main.py         (runs silently, no console window)
"""
import sys

# Crisp rendering on high-DPI Windows screens (must happen before tkinter starts).
if sys.platform.startswith("win"):
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

from app import HydrationApp

if __name__ == "__main__":
    app = HydrationApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()
