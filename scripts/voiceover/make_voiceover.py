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

Each caption is spoken at its start time. When a line is longer than the gap before the next
caption, it is re-synthesised faster (edge) or time-compressed (max 1.35x) so lines never
overlap and captions stay in sync. The result is loudness-normalised and muxed without
re-encoding the picture. Requires ffmpeg/ffprobe on PATH.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

GAP = 0.15        # seconds of silence kept before the next caption
LEAD_IN = 0.12    # small delay after a caption appears before the voice starts
MAX_TEMPO = 1.35  # never speed speech up beyond this


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


def synth_dummy(text: str, out: Path, speed: float) -> None:
    secs = max(1.0, len(text.split()) * 0.42 / speed)
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=220:duration={secs:.2f}",
         "-af", "volume=0.15", str(out)])


async def synth(args, text: str, out: Path, speed: float) -> None:
    if args.engine == "edge":
        await synth_edge(text, out, args.voice, round((speed - 1) * 100) + args.rate)
    elif args.engine == "piper":
        synth_piper(text, out, args.piper_model, 1 / speed)
    else:
        synth_dummy(text, out, speed)


# ------------------------------------------------------------------ main
async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--srt", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--engine", choices=["edge", "piper", "dummy"], default="edge")
    ap.add_argument("--voice", default="ar-EG-ShakirNeural")
    ap.add_argument("--rate", type=int, default=0, help="base speaking-rate change in %% (edge only), e.g. -5 or 8")
    ap.add_argument("--piper-model", help="path to a piper .onnx voice (engine piper)")
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
    ext = "mp3" if args.engine == "edge" else "wav"
    placed: list[tuple[Path, float]] = []
    print(f"{len(cues)} lines · engine {args.engine}{' · voice ' + args.voice if args.engine == 'edge' else ''}")

    for i, cue in enumerate(cues):
        nxt = cues[i + 1].start if i + 1 < len(cues) else video_len
        start = cue.start + LEAD_IN
        slot = max(0.8, nxt - GAP - start)
        text = speakable(cue.text)
        clip = tmp / f"l{i:03d}.{ext}"
        await synth(args, text, clip, 1.0)
        d = duration(clip)
        if d > slot:  # too long for its gap: re-synthesise faster, then compress if still needed
            speed = min(MAX_TEMPO, d / slot * 1.03)
            await synth(args, text, clip, speed)
            d = duration(clip)
            if d > slot:
                tempo = min(MAX_TEMPO, d / slot)
                fitted = tmp / f"l{i:03d}-fit.wav"
                run(["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-filter:a", f"atempo={tempo:.3f}", str(fitted)])
                clip, d = fitted, duration(fitted)
        flag = "  (tight)" if d > slot + 0.05 else ""
        print(f"  {i + 1:>3}/{len(cues)}  {cue.start:7.1f}s  {d:5.1f}s / {slot:5.1f}s{flag}")
        placed.append((clip, start))

    # Mix: each line delayed to its start time, summed, loudness-normalised (broadcast-style -16 LUFS).
    voice = tmp / "voice.wav"
    inputs: list[str] = []
    chains = []
    for k, (clip, start) in enumerate(placed):
        inputs += ["-i", str(clip)]
        ms = int(round(start * 1000))
        chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}:all=1[a{k}]")
    mix = "".join(f"[a{k}]" for k in range(len(placed)))
    graph = ";".join(chains) + f";{mix}amix=inputs={len(placed)}:normalize=0:dropout_transition=0," \
        f"apad=whole_dur={video_len:.3f},atrim=0:{video_len:.3f},loudnorm=I=-16:TP=-1.5:LRA=11[out]"
    script = tmp / "graph.txt"
    script.write_text(graph, encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex_script", str(script), "-map", "[out]",
         "-ac", "2", "-ar", "48000", str(voice)])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(args.video), "-i", str(voice), "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{video_len:.3f}", str(out)])
    if not args.keep_temp:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nDone: {out}  ({math.floor(video_len / 60)}:{int(video_len % 60):02d})")


if __name__ == "__main__":
    asyncio.run(main())
