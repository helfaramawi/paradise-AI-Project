"""Adds a natural Arabic voice-over to the demo video, line by line from its SRT file.

    python scripts/voiceover/make_voiceover.py --video docs/video/future-mirror-demo-ar.mp4 \
        --srt docs/video/future-mirror-demo-ar.srt [--voice ar-EG-ShakirNeural] [--engine edge|piper|dummy]

Engines
  edge   Microsoft neural voices through the free Edge read-aloud service (pip install edge-tts).
         Arabic voices: ar-EG-ShakirNeural (male, default), ar-EG-SalmaNeural (female),
         ar-SA-HamedNeural (male), ar-SA-ZariyahNeural (female). Needs internet.
  piper  Fully offline neural TTS (pip install piper-tts; voice: python -m piper.download_voices
         ar_JO-kareem-medium). Pass --piper-model path/to/ar_JO-kareem-medium.onnx.
  dummy  Tones of the expected speech length; used to test timing and mixing without a TTS service.

Each caption is spoken at natural speed, starting just after it appears. Speech is never sped
up: when a line needs longer than its caption stays on screen, the picture is held (the last
frame, caption still visible) until the line has finished plus a short pause, and everything
after it shifts later. A matching SRT for the new timeline is written next to the output.
The voice is loudness-normalised (-16 LUFS). Requires ffmpeg/ffprobe (with libx264) on PATH.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import bisect
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

LEAD_IN = 0.25    # the caption appears, then the voice starts
PAUSE = 0.7       # silence after a line before the next caption appears
FPS = 25
SR = 48000        # sample rate of the voice track


@dataclass
class Cue:
    start: float
    end: float
    text: str


def parse_srt(path: Path) -> list[Cue]:
    def t(s: str) -> float:
        h, m, rest = s.strip().split(":")
        sec, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000

    cues = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) >= 3 and "-->" in lines[1]:
            a, b = lines[1].split("-->")
            cues.append(Cue(t(a), t(b), " ".join(lines[2:]).strip()))
    return cues


def run(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise SystemExit(f"Command failed: {' '.join(cmd[:4])} ...\n{res.stderr[-1500:]}")
    return res.stdout


def duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)]))


def speakable(text: str) -> str:
    # Captions like "محكمة الوكلاء — مواقف…" read better with a pause instead of a dash.
    return text.replace(" — ", "، ").replace("«", "").replace("»", "")


# ------------------------------------------------------------------ engines
async def synth_edge(text: str, out: Path, voice: str, rate_pct: int) -> None:
    import edge_tts  # noqa: PLC0415

    rate = f"{'+' if rate_pct >= 0 else ''}{rate_pct}%"
    for attempt in range(4):
        try:
            proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None  # corporate networks
            await edge_tts.Communicate(text, voice, rate=rate, proxy=proxy).save(str(out))
            return
        except Exception as exc:  # network hiccups: retry with backoff
            if attempt == 3:
                raise SystemExit(f"Edge TTS failed ({exc}). Check your internet connection, or use --engine piper.") from exc
            await asyncio.sleep(2 * (attempt + 1))


def synth_piper(text: str, out: Path, model: str, length_scale: float) -> None:
    exe = shutil.which("piper")
    cmd = ([exe] if exe else [sys.executable, "-m", "piper"]) + ["-m", model, "-f", str(out), "--length-scale", f"{length_scale:.3f}"]
    res = subprocess.run(cmd, input=text, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0 or not out.exists():
        raise SystemExit(f"Piper failed: {res.stderr[-800:]}")


def synth_dummy(text: str, out: Path, speed: float, rate: int = 0) -> None:
    secs = max(1.0, len(text.split()) * 0.42 / speed * 100 / (100 + rate))  # --rate -40 = slow speech, for tests
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=220:duration={secs:.2f}",
         "-af", "volume=0.15", str(out)])


async def synth(args, text: str, out: Path, speed: float) -> None:
    """Synthesise into `out`, reusing a cached clip when the same line was made before."""
    key = hashlib.sha1(f"{args.engine}|{args.voice}|{args.rate}|{args.piper_model}|{speed:.3f}|{text}".encode()).hexdigest()
    cached = args.cache / f"{key}{out.suffix}"
    if cached.exists() and cached.stat().st_size > 0:
        shutil.copyfile(cached, out)
        return
    await _synth(args, text, out, speed)
    shutil.copyfile(out, cached)


async def _synth(args, text: str, out: Path, speed: float) -> None:
    if args.engine == "edge":
        await synth_edge(text, out, args.voice, round((speed - 1) * 100) + args.rate)
    elif args.engine == "piper":
        synth_piper(text, out, args.piper_model, 1 / speed)
    else:
        synth_dummy(text, out, speed, args.rate)


# ------------------------------------------------------------------ main
async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--srt", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--engine", choices=["edge", "piper", "dummy"], default="edge")
    ap.add_argument("--voice", default="ar-EG-ShakirNeural")
    ap.add_argument("--rate", type=int, default=0, help="speaking-rate change in %% (edge only), e.g. -5 slower, 8 faster")
    ap.add_argument("--piper-model", help="path to a piper .onnx voice (engine piper)")
    ap.add_argument("--music", type=Path, help="optional background music file (mp3/m4a/wav), looped and kept low")
    ap.add_argument("--music-volume", type=float, default=-18.0, help="music level in dB below the voice (default -18; e.g. -24 quieter, -14 louder)")
    ap.add_argument("--keep-temp", action="store_true")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} not found. Install FFmpeg (Windows: winget install Gyan.FFmpeg) and open a new terminal.")
    if args.engine == "piper" and not args.piper_model:
        raise SystemExit("--piper-model is required with --engine piper")
    if args.engine == "edge":
        try:
            import edge_tts  # noqa: F401, PLC0415
        except ImportError:
            raise SystemExit("edge-tts is not installed: python -m pip install edge-tts") from None

    cues = parse_srt(args.srt)
    if not cues:
        raise SystemExit(f"No captions found in {args.srt}")
    video_len = duration(args.video)
    out = args.out or args.video.with_name(args.video.stem + "-voice.mp4")
    tmp = Path(tempfile.mkdtemp(prefix="fm-voice-"))
    args.cache = out.parent / ".voice-cache"  # re-runs reuse lines already synthesised
    args.cache.mkdir(parents=True, exist_ok=True)
    ext = "mp3" if args.engine == "edge" else "wav"
    lines: list[tuple[Path, float]] = []  # (clip, speech duration)
    freezes: list[tuple[float, float]] = []  # (time in source video, seconds to hold the frame)
    print(f"{len(cues)} lines · engine {args.engine}{' · voice ' + args.voice if args.engine == 'edge' else ''}")

    for i, cue in enumerate(cues):
        nxt = cues[i + 1].start if i + 1 < len(cues) else video_len
        clip = tmp / f"l{i:03d}.{ext}"
        await synth(args, speakable(cue.text), clip, 1.0)
        d = duration(clip)
        shown_until = min(cue.end, nxt)  # chapter cards disappear a moment before the next caption
        on_screen = shown_until - cue.start
        extra = max(0.0, LEAD_IN + d + PAUSE - on_screen)  # time the caption still needs on screen
        if extra > 0.04:  # hold a frame where this caption/card is still fully visible
            freezes.append((max(cue.start + 0.2, shown_until - 0.12), extra))
        note = f"  +{extra:.1f}s hold" if extra > 0.04 else ""
        print(f"  {i + 1:>3}/{len(cues)}  {cue.start:7.1f}s  speech {d:5.1f}s / on screen {on_screen:5.1f}s{note}")
        lines.append((clip, d))

    # 1) Picture: cut at each hold point and freeze the last frame there (caption stays visible).
    segs: list[tuple[float, float]] = []  # (source start, new start)
    if freezes:
        print(f"\nHolding the picture at {len(freezes)} points (+{sum(e for _, e in freezes):.0f}s) and re-encoding ...")
        cuts = [0.0] + [t for t, _ in freezes] + ([video_len] if freezes[-1][0] < video_len - 0.01 else [])
        holds = {t: e for t, e in freezes}
        parts, new_t = [], 0.0
        for k in range(len(cuts) - 1):
            a, b = cuts[k], cuts[k + 1]
            if b - a < 0.02:
                continue
            seg = tmp / f"seg{k:03d}.mp4"
            vf = f"fps={FPS}" + (f",tpad=stop_mode=clone:stop_duration={holds[b]:.3f}" if b in holds else "")
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(args.video), "-an",
                 "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                 "-r", str(FPS), str(seg)])
            segs.append((a, new_t))
            new_t += duration(seg)
            parts.append(seg)
            print(f"    segment {len(parts):>3}  {a:7.1f}s → {b:7.1f}s{'  + hold ' + format(holds[b], '.1f') + 's' if b in holds else ''}")
        listing = tmp / "segments.txt"
        listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        picture = tmp / "picture.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(picture)])
        new_len = duration(picture)
    else:
        picture, new_len = args.video, video_len
        segs = [(0.0, 0.0)]
    starts = [a for a, _ in segs]

    def remap(t: float) -> float:  # source-video time -> output time
        k = max(0, bisect.bisect_right(starts, t + 1e-6) - 1)
        return segs[k][1] + (t - segs[k][0])

    # 2) Voice track, built in Python on the new timeline (works with every FFmpeg version).
    voice = tmp / "voice.wav"
    total = int(new_len * SR)
    new_starts = [remap(c.start) for c in cues]
    with wave.open(str(voice), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        pos = 0
        for (clip, _), st in zip(lines, new_starts, strict=True):
            at = int((st + LEAD_IN) * SR)
            if at > pos:
                w.writeframes(b"\x00\x00" * (at - pos))
                pos = at
            pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                                 capture_output=True, check=True).stdout
            w.writeframes(pcm)
            pos += len(pcm) // 2
        if pos < total:
            w.writeframes(b"\x00\x00" * (total - pos))

    # 3) Mux: picture copied, voice loudness-normalised (broadcast-style -16 LUFS), stereo AAC.
    #    Optional music: normalised to the voice's loudness, then lowered (default 18 dB below), looped,
    #    faded in/out, and ducked a further ~8 dB while the voice speaks.
    common = ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-movflags", "+faststart", "-t", f"{new_len:.3f}", str(out)]
    if args.music:
        if not args.music.exists():
            raise SystemExit(f"Music file not found: {args.music}")
        fade_out = max(0.0, new_len - 5)
        graph = (f"[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,aformat=sample_rates={SR}:channel_layouts=stereo,asplit=2[v][key];"
                 f"[2:a]aformat=sample_rates={SR}:channel_layouts=stereo,loudnorm=I=-16:TP=-2,volume={args.music_volume:.1f}dB,"
                 f"afade=t=in:d=3,afade=t=out:st={fade_out:.2f}:d=5[m];"
                 "[m][key]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=600[duck];"
                 "[v][duck]amix=inputs=2:normalize=0:duration=first[a]")
        run(["ffmpeg", "-y", "-v", "error", "-i", str(picture), "-i", str(voice), "-stream_loop", "-1", "-i", str(args.music),
             "-filter_complex", graph, "-map", "0:v:0", "-map", "[a]", *common])
        print(f"Background music: {args.music.name}, {abs(args.music_volume):.0f} dB below the voice, ducked while it speaks")
    else:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(picture), "-i", str(voice), "-map", "0:v:0", "-map", "1:a:0",
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ac", "2", *common])

    # 4) Subtitles for the new timeline (each caption until the next one appears).
    def stamp(x: float) -> str:
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    ends = new_starts[1:] + [new_len]
    out.with_suffix(".srt").write_text("\n".join(
        f"{n + 1}\n{stamp(a)} --> {stamp(max(a + 0.5, b - 0.05))}\n{c.text}\n"
        for n, (c, a, b) in enumerate(zip(cues, new_starts, ends, strict=True))), encoding="utf-8")

    if not args.keep_temp:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nDone: {out}  ({math.floor(new_len / 60)}:{int(new_len % 60):02d}"
          f"{f', was {math.floor(video_len / 60)}:{int(video_len % 60):02d}' if freezes else ''})")
    print(f"Subtitles: {out.with_suffix('.srt')}")


if __name__ == "__main__":
    asyncio.run(main())
