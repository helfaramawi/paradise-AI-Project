#!/usr/bin/env bash
# Stop Future Mirror AI. Your data is kept (the database volume is not deleted).
source "$(dirname "$0")/_common.sh"
check_docker
echo "Stopping Future Mirror AI ..."
docker compose --profile automation down
echo "Stopped. Your data is kept. Run ops/start.sh to start again."
