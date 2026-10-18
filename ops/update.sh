#!/usr/bin/env bash
# Update to the latest version: back up, pull the latest code from GitHub, rebuild and restart.
source "$(dirname "$0")/_common.sh"
check_docker
echo "Step 1/3: taking a full, verified backup ..."
"$OPS_DIR/backup.sh"
echo "Step 2/3: pulling the latest code ..."
git pull origin main
echo "Step 3/3: rebuilding and restarting ..."
docker compose up -d --build
wait_app
echo "Update complete."
