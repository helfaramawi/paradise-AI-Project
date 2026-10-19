#!/usr/bin/env bash
# Egyptian-dialect demo (collections question) with the Egyptian female voice (ar-EG-SalmaNeural).
# Put future-mirror-demo-eg.mp4 and future-mirror-demo-eg.srt in docs/video first.
exec "$(dirname "$0")/make-voiceover.sh" female future-mirror-demo-eg
