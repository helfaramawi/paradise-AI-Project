#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."; . ops/_common.sh
check_docker
echo "Step 1/3: verified backup"; ops/backup.sh
echo "Step 2/3: git pull"; git pull origin main
echo "Step 3/3: rebuild"; docker compose up -d --build; wait_app
