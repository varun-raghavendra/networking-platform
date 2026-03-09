#!/bin/sh
# Run database backup
export PGHOST=postgres
export PGUSER=user
export PGPASSWORD=password
export PGDATABASE=networking
/scripts/backup_db.sh
