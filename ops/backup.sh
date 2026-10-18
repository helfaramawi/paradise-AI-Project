#!/usr/bin/env bash
# Full, verified backup of Future Mirror AI into backups/fm_YYYYMMDD_HHMMSS/:
#   database.dump  all application data (PostgreSQL custom-format dump)
#   env.backup     the .env file (database password, connector secrets) - keep backups private
#   n8n.tar.gz     n8n workflows and settings (only if the automation profile was ever used)
#   manifest.txt   time, code version, verification result, row counts, SHA-256 checksums
# Every backup is test-restored into a scratch database and compared with the live data.
# Options (environment or .env): FM_BACKUP_KEEP=30 (newest backups kept), FM_BACKUP_COPY_TO=/path (second copy).
source "$(dirname "$0")/_common.sh"
check_docker
envval() { [ -f .env ] && grep -E "^$1=" .env | tail -1 | cut -d= -f2- | tr -d '\r' || true; }
KEEP="${FM_BACKUP_KEEP:-$(envval FM_BACKUP_KEEP)}"; KEEP="${KEEP:-30}"
case "$KEEP" in ""|*[!0-9]*|0) KEEP=30 ;; esac
COPY_TO="${FM_BACKUP_COPY_TO:-$(envval FM_BACKUP_COPY_TO)}"

ts=$(date +%Y%m%d_%H%M%S)
dir="backups/fm_$ts"
mkdir -p "$dir"
# A backup that did not finish (or failed verification) is renamed so it is never mistaken for a good one.
trap '[ -n "${complete:-}" ] || { [ -d "$dir" ] && mv "$dir" "backups/failed_fm_$ts" && echo "Incomplete backup moved to backups/failed_fm_$ts"; }' EXIT
docker compose up -d db
wait_db
docker compose cp "$OPS_DIR/db/fm_db.sh" db:/tmp/fm_db.sh >/dev/null 2>&1

echo "1/4 Backing up the database ..."
docker compose exec -T db sh /tmp/fm_db.sh backup /tmp/fm_backup.dump
docker compose cp db:/tmp/fm_backup.dump "$dir/database.dump" >/dev/null 2>&1

echo "2/4 Verifying the backup by restoring it into a scratch database ..."
verdict=$(docker compose exec -T db sh /tmp/fm_db.sh verify /tmp/fm_backup.dump) || { echo "$verdict"; fail "Backup verification failed - the backup in $dir is NOT usable."; }
echo "    $verdict"
counts=$(docker compose exec -T db cat /tmp/fm_restored_counts.txt)
docker compose exec -T db rm -f /tmp/fm_backup.dump /tmp/fm_db.sh /tmp/fm_live_counts.txt /tmp/fm_restored_counts.txt /tmp/fm_verify.log

echo "3/4 Saving configuration and automation data ..."
if [ -f .env ]; then cp .env "$dir/env.backup"; echo "    .env saved"; else echo "    no .env file (defaults in use)"; fi
if docker volume inspect future-mirror_n8ndata >/dev/null 2>&1; then
  docker run --rm -v future-mirror_n8ndata:/data:ro -v "$(pwd)/$dir:/out" alpine:3.20 tar czf /out/n8n.tar.gz -C /data .
  echo "    n8n data saved"
else
  echo "    n8n not used (nothing to save)"
fi

echo "4/4 Writing the manifest ..."
{
  echo "Future Mirror AI backup"
  echo "Created:      $(date '+%Y-%m-%d %H:%M:%S')"
  echo "Code version: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "Verification: $verdict"
  echo
  echo "Files (SHA-256):"
  (cd "$dir" && for f in database.dump env.backup n8n.tar.gz; do
    if [ -f "$f" ]; then printf '  %-14s %10s bytes  %s\n' "$f" "$(wc -c < "$f" | tr -d ' ')" "$( (sha256sum "$f" 2>/dev/null || shasum -a 256 "$f") | cut -d' ' -f1)"; fi
  done)
  echo
  echo "Rows per table in the verified copy:"
  echo "$counts" | awk '{printf "  %-32s %s\n", $1, $2}'
  echo
  echo "Restore with: ops/restore.sh fm_$ts   (Windows: ops\\restore.bat fm_$ts)"
} > "$dir/manifest.txt"

if [ -n "$COPY_TO" ]; then
  mkdir -p "$COPY_TO" && cp -R "$dir" "$COPY_TO/" && echo "Second copy saved to: $COPY_TO/fm_$ts" \
    || echo "WARNING: could not copy the backup to $COPY_TO (the backup in $dir is fine)"
fi
# Retention: keep the newest $KEEP good backups (bundles and older single-file dumps).
ls -1d backups/fm_* 2>/dev/null | sort -r | tail -n +"$((KEEP + 1))" | while read -r old; do rm -rf "$old"; echo "Removed old backup: $old"; done

complete=1
echo
echo "Backup complete and verified: $(pwd)/$dir"
