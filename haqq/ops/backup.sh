#!/usr/bin/env sh
# Backup HAQQ: PostgreSQL dump + document object storage. Usage: ops/backup.sh [target-dir]
set -eu
DIR=${1:-./backups/$(date +%Y%m%d-%H%M%S)}
mkdir -p "$DIR"
docker compose exec -T db pg_dump -U haqq -d haqq -Fc > "$DIR/haqq.dump"
docker compose run --rm -v "$(cd "$DIR" && pwd)":/backup --entrypoint sh backend -c "tar czf /backup/storage.tgz -C /data storage"
sha256sum "$DIR"/* > "$DIR/SHA256SUMS"
echo "Backup written to $DIR"
