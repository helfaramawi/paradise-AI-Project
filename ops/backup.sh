#!/usr/bin/env bash
# Full, verified backup of Future Mirror AI into backups/fm_YYYYMMDD_HHMMSS/:
#   database.dump  all application data (PostgreSQL custom-format dump)
#   env.backup     the .env file (database password, connector secrets) - keep backups private
#   n8n.tar.gz     n8n workflows and settings (only if the automation profile was ever used)
#   project.tar.gz the project folder: code and git history, local changes, docs, demo videos, music
#                  (not node_modules or older backups - those are rebuilt or already kept)
#   manifest.txt   time, code version, verification result, row counts, SHA-256 checksums
# Every backup is test-restored into a scratch database and compared with the live data.
# Options (environment or .env): FM_BACKUP_KEEP=30 (newest backups kept), FM_BACKUP_COPY_TO=/path (second copy),
# FM_BACKUP_FILES=0 (leave out the project folder).
source "$(dirname "$0")/_common.sh"
check_docker
envval() { [ -f .env ] && grep -E "^$1=" .env | tail -1 | cut -d= -f2- | tr -d '\r' || true; }
KEEP="${FM_BACKUP_KEEP:-$(envval FM_BACKUP_KEEP)}"; KEEP="${KEEP:-30}"
case "$KEEP" in ""|*[!0-9]*|0) KEEP=30 ;; esac
COPY_TO="${FM_BACKUP_COPY_TO:-$(envval FM_BACKUP_COPY_TO)}"
FILES="${FM_BACKUP_FILES:-$(envval FM_BACKUP_FILES)}"

ts=$(date +%Y%m%d_%H%M%S)
dir="backups/fm_$ts"
mkdir -p "$dir"
# A backup that did not finish (or failed verification) is renamed so it is never mistaken for a good one.
trap '[ -n "${complete:-}" ] || { [ -d "$dir" ] && mv "$dir" "backups/failed_fm_$ts" && echo "Incomplete backup moved to backups/failed_fm_$ts"; }' EXIT
docker compose up -d db
wait_db
docker compose cp "$OPS_DIR/db/fm_db.sh" db:/tmp/fm_db.sh >/dev/null 2>&1

echo "1/5 Backing up the database ..."
docker compose exec -T db sh /tmp/fm_db.sh backup /tmp/fm_backup.dump
docker compose cp db:/tmp/fm_backup.dump "$dir/database.dump" >/dev/null 2>&1

echo "2/5 Verifying the backup by restoring it into a scratch database ..."
verdict=$(docker compose exec -T db sh /tmp/fm_db.sh verify /tmp/fm_backup.dump) || { echo "$verdict"; fail "Backup verification failed - the backup in $dir is NOT usable."; }
echo "    $verdict"
counts=$(docker compose exec -T db cat /tmp/fm_restored_counts.txt)
docker compose exec -T db rm -f /tmp/fm_backup.dump /tmp/fm_db.sh /tmp/fm_live_counts.txt /tmp/fm_restored_counts.txt /tmp/fm_verify.log

echo "3/5 Saving configuration and automation data ..."
if [ -f .env ]; then cp .env "$dir/env.backup"; echo "    .env saved"; else echo "    no .env file (defaults in use)"; fi
if docker volume inspect future-mirror_n8ndata >/dev/null 2>&1; then
  docker run --rm -v future-mirror_n8ndata:/data:ro -v "$(pwd)/$dir:/out" alpine:3.20 tar czf /out/n8n.tar.gz -C /data .
  echo "    n8n data saved"
else
  echo "    n8n not used (nothing to save)"
fi

echo "4/5 Saving the project folder (code, docs, videos) ..."
files_note="not included (FM_BACKUP_FILES=0)"
if [ "$FILES" != "0" ]; then
  docker run --rm -v "$(pwd):/src:ro" -v "$(pwd)/$dir:/out" alpine:3.20 sh -c '
    cd /src && tar czf /out/project.tar.gz --exclude=./backups --exclude=node_modules --exclude=__pycache__ \
      --exclude=./.venv --exclude=./frontend/dist --exclude=.pytest_cache --exclude=.ruff_cache \
      --exclude=./frontend/test-results --exclude=./frontend/playwright-report . &&
    tar tzf /out/project.tar.gz | grep -vc "/$"' > "$dir/files.count"
  files_note="$(cat "$dir/files.count") files, archive checked"; rm -f "$dir/files.count"
  echo "    $files_note"
else
  echo "    $files_note"
fi

echo "5/5 Writing the manifest ..."
{
  echo "Future Mirror AI backup"
  echo "Created:      $(date '+%Y-%m-%d %H:%M:%S')"
  echo "Code version: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "Verification: $verdict"
  echo "Project:      $files_note"
  echo
  echo "Files (SHA-256):"
  (cd "$dir" && for f in database.dump env.backup n8n.tar.gz project.tar.gz; do
    if [ -f "$f" ]; then printf '  %-14s %10s bytes  %s\n' "$f" "$(wc -c < "$f" | tr -d ' ')" "$( (sha256sum "$f" 2>/dev/null || shasum -a 256 "$f") | cut -d' ' -f1)"; fi
  done)
  echo
  echo "Rows per table in the verified copy:"
  echo "$counts" | awk '{printf "  %-32s %s\n", $1, $2}'
  echo
  echo "Restore with: ops/restore.sh fm_$ts   (Windows: ops\\restore.bat fm_$ts)"
  echo "Project folder lost? Unpack project.tar.gz into a new folder (tar -xzf project.tar.gz), copy this"
  echo "backup folder into its backups folder, then run the restore command above from there."
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
