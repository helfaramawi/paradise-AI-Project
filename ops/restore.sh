#!/usr/bin/env bash
# Restore the Future Mirror AI database from a backup file.
#   ops/restore.sh                         (lists backups and asks which one)
#   ops/restore.sh fm_20261016_190000.dump
source "$(dirname "$0")/_common.sh"
check_docker
file="${1:-}"
if [ -z "$file" ]; then
  ls backups/*.dump >/dev/null 2>&1 || fail "No backups found in the backups folder. Run ops/backup.sh first."
  echo "Available backups, newest first:"
  ls -1t backups/*.dump | xargs -n1 basename
  echo
  read -r -p "Type the backup file name to restore: " file
fi
[ -f "$file" ] || { [ -f "backups/$file" ] && file="backups/$file"; } || true
[ -f "$file" ] || fail "File not found: $file"
echo
echo "WARNING: this replaces ALL current data with the contents of:"
echo "  $file"
echo "A safety backup of the current data is taken first."
read -r -p "Type YES to continue: " ok
[ "$ok" = "YES" ] || { echo "Cancelled. Nothing was changed."; exit 0; }
echo "Taking a safety backup of the current data ..."
"$OPS_DIR/backup.sh"
echo "Stopping the app ..."
docker compose stop frontend backend
docker compose up -d db
wait_db
echo "Restoring ..."
docker compose cp "$file" db:/tmp/fm_restore.dump
docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB" && pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error /tmp/fm_restore.dump; rc=$?; rm -f /tmp/fm_restore.dump; exit $rc' \
  || fail "Restore failed. Restore the safety backup the same way."
echo "Starting the app ..."
docker compose up -d
wait_app
echo "Restore complete."
