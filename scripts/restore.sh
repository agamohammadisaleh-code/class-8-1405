#!/usr/bin/env bash
# بازیابی:  ./scripts/restore.sh backups/tutor8-YYYYMMDD-HHMMSS.db
set -e
cp "$1" server/tutor8.db
echo "بازیابی انجام شد. سرور را دوباره اجرا کنید."
