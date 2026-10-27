"""Pouring-water sound effect, synthesised procedurally (numpy only).

The sound is built the way water actually behaves in a glass:

* a bright "hiss" of noise from the falling stream
* a resonant tone that rises in pitch as the glass fills (the air column above
  the water gets shorter, so its resonant frequency climbs: the classic
  "glug glug glug" you hear when filling a bottle)
* random bubble "bloops" with upward chirps
* a splash at the start, a few drips at the end, and a soft sparkle when done

`ensure_sounds()` writes assets/pour.wav and assets/chime.wav (once). Playback
uses the built-in `winsound` on Windows with no extra dependencies, and falls
back to afplay/paplay/aplay elsewhere.
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np

SR = 22050
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
POUR_WAV = os.path.join(ASSETS, "pour.wav")
CHIME_WAV = os.path.join(ASSETS, "chime.wav")

FILL_SECONDS = 3.2       # keep in sync with Scene.T_POUR
TOTAL_SECONDS = 4.6


# ---------------------------------------------------------------- DSP helpers
def _biquad_bandpass(x, centers, q):
    """Band-pass filter with a time-varying centre frequency (RBJ biquad)."""
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    block = 64
    xl = x.tolist()
    out = y.tolist()
    n = len(xl)
    for start in range(0, n, block):
        fc = float(centers[min(start, n - 1)])
        w0 = 2 * math.pi * fc / SR
        alpha = math.sin(w0) / (2 * q)
        cw = math.cos(w0)
        a0 = 1 + alpha
        b0, b2 = alpha / a0, -alpha / a0
        a1, a2 = -2 * cw / a0, (1 - alpha) / a0
        for i in range(start, min(start + block, n)):
            xi = xl[i]
            yi = b0 * xi + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1 = x1, xi
            y2, y1 = y1, yi
            out[i] = yi
    return np.array(out)


def _smooth_noise(n, rate_hz, rng):
    """Slow random wobble in [0, 1] used for natural turbulence."""
    pts = rng.random(max(2, int(n / SR * rate_hz) + 2))
    return np.interp(np.linspace(0, len(pts) - 1, n), np.arange(len(pts)), pts)


def _envelope(n, t_on, t_off, attack, release):
    t = np.arange(n) / SR
    env = np.clip((t - t_on) / attack, 0, 1) * np.clip((t_off - t) / release, 0, 1)
    return env * env * (3 - 2 * env)


def _bloop(buf, t0, freq, amp, dur=0.07, rng=None):
    i0 = int(t0 * SR)
    n = int(dur * SR)
    if i0 < 0 or i0 + n >= len(buf):
        return
    t = np.arange(n) / SR
    f = freq * (1 + 0.8 * t / dur)                      # chirps upward
    phase = 2 * math.pi * np.cumsum(f) / SR
    env = np.exp(-t / (dur * 0.33)) * np.clip(t / 0.003, 0, 1)
    buf[i0:i0 + n] += amp * env * np.sin(phase)


def _sparkle(buf, t0, freq, amp, dur=0.55):
    i0 = int(t0 * SR)
    n = int(dur * SR)
    if i0 + n >= len(buf):
        n = len(buf) - i0 - 1
    t = np.arange(n) / SR
    env = np.exp(-t / (dur * 0.28)) * np.clip(t / 0.004, 0, 1)
    tone = np.sin(2 * math.pi * freq * t) + 0.35 * np.sin(2 * math.pi * freq * 2.01 * t) + \
        0.12 * np.sin(2 * math.pi * freq * 3.02 * t)
    buf[i0:i0 + n] += amp * env * tone


# ------------------------------------------------------------------ synthesis
def synth_pour(seed=7):
    rng = np.random.default_rng(seed)
    n = int(TOTAL_SECONDS * SR)
    t = np.arange(n) / SR
    pour_end = FILL_SECONDS

    env = _envelope(n, 0.0, pour_end, 0.10, 0.35)
    turb = 0.75 + 0.5 * _smooth_noise(n, 9, rng)

    # 1) falling stream: bright noise
    noise = rng.standard_normal(n)
    stream = _biquad_bandpass(noise, np.full(n, 2600.0), 0.6)
    stream += 0.6 * _biquad_bandpass(rng.standard_normal(n), np.full(n, 5200.0), 0.8)
    stream *= env * turb * 0.30

    # 2) cavity resonance that rises as the glass fills
    fill = np.clip(t / pour_end, 0, 1) * 0.86
    fres = 240.0 / (1.0 - fill + 0.12)
    cav = _biquad_bandpass(rng.standard_normal(n), fres, 11.0)
    cav *= env * (0.55 + 0.9 * _smooth_noise(n, 6, rng)) * 3.4

    # 3) low body of the splash
    body = _biquad_bandpass(rng.standard_normal(n), np.full(n, 420.0), 1.2) * env * 0.5

    out = stream + cav + body

    # 4) bubbles (pitch drifts up with the fill level)
    for _ in range(int(pour_end * 9)):
        t0 = rng.uniform(0.05, pour_end - 0.05)
        base = 520 + 900 * (t0 / pour_end) + rng.uniform(-120, 160)
        _bloop(out, t0, base, rng.uniform(0.07, 0.20), dur=rng.uniform(0.04, 0.09))

    # 5) first splash thump
    _bloop(out, 0.0, 150, 0.45, dur=0.14)
    _bloop(out, 0.02, 320, 0.25, dur=0.09)

    # 6) end: drips and a gentle two-note sparkle
    for t0, f, a in [(pour_end + 0.12, 1250, 0.13), (pour_end + 0.30, 1050, 0.09), (pour_end + 0.55, 1420, 0.07)]:
        _bloop(out, t0, f, a, dur=0.06)
    _sparkle(out, pour_end + 0.22, 1318.5, 0.075)
    _sparkle(out, pour_end + 0.36, 1760.0, 0.065)

    return _finish(out)


def synth_chime():
    n = int(0.9 * SR)
    out = np.zeros(n)
    _bloop(out, 0.0, 700, 0.30, dur=0.08)
    _sparkle(out, 0.06, 1318.5, 0.22, dur=0.6)
    _sparkle(out, 0.17, 1760.0, 0.20, dur=0.6)
    _sparkle(out, 0.29, 2217.5, 0.16, dur=0.55)
    return _finish(out, peak=0.7)


def _finish(x, peak=0.85):
    x = x - np.mean(x)
    fade = int(0.04 * SR)
    x[-fade:] *= np.linspace(1, 0, fade)
    x = np.tanh(1.4 * x / max(np.max(np.abs(x)), 1e-9)) / np.tanh(1.4)   # soft limiter
    return (x * peak).astype(np.float32)


def write_wav(path, samples, volume=1.0):
    pcm = (np.clip(samples * volume, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def ensure_sounds():
    """Create the wav files if they don't exist yet (takes a second or two)."""
    os.makedirs(ASSETS, exist_ok=True)
    if not os.path.exists(POUR_WAV):
        write_wav(POUR_WAV, synth_pour())
    if not os.path.exists(CHIME_WAV):
        write_wav(CHIME_WAV, synth_chime())


# -------------------------------------------------------------------- playback
class SoundPlayer:
    """Plays the pour/chime sounds. Never raises: sound is a bonus, not a requirement."""

    def __init__(self, enabled=True, volume=0.7):
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, float(volume)))
        self._files = {}
        self._tmpdir = None
        if not enabled:
            return
        try:
            ensure_sounds()
            self._files = {"pour": self._scaled(POUR_WAV), "chime": self._scaled(CHIME_WAV)}
        except Exception as e:
            print(f"[sound] Could not prepare sounds: {e}")
            self.enabled = False

    def _scaled(self, src):
        """Return a path to a copy of src at the configured volume (winsound has no volume control)."""
        if abs(self.volume - 1.0) < 0.01:
            return src
        if self._tmpdir is None:
            self._tmpdir = tempfile.mkdtemp(prefix="hydration_")
        with wave.open(src, "rb") as w:
            frames = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        dst = os.path.join(self._tmpdir, os.path.basename(src))
        scaled = (frames.astype(np.float32) / 32767.0)
        write_wav(dst, scaled, self.volume)
        return dst

    def _play(self, name):
        if not self.enabled or name not in self._files:
            return
        path = self._files[name]
        try:
            if sys.platform.startswith("win"):
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            for cmd in (["afplay", path], ["paplay", path], ["aplay", "-q", path]):
                if shutil.which(cmd[0]):
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return
        except Exception as e:
            print(f"[sound] Playback failed: {e}")

    def play_pour(self):
        self._play("pour")

    def play_chime(self):
        self._play("chime")


if __name__ == "__main__":
    # `python sound.py` regenerates the sound files.
    os.makedirs(ASSETS, exist_ok=True)
    write_wav(POUR_WAV, synth_pour())
    write_wav(CHIME_WAV, synth_chime())
    print("Wrote", POUR_WAV, "and", CHIME_WAV)
