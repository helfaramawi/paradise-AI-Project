#!/usr/bin/env bash
# Full, VERIFIED HAQQ backup (macOS / Linux). Same contents and checks as backup.bat.
#   ops/backup.sh      -> haqq/backups/haqq_YYYYMMDD_HHMMSS/
# Options (.env or environment): HAQQ_BACKUP_KEEP=30, HAQQ_BACKUP_COPY_TO=/mnt/backups/haqq
set -euo pipefail
cd "$(dirname "$0")/.."; . ops/_common.sh
check_docker
KEEP=${HAQQ_BACKUP_KEEP:-$(env_value HAQQ_BACKUP_KEEP)}; KEEP=${KEEP:-30}
COPY_TO=${HAQQ_BACKUP_COPY_TO:-$(env_value HAQQ_BACKUP_COPY_TO)}
TS=$(date +%Y%m%d_%H%M%S); NAME="haqq_$TS"; DIR="backups/$NAME"
mkdir -p "$DIR"
fail() { echo "[FAILED] $*"; [ -d "$DIR" ] && mv "$DIR" "backups/failed_$NAME" && echo "Incomplete backup moved to backups/failed_$NAME"; exit 1; }
trap 'fail "see the messages above"' ERR
docker compose up -d db >/dev/null; wait_db
docker compose cp ops/db/haqq_db.sh db:/tmp/haqq_db.sh >/dev/null
echo "1/5 Backing up the database ..."
docker compose exec -T db sh /tmp/haqq_db.sh backup /tmp/haqq_backup.dump
docker compose cp db:/tmp/haqq_backup.dump "$DIR/database.dump" >/dev/null
echo "2/5 Verifying the database backup (scratch restore) ..."
DB_VERDICT=$(docker compose exec -T db sh /tmp/haqq_db.sh verify /tmp/haqq_backup.dump) || fail "$DB_VERDICT"
echo "    $DB_VERDICT"
docker compose exec -T db cat /tmp/haqq_restored_counts.txt > "$DIR/counts.txt"
docker compose exec -T db rm -f /tmp/haqq_backup.dump /tmp/haqq_db.sh /tmp/haqq_live_counts.txt /tmp/haqq_restored_counts.txt /tmp/haqq_verify.log
echo "3/5 Backing up documents ..."
ABS=$(cd "$DIR" && pwd)
docker compose run --rm --no-deps --user "$(id -u):$(id -g)" -v "$ABS:/out" --entrypoint sh backend -c "tar czf /out/documents.tar.gz -C /data storage"
echo "4/5 Verifying every stored file against its SHA-256 ..."
DOC_VERDICT=$(docker compose run --rm --no-deps -v "$ABS:/out:ro" backend python -m app.ops_tools verify-archive /out/documents.tar.gz | head -1) || fail "$DOC_VERDICT"
case "$DOC_VERDICT" in VERIFIED*) ;; *) fail "$DOC_VERDICT" ;; esac
echo "    $DOC_VERDICT"
echo "5/5 Configuration and manifest ..."
[ -f .env ] && cp .env "$DIR/env.backup"
{
  echo "HAQQ backup"; echo "Created:      $(date '+%Y-%m-%d %H:%M:%S')"
  echo "Code version: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "Database:     $DB_VERDICT"; echo "Documents:    $DOC_VERDICT"; echo; echo "Files (SHA-256):"
  (cd "$DIR" && for f in database.dump documents.tar.gz env.backup; do [ -f "$f" ] && echo "  $f  $(wc -c < "$f" | tr -d ' ') bytes  $(sha256sum "$f" 2>/dev/null | cut -d' ' -f1 || shasum -a 256 "$f" | cut -d' ' -f1)"; done)
  echo; echo "Rows per table in the verified copy:"; sed 's/^/  /' "$DIR/counts.txt"
  echo; echo "Restore with: ops/restore.sh $NAME   (Windows: ops\\restore.bat $NAME)"
} > "$DIR/manifest.txt"
rm -f "$DIR/counts.txt"
trap - ERR
[ -n "${COPY_TO:-}" ] && { mkdir -p "$COPY_TO" && cp -r "$DIR" "$COPY_TO/" && echo "Second copy: $COPY_TO/$NAME" || echo "WARNING: second copy failed"; }
ls -1d backups/haqq_* 2>/dev/null | sort -r | tail -n +$((KEEP + 1)) | while read -r old; do rm -rf "$old"; echo "Removed old backup: $old"; done
echo "Backup complete and verified: $PWD/$DIR"
