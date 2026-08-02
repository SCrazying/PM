#!/usr/bin/env bash
# PM-System 数据库恢复
# 用法：bash restore.sh <备份文件.sql.gz>
set -euo pipefail

DB_NAME="${DB_NAME:-pm_system}"
DB_USER="${DB_USER:-pm}"
BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
  echo "用法: bash restore.sh <备份文件.sql.gz>"
  exit 1
fi

echo "⚠️  即将用 $BACKUP_FILE 覆盖数据库 $DB_NAME，此操作不可逆！"
read -r -p "确认继续？(yes/no): " confirm
[ "$confirm" = "yes" ] || { echo "已取消"; exit 0; }

echo "==> 停止后端"
systemctl stop pm-system 2>/dev/null || true

echo "==> 重建数据库 $DB_NAME"
sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DB_NAME;"
sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"

echo "==> 导入备份"
gunzip -c "$BACKUP_FILE" | psql -U "$DB_USER" "$DB_NAME"

echo "==> 启动后端"
systemctl start pm-system 2>/dev/null || true

echo "✅ 恢复完成"
