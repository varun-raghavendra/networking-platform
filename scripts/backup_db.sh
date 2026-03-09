#!/bin/sh
# Backup PostgreSQL database - run from backup container
# Backups saved to /backups with timestamp

set -e
BACKUP_DIR="${BACKUP_DIR:-/backups}"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/networking_${TIMESTAMP}.sql.gz"

export PGHOST="${PGHOST:-postgres}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-user}"
export PGPASSWORD="${PGPASSWORD:-password}"
export PGDATABASE="${PGDATABASE:-networking}"

echo "[$(date '+%Y-%m-%dT%H:%M:%S')] Starting backup to $FILE"
pg_dump "$PGDATABASE" | gzip > "$FILE"
echo "[$(date '+%Y-%m-%dT%H:%M:%S')] Backup complete: $(ls -lh "$FILE" | awk '{print $5}')"

# Keep last 28 backups (7 days at 6h interval)
ls -t "$BACKUP_DIR"/networking_*.sql.gz 2>/dev/null | tail -n +29 | while read f; do rm -f "$f"; done
