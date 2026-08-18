"""System tray icon: right-click to test a reminder or quit cleanly."""
import threading


def _make_icon_image():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((16, 8, 48, 56), fill=(58, 160, 255, 255))
    return img


def start_tray(app):
    import pystray

    def on_quit(icon, item):
        icon.stop()
        app.shutdown()

    def on_test(icon, item):
        app.task_queue.put("show_popup")

    menu = pystray.Menu(
        pystray.MenuItem("Drink reminder now (test)", on_test),
        pystray.MenuItem("Quit Hydration Reminder", on_quit),
    )
    icon = pystray.Icon("hydration_reminder", _make_icon_image(), "Hydration Reminder", menu)
    threading.Thread(target=icon.run, daemon=True).start()
    return icon
