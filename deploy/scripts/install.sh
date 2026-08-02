#!/usr/bin/env bash
# PM-System 离线/原生部署一键安装（内网无 Docker 场景）
# 用法：sudo bash install.sh
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_HOME="${APP_HOME:-/opt/pm-system}"
APP_USER="${APP_USER:-pm}"
DB_NAME="${DB_NAME:-pm_system}"
DB_USER="${DB_USER:-pm}"
DB_PASSWORD="${DB_PASSWORD:-pm123}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

echo "==> 部署目录: $DEPLOY_DIR"
echo "==> 安装目标: $APP_HOME (用户 $APP_USER)"

# 1. 创建应用用户与目录
id -u "$APP_USER" &>/dev/null || useradd -r -m -d "$APP_HOME" "$APP_USER" || true
mkdir -p "$APP_HOME"/{backend,frontend,data/uploads,data/backups,logs}
cp -r "$DEPLOY_DIR/backend/." "$APP_HOME/backend/"
cp -r "$DEPLOY_DIR/frontend/dist/." "$APP_HOME/frontend/" 2>/dev/null || echo "!! 前端 dist 未找到，请先构建"

# 2. 安装 Python 依赖（离线 wheels）
echo "==> 创建 venv 并离线安装依赖"
python3.11 -m venv "$APP_HOME/venv"
"$APP_HOME/venv/bin/pip" install --upgrade pip
"$APP_HOME/venv/bin/pip" install --no-index --find-links="$APP_HOME/backend/wheels" -r "$APP_HOME/backend/requirements.txt"

# 3. 配置环境变量
if [ ! -f "$APP_HOME/backend/.env" ]; then
  cp "$APP_HOME/backend/.env.example" "$APP_HOME/backend/.env"
  sed -i "s#^DATABASE_URL=.*#DATABASE_URL=postgresql+psycopg2://$DB_USER:$DB_PASSWORD@127.0.0.1:5432/$DB_NAME#" "$APP_HOME/backend/.env"
  sed -i "s#^UPLOAD_DIR=.*#UPLOAD_DIR=$APP_HOME/data/uploads#" "$APP_HOME/backend/.env"
  sed -i "s#^BACKUP_DIR=.*#BACKUP_DIR=$APP_HOME/data/backups#" "$APP_HOME/backend/.env"
  echo "!! 已生成 $APP_HOME/backend/.env，请修改 JWT_SECRET / AI 配置 / 数据库密码"
fi

# 4. 初始化数据库（假定 PostgreSQL 已安装并运行）
echo "==> 初始化数据库与迁移"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
  sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"

cd "$APP_HOME/backend"
"$APP_HOME/venv/bin/alembic" upgrade head
"$APP_HOME/venv/bin/python" -m app.seed

# 5. 配置 systemd 常驻
echo "==> 配置 systemd 服务"
cp "$DEPLOY_DIR/scripts/pm-system.service" /etc/systemd/system/
sed -i "s#{{APP_HOME}}#$APP_HOME#g; s#{{APP_USER}}#$APP_USER#g; s#{{BACKEND_PORT}}#$BACKEND_PORT#g" /etc/systemd/system/pm-system.service
systemctl daemon-reload
systemctl enable --now pm-system

# 6. 权限
chown -R "$APP_USER":"$APP_USER" "$APP_HOME"

echo ""
echo "✅ 安装完成。后端运行于 127.0.0.1:$BACKEND_PORT"
echo "   下一步：配置 Nginx（deploy/nginx/nginx.conf）指向 127.0.0.1:$BACKEND_PORT 并托管 $APP_HOME/frontend"
echo "   健康检查：curl http://127.0.0.1:$BACKEND_PORT/health"
