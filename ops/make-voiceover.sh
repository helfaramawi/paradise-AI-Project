#!/usr/bin/env bash
# Adds a natural Arabic voice-over to the demo video (Microsoft neural voices, free).
#   ops/make-voiceover.sh [male|female|<edge voice name>] [video name without .mp4]
# Put the video (.mp4) and its .srt in docs/video first (default: future-mirror-demo-ar).
# Optional background music: docs/video/music.mp3 (or .m4a/.wav), kept low and ducked under the voice.
set -euo pipefail
cd "$(dirname "$0")/.."
VOICE=ar-EG-ShakirNeural
case "${1:-}" in female) VOICE=ar-EG-SalmaNeural ;; ar-*) VOICE=$1 ;; esac
VIDEO="${2:-future-mirror-demo-ar}"
command -v ffmpeg >/dev/null || { echo "Install FFmpeg first (macOS: brew install ffmpeg; Ubuntu: sudo apt install ffmpeg)"; exit 1; }
for f in docs/video/$VIDEO.mp4 docs/video/$VIDEO.srt; do
  [ -f "$f" ] || { echo "Missing $f: copy the demo video and its .srt into docs/video"; exit 1; }
done
python3 -m pip install --quiet --upgrade edge-tts
MUSIC=()
for m in docs/video/music.mp3 docs/video/music.m4a docs/video/music.wav; do [ -f "$m" ] && MUSIC=(--music "$m"); done
python3 scripts/voiceover/make_voiceover.py --video docs/video/$VIDEO.mp4 \
  --srt docs/video/$VIDEO.srt --voice "$VOICE" "${MUSIC[@]}"
echo "Done: docs/video/$VIDEO-voice.mp4"
