"""Offline voice reminder using pyttsx3 (Windows SAPI5 voices).

By default every reminder is spoken by a different installed voice (never the same
one twice in a row). Set "voice_name" in config.json to pin one specific voice, or
set "voice_random" to false to always use the system default.
"""
import random
import threading

_last_voice_id = None
_lock = threading.Lock()


def _is_english(v):
    text = f"{getattr(v, 'name', '')} {getattr(v, 'id', '')}".lower()
    langs = " ".join(str(l) for l in (getattr(v, "languages", None) or [])).lower()
    return any(k in text + langs for k in ("english", "en-us", "en-gb", "en_us", "en_gb", "en-au", "en-in", "0409", "0809"))


def _choose_voice(voices, voice_name, randomize):
    """Returns a voice id, or None to keep the engine default."""
    global _last_voice_id
    if not voices:
        return None
    if voice_name:
        for v in voices:
            if voice_name.lower() in (v.name or "").lower():
                return v.id
        return None
    if not randomize:
        return None
    pool = [v for v in voices if _is_english(v)] or list(voices)
    with _lock:
        choices = [v for v in pool if v.id != _last_voice_id] or pool
        pick = random.choice(choices)
        _last_voice_id = pick.id
    return pick.id


def speak(text, rate=170, voice_name="", volume=1.0, randomize=True):
    """Speak text in a background thread so it never blocks the UI."""

    def _run():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", rate)
            engine.setProperty("volume", volume)
            vid = _choose_voice(engine.getProperty("voices"), voice_name, randomize)
            if vid:
                engine.setProperty("voice", vid)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[voice] TTS failed: {e}")

    threading.Thread(target=_run, daemon=True).start()
