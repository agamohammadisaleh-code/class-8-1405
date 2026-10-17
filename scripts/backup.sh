#!/usr/bin/env bash
# پشتیبان‌گیری پایگاه داده
# SQLite:   ./scripts/backup.sh sqlite server/tutor8.db
# Postgres: ./scripts/backup.sh pg
set -e
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
if [ "$1" = "pg" ]; then
  pg_dump "${DATABASE_URL:-postgresql://tutor@localhost:5432/tutor8}" > "backups/tutor8-$STAMP.sql"
else
  cp "${2:-server/tutor8.db}" "backups/tutor8-$STAMP.db"
fi
echo "پشتیبان ساخته شد: backups/tutor8-$STAMP"
