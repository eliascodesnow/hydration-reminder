"""Checks the time of day and adjusts screen brightness accordingly.

Windows does not expose ambient-light-sensor readings to normal desktop
apps, so this uses a time-of-day schedule instead (similar to Night Light /
f.lux-style tools). It only touches brightness if screen_brightness_control
can control your display (built-in laptop panels almost always work;
external monitors need DDC/CI support, which varies).
"""
from datetime import datetime, time as dtime


def _parse(t):
    return dtime.fromisoformat(t)


def target_brightness(cfg):
    now = datetime.now().time()
    day_start = _parse(cfg["day_start"])
    evening_start = _parse(cfg["evening_start"])
    night_start = _parse(cfg["night_start"])

    if day_start <= now < evening_start:
        return cfg["brightness_day"]
    elif evening_start <= now < night_start:
        return cfg["brightness_evening"]
    else:
        return cfg["brightness_night"]


def adjust_brightness(cfg, log=print):
    if not cfg.get("brightness_auto", True):
        return
    try:
        import screen_brightness_control as sbc
        target = target_brightness(cfg)
        current_list = sbc.get_brightness()
        current = current_list[0] if current_list else None
        if current is None:
            return
        # avoid constant tiny adjustments / fighting manual changes
        if abs(current - target) >= 3:
            sbc.set_brightness(target)
            log(f"[brightness] Adjusted {current}% -> {target}%")
    except Exception as e:
        log(f"[brightness] Could not adjust brightness on this display: {e}")
