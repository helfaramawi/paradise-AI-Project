#!/usr/bin/env bash
# Back up the Future Mirror AI database to backups/fm_YYYYMMDD_HHMMSS.dump
source "$(dirname "$0")/_common.sh"
check_docker
mkdir -p backups
docker compose up -d db
wait_db
file="backups/fm_$(date +%Y%m%d_%H%M%S).dump"
echo "Backing up the database ..."
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/fm_backup.dump'
docker compose cp db:/tmp/fm_backup.dump "$file"
docker compose exec -T db rm -f /tmp/fm_backup.dump
echo "Backup saved: $(pwd)/$file ($(wc -c < "$file" | tr -d ' ') bytes)"
