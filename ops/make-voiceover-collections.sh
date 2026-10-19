#!/usr/bin/env bash
# Port Said Free Zone demo (collections question, Modern Standard Arabic) with a female voice.
# Put future-mirror-demo-collections.mp4 and future-mirror-demo-collections.srt in docs/video first.
# Optional first argument: another voice, e.g. ar-SA-ZariyahNeural (default: female = ar-EG-SalmaNeural).
FM_VOICE_RATE="${FM_VOICE_RATE:-10}" exec "$(dirname "$0")/make-voiceover.sh" "${1:-female}" future-mirror-demo-collections
