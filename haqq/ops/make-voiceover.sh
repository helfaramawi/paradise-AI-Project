#!/usr/bin/env bash
# Adds the Egyptian Arabic voice-over to haqq/docs/video/haqq-demo-ar.mp4 (needs internet, Python, FFmpeg).
#   ops/make-voiceover.sh [male|female|<edge voice>]      env: HQ_MUSIC=none|file, HQ_MUSIC_VOLUME=-24, HQ_VOICE_RATE=0
set -euo pipefail
cd "$(dirname "$0")/.."
VOICE=ar-EG-ShakirNeural; case "${1:-}" in female) VOICE=ar-EG-SalmaNeural ;; ar-*) VOICE=$1 ;; esac
for f in docs/video/haqq-demo-ar.mp4 docs/video/haqq-demo-ar.srt; do [ -f "$f" ] || { echo "Missing $f - run ops/record-demo.sh first"; exit 1; }; done
python3 -m pip install --quiet --upgrade edge-tts
MUSIC=(); [ -f ../docs/video/music-calm.mp3 ] && MUSIC=(--music ../docs/video/music-calm.mp3)
[ "${HQ_MUSIC:-}" = none ] && MUSIC=(); [ -n "${HQ_MUSIC:-}" ] && [ -f "${HQ_MUSIC}" ] && MUSIC=(--music "$HQ_MUSIC")
[ ${#MUSIC[@]} -gt 0 ] && MUSIC+=(--music-volume "${HQ_MUSIC_VOLUME:--24}")
python3 ../scripts/voiceover/make_voiceover.py --video docs/video/haqq-demo-ar.mp4 --srt docs/video/haqq-demo-ar.srt \
  --voice "$VOICE" --rate "${HQ_VOICE_RATE:-0}" "${MUSIC[@]}"
echo "Done: docs/video/haqq-demo-ar-voice.mp4"
