#!/usr/bin/env bash
# Start Future Mirror AI (builds the images on first run).
source "$(dirname "$0")/_common.sh"
check_docker
echo "Starting Future Mirror AI ..."
docker compose up -d
wait_app
