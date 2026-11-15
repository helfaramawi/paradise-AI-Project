"""Generate an original, calm ambient background track for the demo videos (no samples, no copyright).

    python scripts/voiceover/make_calm_music.py [out.mp3] [--minutes 4]

Slow pad chords (Am - Fmaj7 - C - G, 8 seconds each) built from soft detuned sines with long
attack and release, a quiet low drone, sparse bell notes from the A minor pentatonic scale and a
light stereo echo. No drums and nothing in the 1-4 kHz band where speech sits, so it stays behind
the voice. The end fades into the start, so the voice-over tool can loop it seamlessly.
Requires numpy and ffmpeg.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 44100
CHORDS = [  # MIDI notes: Am, Fmaj7, C(add9), G(6)
    [45, 57, 60, 64, 69], [41, 53, 57, 60, 64], [48, 55, 60, 62, 67], [43, 55, 59, 62, 64]]
BELL = [69, 72, 74, 76, 79, 81]  # A minor pentatonic, upper register
CHORD_S = 8.0


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def envelope(n: int, attack: float, release: float) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / attack, 0, 1)
    r = np.clip((n / SR - t) / release, 0, 1)
    return (np.sin(a * np.pi / 2) * np.sin(r * np.pi / 2)) ** 2


def pad(notes: list[int], seconds: float, rng: np.random.Generator) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for i, m in enumerate(notes):
        f = hz(m)
        level = 0.16 if i == 0 else 0.10 / (1 + 0.15 * i)
        for side, det in ((0, -0.12), (1, 0.12)):  # gentle detune for width
            ph = rng.uniform(0, 2 * np.pi)
            wob = 1 + 0.002 * np.sin(2 * np.pi * 0.11 * t + ph)
            tone = np.sin(2 * np.pi * (f + det) * wob * t + ph) + 0.18 * np.sin(2 * np.pi * 2 * (f + det) * t + ph)
            out[:, side] += level * tone
    return out * envelope(n, 2.8, 3.2)[:, None]


def bell(m: int, seconds: float = 4.5) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    f = hz(m)
    tone = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2.01 * f * t) + 0.12 * np.sin(2 * np.pi * 3.0 * f * t))
    env = np.exp(-t * 1.1) * np.clip(t / 0.02, 0, 1)
    return 0.05 * tone * env


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = np.zeros(x.shape[1])
    for i in range(len(x)):  # one-pole filter, applied twice below
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def compose(minutes: float, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    total = int(minutes * 60 / (CHORD_S * len(CHORDS))) * len(CHORDS)  # whole progressions only
    length = int(total * CHORD_S * SR)
    mix = np.zeros((length + int(10 * SR), 2))
    for k in range(total):
        start = int(k * CHORD_S * SR)
        p = pad(CHORDS[k % len(CHORDS)], CHORD_S + 3.5, rng)  # overlap the next chord
        mix[start:start + len(p)] += p
        if rng.random() < 0.55:  # a sparse bell, never on every chord
            b = bell(int(rng.choice(BELL)))
            at = start + int(rng.uniform(1.5, 5.5) * SR)
            pan = rng.uniform(0.3, 0.7)
            mix[at:at + len(b), 0] += b * (1 - pan)
            mix[at:at + len(b), 1] += b * pan
    t = np.arange(len(mix)) / SR
    drone = 0.05 * np.sin(2 * np.pi * hz(33) * t) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.05 * t))
    mix += drone[:, None]
    tail = mix[length:]  # wrap the overlap into the start: a seamless loop
    mix = mix[:length]
    mix[:len(tail)] += tail
    delay = int(0.38 * SR)  # light ping-pong echo
    echo = np.zeros_like(mix)
    echo[delay:, 0] = mix[:-delay, 1] * 0.22
    echo[delay:, 1] = mix[:-delay, 0] * 0.22
    mix = lowpass(lowpass(mix + echo, 1800.0), 1800.0)  # keep it soft, out of the speech band
    return mix / np.max(np.abs(mix)) * 0.7


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", nargs="?", type=Path, default=Path("docs/video/music-calm.mp3"))
    ap.add_argument("--minutes", type=float, default=4.0)
    args = ap.parse_args()
    audio = compose(args.minutes)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "music.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((audio * 32767).astype("<i2").tobytes())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "128k", str(args.out)],
                       check=True)
    print(f"Wrote {args.out} ({len(audio) / SR / 60:.1f} min)")


if __name__ == "__main__":
    main()
