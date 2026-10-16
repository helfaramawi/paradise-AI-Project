#!/usr/bin/env bash
# Start Future Mirror AI. Rebuilds the images when the code has changed (e.g. after git pull).
source "$(dirname "$0")/_common.sh"
check_docker
echo "Starting Future Mirror AI ..."
docker compose up -d --build
wait_app
