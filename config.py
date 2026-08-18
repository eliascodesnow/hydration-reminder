"""Config loading/saving for Hydration Reminder."""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULTS = {
    "interval_hours": 2,          # how often to remind you
    "popup_duration_sec": 20,     # how long the popup stays before auto-closing
    "voice_enabled": True,
    "voice_rate": 170,            # words per minute for TTS
    "brightness_auto": True,      # set False to disable brightness adjustment entirely
    "brightness_day": 100,        # % brightness during the day
    "brightness_evening": 60,     # % brightness in the evening
    "brightness_night": 30,       # % brightness late at night
    "day_start": "07:00",
    "evening_start": "19:00",
    "night_start": "23:00",
    "brightness_check_minutes": 15,
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULTS)
        return dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
        # fill in any missing keys with defaults (e.g. after an update)
        merged = dict(DEFAULTS)
        merged.update(cfg)
        return merged
    except Exception:
        return dict(DEFAULTS)


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
