"""Offline voice reminder using pyttsx3 (Windows SAPI5 voices)."""
import threading


def speak(text, rate=170):
    """Speak text in a background thread so it never blocks the UI."""

    def _run():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", rate)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[voice] TTS failed: {e}")

    threading.Thread(target=_run, daemon=True).start()
