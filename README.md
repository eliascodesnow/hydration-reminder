# Hydration Reminder

A lightweight background app for Windows that, every 2 hours (configurable):

- Pops up a small animated "pouring water" window
- Reads a voice reminder out loud (offline text-to-speech, no internet needed)
- Auto-closes itself after 20 seconds (configurable) so it never lingers
- Periodically checks the time of day and adjusts your screen brightness on a schedule

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
| `popup_duration_sec` | Seconds before the popup auto-closes | `20` |
| `voice_enabled` | Speak the reminder aloud | `true` |
| `voice_rate` | Speech speed (words/min) | `170` |
| `brightness_auto` | Enable/disable brightness adjustment | `true` |
| `brightness_day` / `brightness_evening` / `brightness_night` | Target brightness % for each period | `100 / 60 / 30` |
| `day_start` / `evening_start` / `night_start` | Times (24h `HH:MM`) each period begins | `07:00 / 19:00 / 23:00` |
| `brightness_check_minutes` | How often to re-check/apply brightness | `15` |

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

- `main.py` — entry point
- `app.py` — scheduling/orchestration
- `animation.py` — the popup + water animation
- `voice.py` — offline text-to-speech
- `brightness.py` — schedule-based brightness adjustment
- `tray_icon.py` — system tray icon (test/quit)
- `config.py` — settings load/save
- `config.json` — your settings (created on first run)
- `register_autostart.ps1` — optional Task Scheduler auto-start
