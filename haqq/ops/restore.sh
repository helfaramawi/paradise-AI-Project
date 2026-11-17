#!/usr/bin/env bash
# Restore HAQQ from a backup folder (macOS / Linux). Same behaviour as restore.bat.
#   ops/restore.sh haqq_20261118_090000      (folder name in haqq/backups or a path)
set -euo pipefail
cd "$(dirname "$0")/.."; . ops/_common.sh
check_docker
SRC=${1:-}
if [ -z "$SRC" ]; then echo "Available backups:"; ls -1d backups/haqq_* 2>/dev/null | sort -r; read -rp "Backup name: " SRC; fi
[ -d "$SRC" ] || SRC="backups/$SRC"
[ -f "$SRC/database.dump" ] && [ -f "$SRC/documents.tar.gz" ] || { echo "[ERROR] $SRC is not a complete HAQQ backup"; exit 1; }
SRC=$(cd "$SRC" && pwd)
grep -E '^(Created|Code version|Database|Documents):' "$SRC/manifest.txt" 2>/dev/null || true
echo "WARNING: this replaces ALL current HAQQ data with $SRC"
read -rp "Type YES to continue: " OK; [ "$OK" = "YES" ] || { echo "Cancelled."; exit 0; }
if [ -f "$SRC/env.backup" ]; then
  if [ ! -f .env ]; then cp "$SRC/env.backup" .env; echo "Restored .env"; 
  elif ! cmp -s .env "$SRC/env.backup"; then cp "$SRC/env.backup" .env.from-backup; echo "Kept current .env; backed-up one saved as .env.from-backup"; fi
fi
if docker compose ps --status running --services 2>/dev/null | grep -qx backend; then echo "Safety backup first ..."; ops/backup.sh; fi
echo "1/4 Stopping HAQQ ..."; docker compose stop frontend worker backend >/dev/null 2>&1 || true
docker compose up -d db >/dev/null; wait_db
echo "2/4 Restoring the database ..."
docker compose cp ops/db/haqq_db.sh db:/tmp/haqq_db.sh >/dev/null
docker compose cp "$SRC/database.dump" db:/tmp/haqq_restore.dump >/dev/null
docker compose exec -T db sh /tmp/haqq_db.sh restore /tmp/haqq_restore.dump
docker compose exec -T db rm -f /tmp/haqq_restore.dump /tmp/haqq_db.sh
echo "3/4 Restoring documents ..."
docker compose run --rm --no-deps -v "$SRC:/in:ro" --entrypoint sh backend -c "rm -rf /data/storage/* && tar xzf /in/documents.tar.gz -C /data"
echo "4/4 Starting and checking every stored file ..."
docker compose up -d; wait_app
docker compose exec -T backend python -m app.ops_tools check-storage
docker compose exec -T backend python -m app.ops_tools counts
echo "Restore complete."
