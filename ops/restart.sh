#!/usr/bin/env bash
# Restart Future Mirror AI (stop, then start). Use after editing .env.
source "$(dirname "$0")/_common.sh"
check_docker
echo "Restarting Future Mirror AI ..."
docker compose down
docker compose up -d
wait_app
