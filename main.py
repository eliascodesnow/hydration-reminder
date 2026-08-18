"""Hydration Reminder - entry point.

Run with:
    python main.py          (shows console output/logs)
    pythonw main.py         (runs silently, no console window)
"""
from app import HydrationApp

if __name__ == "__main__":
    app = HydrationApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()
