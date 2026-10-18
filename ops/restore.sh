#!/usr/bin/env bash
# Restore Future Mirror AI from a backup made by ops/backup.sh.
#   ops/restore.sh                      (lists backups and asks which one)
#   ops/restore.sh fm_20261018_090000   (a full backup folder)
#   ops/restore.sh fm_20261016_190000.dump   (an older database-only backup)
# Restores the database, n8n data if present, and .env if this machine has none yet
# (an existing .env is kept; the backed-up one is saved next to it as .env.from-backup).
source "$(dirname "$0")/_common.sh"
check_docker
src="${1:-}"
if [ -z "$src" ]; then
  ls -d backups/fm_* >/dev/null 2>&1 || fail "No backups found in the backups folder. Run ops/backup.sh first."
  echo "Available backups, newest first:"
  ls -1d backups/fm_* | sort -r | xargs -n1 basename
  echo
  read -r -p "Type the backup name to restore: " src
fi
[ -e "$src" ] || { [ -e "backups/$src" ] && src="backups/$src"; } || true
[ -e "$src" ] || fail "Backup not found: $src"
if [ -d "$src" ]; then dump="$src/database.dump"; else dump="$src"; fi
[ -f "$dump" ] || fail "No database.dump in $src"
echo
[ -f "$src/manifest.txt" ] && grep -E '^(Created|Code version|Verification):' "$src/manifest.txt"
echo "WARNING: this replaces ALL current data with the contents of:"
echo "  $src"
echo "A safety backup of the current data is taken first (when the app has data)."
read -r -p "Type YES to continue: " ok
[ "$ok" = "YES" ] || { echo "Cancelled. Nothing was changed."; exit 0; }

# Configuration first: on a new machine the database must start with the backed-up password.
if [ -d "$src" ] && [ -f "$src/env.backup" ]; then
  if [ ! -f .env ]; then cp "$src/env.backup" .env; echo "Restored .env from the backup."
  elif ! cmp -s .env "$src/env.backup"; then cp "$src/env.backup" .env.from-backup
    echo "Kept your current .env; the backed-up one is saved as .env.from-backup (compare them if logins or connectors fail)."
  fi
fi

if docker compose ps --status running --services 2>/dev/null | grep -qx backend; then
  echo "Taking a safety backup of the current data ..."
  "$OPS_DIR/backup.sh"
fi
echo "Stopping the app ..."
docker compose --profile automation stop frontend backend n8n >/dev/null 2>&1 || true
docker compose up -d db
wait_db
echo "Restoring the database ..."
docker compose cp "$OPS_DIR/db/fm_db.sh" db:/tmp/fm_db.sh >/dev/null 2>&1
docker compose cp "$dump" db:/tmp/fm_restore.dump >/dev/null 2>&1
docker compose exec -T db sh /tmp/fm_db.sh restore /tmp/fm_restore.dump \
  || fail "Database restore failed. Restore the safety backup the same way."
docker compose exec -T db rm -f /tmp/fm_restore.dump /tmp/fm_db.sh

if [ -d "$src" ] && [ -f "$src/n8n.tar.gz" ]; then
  echo "Restoring n8n data ..."
  docker volume create future-mirror_n8ndata >/dev/null 2>&1
  docker run --rm -v future-mirror_n8ndata:/data -v "$(cd "$src" && pwd):/in:ro" alpine:3.20 \
    sh -c 'rm -rf /data/* /data/.[!.]* 2>/dev/null; tar xzf /in/n8n.tar.gz -C /data'
fi
echo "Starting the app ..."
docker compose up -d
wait_app
echo "Restore complete."
