#!/usr/bin/env bash
# Clear all tables in the networking platform database

set -e

cd "$(dirname "$0")"
docker compose exec -T postgres psql -U user -d networking -c \
  "TRUNCATE companies, contacts, interactions, todos, scheduled_events, audit_log CASCADE;"
echo "All tables cleared."
