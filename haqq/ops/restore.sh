#!/usr/bin/env sh
# Restore HAQQ from a backup directory produced by ops/backup.sh. DESTRUCTIVE: replaces current data.
set -eu
DIR=${1:?usage: ops/restore.sh <backup-dir>}
(cd "$DIR" && sha256sum -c SHA256SUMS)
docker compose exec -T db pg_restore -U haqq -d haqq --clean --if-exists < "$DIR/haqq.dump"
docker compose run --rm -v "$(cd "$DIR" && pwd)":/backup --entrypoint sh backend -c "rm -rf /data/storage/* && tar xzf /backup/storage.tgz -C /data"
echo "Restore complete"
