"""System tray icon: progress, test reminder, log a glass, quit."""
import math
import threading


def _make_icon_image():
    from PIL import Image, ImageDraw
    s = 4
    img = Image.new("RGBA", (64 * s, 64 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(60):
        t = 2 * math.pi * i / 60
        pts.append((32 * s + math.sin(t) * (math.sin(t / 2) ** 1.15) * 24 * s, 34 * s - math.cos(t) * 26 * s))
    d.polygon(pts, fill=(58, 170, 255, 255))
    d.ellipse((22 * s, 30 * s, 29 * s, 41 * s), fill=(255, 255, 255, 120))
    return img.resize((64, 64))


def start_tray(app):
    import pystray

    def on_quit(icon, item):
        icon.stop()
        app.request_quit()

    def progress_text(item):
        p = app.stats.progress()
        return f"Today: {p['glasses']} / {p['goal']} glasses"

    menu = pystray.Menu(
        pystray.MenuItem(progress_text, None, enabled=False),
        pystray.MenuItem("Drink reminder now (test)", lambda i, it: app.request_popup()),
        pystray.MenuItem("Log a glass", lambda i, it: app.request_log_glass()),
        pystray.MenuItem("Quit Hydration Reminder", on_quit),
    )
    icon = pystray.Icon("hydration_reminder", _make_icon_image(), "Hydration Reminder", menu)
    threading.Thread(target=icon.run, daemon=True).start()
    return icon
