"""Offline voice reminder using pyttsx3 (Windows SAPI5 voices)."""
import threading


def speak(text, rate=170, voice_name="", volume=1.0):
    """Speak text in a background thread so it never blocks the UI."""

    def _run():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", rate)
            engine.setProperty("volume", volume)
            if voice_name:
                for v in engine.getProperty("voices"):
                    if voice_name.lower() in (v.name or "").lower():
                        engine.setProperty("voice", v.id)
                        break
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[voice] TTS failed: {e}")

    threading.Thread(target=_run, daemon=True).start()
