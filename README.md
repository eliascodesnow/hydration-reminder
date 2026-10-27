# Hydration Reminder

A lightweight background app for Windows that nudges you to drink water, and makes it
a little moment worth looking at.

## What's new in v2

- **Real 3D pour animation** - a perspective camera gently orbits a tapered glass while a
  3D bottle tilts in and pours along a true gravity arc. The water is a rippling surface
  mesh with splashes, rising bubbles, glass reflections, condensation drops and a glowing floor.
  Rendered in software (Pillow + numpy), so no GPU or extra 3D library is needed.
- **Pouring-water sound effect** - synthesised procedurally: stream hiss, a "glug" resonance that
  rises in pitch as the glass fills, bubbles, a splash and a soft sparkle at the end.
- **Never the same reminder twice** - 35+ messages across fun facts, dev humour, posture/eye
  breaks, mini challenges, and time-of-day specific lines, plus dynamic ones that react to your
  progress ("Glass number 4", "Just one more!", "5-day streak"). The last 12 are never repeated,
  and the spoken line varies too.
- **Daily goal, progress drops and streaks** - tap *I drank some* to log a glass (with a little celebration).
- **Smarter scheduling** - Snooze button, quiet hours at night, a gentle re-remind if you miss one,
  and the countdown pauses while your mouse is over the popup.
- **Mood follows the time of day** - sunrise, day, golden hour, dusk and night colour themes.

> **Note:** This project is now part of **HealthBuddy**, a comprehensive wellness suite. See [HealthBuddy](https://github.com/eliascodesnow/health-buddy) for the latest development and integration with other health-focused features.

## One thing worth knowing up front

This app is designed to be an ordinary, well-behaved Windows program: it shows up
in Task Manager as `pythonw.exe` and you can close it there, no different from any
other app. I intentionally didn't build in anything that resists being closed —
that kind of anti-kill behavior is a hallmark of malware, and a reminder tool that
fights you to stay open would be a worse experience anyway.

If what you actually want is "I don't want to forget it's off," the included
`register_autostart.ps1` script does that the right way: it registers a Windows
Task Scheduler entry that relaunches the app automatically each time you log in.
You stay in control — view, disable, or delete it anytime in Task Scheduler.

## Setup

1. Install Python 3.9+ from python.org if you don't have it (check "Add to PATH" during install).
2. Open a terminal in this folder and install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run it:
   ```
   python main.py
   ```
   (the pouring sound files are generated automatically into `assets/` on first run)
   This shows a console window with logs (useful the first time, so you can see
   brightness/voice errors if any). Once you're happy, run it silently with:
   ```
   pythonw main.py
   ```
   (no console window; look for it in Task Manager > Details as `pythonw.exe`)

4. **Test it immediately** without waiting 2 hours: right-click the tray icon
   (small blue circle near your clock) and choose "Drink reminder now (test)".

## Auto-start at login (optional)

Open PowerShell **as Administrator**, `cd` into this folder, then run:
```
.\register_autostart.ps1
```
To remove it later:
```
Unregister-ScheduledTask -TaskName "HydrationReminder" -Confirm:$false
```

## Configuration

A `config.json` file is created next to `main.py` on first run. Edit it and
restart the app to change settings:

| Key | Meaning | Default |
|---|---|---|
| `interval_hours` | Hours between reminders | `2` |
| `remind_on_start` | Show a reminder as soon as the app starts | `true` |
| `popup_duration_sec` | Seconds before the popup auto-closes | `20` |
| `snooze_minutes` | What the Snooze button does | `10` |
| `missed_retry_minutes` / `max_retries` | Re-remind after an ignored popup, up to N times | `15` / `2` |
| `quiet_hours`, `quiet_start`, `quiet_end` | No popups during these hours | `true`, `23:00`, `07:00` |
| `daily_goal` | Glasses per day | `8` |
| `user_name` | Optional, used in some spoken reminders | `""` |
| `theme` | `auto`, `sunrise`, `day`, `golden`, `dusk`, `night` | `auto` |
| `popup_position` | `bottom-right`, `bottom-left`, `top-right`, `top-left`, `center` | `bottom-right` |
| `animation_fps` | Animation frame rate | `30` |
| `low_power_mode` | Lower 3D render quality on slow PCs (it also adapts automatically) | `false` |
| `sound_enabled` / `sound_volume` | Pouring sound effect, volume 0-1 | `true` / `0.6` |
| `voice_enabled` / `voice_rate` / `voice_name` | Spoken reminder, speed, optional voice (e.g. `"Zira"`) | `true` / `170` / `""` |
| `brightness_auto` | Enable/disable brightness adjustment | `true` |
| `brightness_day` / `brightness_evening` / `brightness_night` | Target brightness % for each period | `100 / 60 / 30` |
| `day_start` / `evening_start` / `night_start` | Times (24h `HH:MM`) each period begins | `07:00 / 19:00 / 23:00` |
| `brightness_check_minutes` | How often to re-check/apply brightness | `15` |

Your daily count and streak are kept in `stats.json` (local only, git-ignored).

## About the brightness feature

Windows doesn't give regular desktop apps access to an ambient light sensor
reading, so this uses a **time-of-day schedule** instead (the same approach
Night Light and f.lux use) rather than reacting to actual room light. It
works reliably on most laptop built-in displays. External monitors need
DDC/CI support, which varies by monitor/cable — if adjustment fails, the app
logs a message and simply skips it rather than erroring out.

## Quitting

- Right-click the tray icon → "Quit Hydration Reminder" (clean shutdown), or
- Task Manager → find `pythonw.exe` → End Task, or
- If running via `python main.py` in a terminal, just press Ctrl+C.

## Files

- `main.py` - entry point
- `app.py` - scheduling/orchestration (snooze, quiet hours, retries)
- `animation.py` - the popup window (tkinter shell)
- `card.py` - composes each frame: scene + text + progress + buttons
- `scene3d.py` - the software 3D renderer (glass, water, bottle, particles)
- `sound.py` - procedural pouring-water sound + playback
- `messages.py` - the reminder library and selection logic
- `stats.py` - daily glasses, streak, recently shown reminders
- `themes.py` - time-of-day colour themes
- `voice.py` - offline text-to-speech
- `brightness.py` - schedule-based brightness adjustment
- `tray_icon.py` - system tray icon
- `config.py` - settings load/save
- `assets/` - generated `pour.wav` and `chime.wav` (run `python sound.py` to regenerate)
- `register_autostart.ps1` - optional Task Scheduler auto-start
