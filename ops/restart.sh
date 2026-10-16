#!/usr/bin/env bash
# Restart Future Mirror AI (stop, then start), rebuilding if the code changed. Use after editing .env or pulling.
source "$(dirname "$0")/_common.sh"
check_docker
echo "Restarting Future Mirror AI ..."
docker compose down
docker compose up -d --build
wait_app
