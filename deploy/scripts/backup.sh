#!/usr/bin/env bash
# PM-System 数据库备份（pg_dump）+ 附件归档
# 用法：bash backup.sh  （建议 crontab 每日执行：0 2 * * *）
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/pm-system}"
BACKUP_DIR="${BACKUP_DIR:-$APP_HOME/data/backups}"
DB_NAME="${DB_NAME:-pm_system}"
DB_USER="${DB_USER:-pm}"
KEEP="${KEEP:-14}"
TS="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

echo "==> 备份数据库 $DB_NAME → $BACKUP_DIR/db_$TS.sql.gz"
pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/db_$TS.sql.gz"

echo "==> 归档附件 → $BACKUP_DIR/uploads_$TS.tar.gz"
[ -d "$APP_HOME/data/uploads" ] && tar -czf "$BACKUP_DIR/uploads_$TS.tar.gz" -C "$APP_HOME/data" uploads || true

# 清理过期备份（保留最近 KEEP 份）
ls -1t "$BACKUP_DIR"/db_*.sql.gz 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f
ls -1t "$BACKUP_DIR"/uploads_*.tar.gz 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f

echo "✅ 备份完成（保留最近 $KEEP 份）"
