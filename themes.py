"""Colour themes. The popup's mood follows the time of day."""
from datetime import datetime

# top / bottom = background gradient, accent = highlights, glow = light behind the glass
THEMES = {
    "sunrise": {"top": (96, 58, 116), "bottom": (18, 28, 58), "accent": (255, 190, 130), "glow": (255, 170, 120)},
    "day":     {"top": (16, 96, 150), "bottom": (7, 30, 64),  "accent": (120, 220, 255), "glow": (110, 210, 255)},
    "golden":  {"top": (126, 66, 92), "bottom": (22, 26, 58), "accent": (255, 176, 130), "glow": (255, 150, 110)},
    "dusk":    {"top": (62, 42, 124), "bottom": (13, 15, 46), "accent": (190, 160, 255), "glow": (160, 130, 255)},
    "night":   {"top": (16, 28, 72),  "bottom": (5, 9, 28),   "accent": (130, 178, 255), "glow": (100, 150, 255)},
}


def theme_name_for(now=None):
    h = (now or datetime.now()).hour
    if 5 <= h < 10:
        return "sunrise"
    if 10 <= h < 16:
        return "day"
    if 16 <= h < 19:
        return "golden"
    if 19 <= h < 22:
        return "dusk"
    return "night"


def get_theme(name="auto", now=None):
    if name == "auto" or name not in THEMES:
        name = theme_name_for(now)
    return dict(THEMES[name], name=name)
