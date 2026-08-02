#!/usr/bin/env bash
# PM-System 开发环境一键启动（Git Bash / Linux）
# 用法：bash start-dev.sh
# 使用系统 Python（已验证可用）
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

BACKEND_PORT="${BACKEND_PORT:-8001}"

echo "=========================================="
echo "  PM-System 开发环境一键启动"
echo "=========================================="

# 检查后端依赖
echo "[检查] 后端依赖..."
if ! python -c "import fastapi, sqlalchemy, alembic, uvicorn" 2>/dev/null; then
  echo "[初始化] 安装后端依赖（首次较慢）..."
  python -m pip install -r backend/requirements-dev.txt
fi

if [ ! -f backend/.env ]; then
  echo "[初始化] 生成后端 .env（请按需修改）"
  cp backend/.env.example backend/.env
fi

echo "[启动] 后端 http://127.0.0.1:$BACKEND_PORT (自动执行迁移)"
(cd backend && alembic upgrade head && python -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload) &
BACK_PID=$!

if [ ! -d frontend/node_modules ]; then
  echo "[初始化] 安装前端依赖..."
  (cd frontend && npm install)
fi

echo "[启动] 前端 http://localhost:5173"
(cd frontend && npm run dev) &
FRONT_PID=$!

echo ""
echo "=========================================="
echo "  后端 API:  http://127.0.0.1:$BACKEND_PORT/docs"
echo "  前端页面:  http://localhost:5173"
echo "  默认账号:  admin / admin123"
echo "=========================================="
echo "按 Ctrl+C 停止全部服务"

trap 'kill $BACK_PID $FRONT_PID 2>/dev/null' INT TERM
wait
