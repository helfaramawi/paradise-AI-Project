#!/usr/bin/env bash
# Dynamics 365 F&O + OData demo (Modern Standard Arabic) with a female voice and calm background music.
# Put future-mirror-demo-d365.mp4 and future-mirror-demo-d365.srt in docs/video first.
# Optional first argument: another voice, e.g. ar-SA-ZariyahNeural (default: female = ar-EG-SalmaNeural).
# The music (docs/video/music-calm.mp3) sits 26 dB below the voice and dips further while she speaks;
# change it with FM_MUSIC_VOLUME=-30 (quieter) or -22 (louder), or FM_MUSIC=none for no music.
cd "$(dirname "$0")/.."
export FM_VOICE_RATE="${FM_VOICE_RATE:-0}"
export FM_MUSIC_VOLUME="${FM_MUSIC_VOLUME:--26}"
[ "${FM_MUSIC:-}" = none ] || export FM_MUSIC="${FM_MUSIC:-docs/video/music-calm.mp3}"
exec ops/make-voiceover.sh "${1:-female}" future-mirror-demo-d365
