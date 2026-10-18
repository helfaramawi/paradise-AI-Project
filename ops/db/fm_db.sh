#!/bin/sh
# Database steps for backup / verify / restore. Runs INSIDE the db container (copied in by the
# ops scripts), so Windows and macOS/Linux share exactly the same logic.
#   sh /tmp/fm_db.sh backup  /tmp/fm_backup.dump   # live row counts + pg_dump (custom format)
#   sh /tmp/fm_db.sh verify  /tmp/fm_backup.dump   # restore into a scratch DB, compare, drop it
#   sh /tmp/fm_db.sh restore /tmp/fm_restore.dump  # replace the application database, re-apply password
set -eu
export PGOPTIONS="-c client_min_messages=warning"
U="$POSTGRES_USER"
D="$POSTGRES_DB"
SCRATCH="fm_verify_scratch"

counts() {  # "<table> <rows>" for every table in the public schema, sorted by name
  psql -U "$U" -d "$1" -At -F ' ' -c "
    select table_name,
           (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from public.%I', table_name),
                                                false, true, '')))[1]::text
    from information_schema.tables
    where table_schema = 'public' and table_type = 'BASE TABLE'
    order by 1"
}

case "${1:-}" in
  backup)
    counts "$D" > /tmp/fm_live_counts.txt
    pg_dump -U "$U" -d "$D" -Fc -f "$2"
    ;;
  verify)
    dropdb -U "$U" --if-exists --force "$SCRATCH"
    createdb -U "$U" "$SCRATCH"
    if ! pg_restore -U "$U" -d "$SCRATCH" --no-owner --exit-on-error "$2" > /tmp/fm_verify.log 2>&1; then
      dropdb -U "$U" --if-exists --force "$SCRATCH"
      echo "VERIFY FAILED: the backup could not be restored:"
      tail -5 /tmp/fm_verify.log
      exit 1
    fi
    counts "$SCRATCH" > /tmp/fm_restored_counts.txt
    dropdb -U "$U" --force "$SCRATCH"
    tables=$(wc -l < /tmp/fm_restored_counts.txt | tr -d ' ')
    rows=$(awk '{s += $2} END {print s + 0}' /tmp/fm_restored_counts.txt)
    if [ "$tables" -eq 0 ]; then
      echo "VERIFY FAILED: the restored copy contains no tables"
      exit 1
    fi
    if cmp -s /tmp/fm_live_counts.txt /tmp/fm_restored_counts.txt; then
      echo "VERIFIED: test restore OK - $tables tables, $rows rows, every table matches the live database"
    else
      echo "VERIFIED: test restore OK - $tables tables, $rows rows (some rows were added while the backup ran; the backup is a consistent snapshot)"
    fi
    ;;
  restore)
    dropdb -U "$U" --if-exists --force "$D"
    createdb -U "$U" "$D"
    pg_restore -U "$U" -d "$D" --no-owner --exit-on-error "$2"
    # Role passwords are not part of a dump: re-apply the one from .env so the app can log in
    # (matters on a new machine whose database was first started with a different password).
    echo "alter role current_user password :'pw';" | psql -U "$U" -d "$D" -q -v ON_ERROR_STOP=1 -v pw="$POSTGRES_PASSWORD"
    ;;
  *)
    echo "usage: fm_db.sh backup|verify|restore <dumpfile>" >&2
    exit 2
    ;;
esac
