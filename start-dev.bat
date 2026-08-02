@echo off
chcp 65001 >nul
title PM-System 一键启动
cd /d %~dp0

echo ==========================================
echo   PM-System 开发环境一键启动
echo ==========================================

REM 使用系统 Python（已验证可用）。检查后端依赖：
python -c "import fastapi, sqlalchemy, alembic, uvicorn" 2>nul
if errorlevel 1 (
    echo [初始化] 安装后端依赖（首次较慢）...
    python -m pip install -r backend\requirements-dev.txt
)

if not exist backend\.env (
    echo [初始化] 生成后端 .env（请按需修改）
    copy backend\.env.example backend\.env >nul
)

echo [启动] 后端 http://127.0.0.1:8001 （自动执行数据库迁移）
start "PM-Backend" cmd /k "cd /d %~dp0backend && alembic upgrade head && python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload"

if not exist frontend\node_modules (
    echo [初始化] 安装前端依赖...
    cd frontend
    call npm install
    cd ..
)

echo [启动] 前端 http://localhost:5173
start "PM-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ==========================================
echo   后端 API:  http://127.0.0.1:8001/docs
echo   前端页面:  http://localhost:5173
echo   默认账号:  admin / admin123
echo ==========================================
echo.
echo 两个服务已在新窗口中启动，关闭对应窗口即停止。
pause
