#!/usr/bin/env bash
# Records the Arabic HAQQ demo video from the running app (ops/start.sh first). Needs Node 22 and FFmpeg.
set -euo pipefail
cd "$(dirname "$0")/.."; . ops/_common.sh; hq_port
docker compose exec -T backend python -m app.demo.seed --reset >/dev/null
cd frontend; [ -d node_modules ] || npm ci --no-audit --no-fund; npx playwright install chromium
BASE_URL="http://localhost:$HQ_PORT" OUT_DIR=../docs/video node e2e/video/record-demo-ar.mjs
echo "Done: docs/video/haqq-demo-ar.mp4 - now run ops/make-voiceover.sh"
