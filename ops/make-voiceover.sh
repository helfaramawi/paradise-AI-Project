#!/usr/bin/env bash
# Adds a natural Arabic voice-over to the demo video (Microsoft neural voices, free).
#   ops/make-voiceover.sh [male|female|<edge voice name>]
# Put future-mirror-demo-ar.mp4 and future-mirror-demo-ar.srt in docs/video first.
set -euo pipefail
cd "$(dirname "$0")/.."
VOICE=ar-EG-ShakirNeural
case "${1:-}" in female) VOICE=ar-EG-SalmaNeural ;; ar-*) VOICE=$1 ;; esac
command -v ffmpeg >/dev/null || { echo "Install FFmpeg first (macOS: brew install ffmpeg; Ubuntu: sudo apt install ffmpeg)"; exit 1; }
for f in docs/video/future-mirror-demo-ar.mp4 docs/video/future-mirror-demo-ar.srt; do
  [ -f "$f" ] || { echo "Missing $f: copy the demo video and its .srt into docs/video"; exit 1; }
done
python3 -m pip install --quiet --upgrade edge-tts
python3 scripts/voiceover/make_voiceover.py --video docs/video/future-mirror-demo-ar.mp4 \
  --srt docs/video/future-mirror-demo-ar.srt --voice "$VOICE"
echo "Done: docs/video/future-mirror-demo-ar-voice.mp4"
