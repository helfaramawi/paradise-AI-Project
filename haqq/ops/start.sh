#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."; . ops/_common.sh
check_docker
[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example - review it before real use."; }
docker compose up -d --build
wait_app
