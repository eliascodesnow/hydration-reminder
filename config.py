"""Config loading/saving for Hydration Reminder."""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULTS = {
    # --- reminders ---------------------------------------------------------
    "interval_hours": 2,          # how often to remind you
    "remind_on_start": True,      # show a reminder as soon as the app starts
    "popup_duration_sec": 20,     # how long the popup stays before auto-closing
    "snooze_minutes": 10,         # what the Snooze button does
    "missed_retry_minutes": 15,   # if you ignore a popup, remind again after this long...
    "max_retries": 2,             # ...up to this many times, then back to the normal interval
    "quiet_hours": True,          # don't pop up during the night
    "quiet_start": "23:00",
    "quiet_end": "07:00",
    "daily_goal": 8,              # glasses per day (drives the progress drops and streaks)
    "user_name": "",              # optional: used in some spoken reminders

    # --- look & feel ---------------------------------------------------------
    "theme": "auto",              # auto | sunrise | day | golden | dusk | night
    "popup_position": "bottom-right",   # bottom-right | bottom-left | top-right | top-left | center
    "animation_fps": 30,
    "low_power_mode": False,      # True = render the 3D scene at lower quality (faster)

    # --- sound -----------------------------------------------------------------
    "sound_enabled": True,        # pouring-water sound effect
    "sound_volume": 0.6,          # 0.0 - 1.0
    "voice_enabled": True,        # speak the reminder aloud
    "voice_rate": 170,            # words per minute for TTS
    "voice_random": True,         # use a different installed voice for each reminder
    "voice_name": "",             # optional: pin one voice (part of its name, e.g. "Zira"); overrides voice_random

    # --- brightness (unchanged) --------------------------------------------------
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
