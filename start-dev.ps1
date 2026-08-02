# PM-System 开发环境一键启动（PowerShell）
# 用法：右键“使用 PowerShell 运行”，或执行
#   powershell -ExecutionPolicy Bypass -File .\start-dev.ps1
#
# 说明：
#   默认使用系统 Python（已验证可用）。如需用 venv，先手动创建并装依赖：
#     python -m venv backend\venv ; backend\venv\Scripts\pip install -r backend\requirements-dev.txt
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Set-Location -Path $PSScriptRoot
$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { 8001 }

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  PM-System 开发环境一键启动" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# ---------- 选择 Python（优先 venv，回退系统）----------
$venvPython = Join-Path $PSScriptRoot "backend\venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
    $pySrc = "venv"
} else {
    $python = "python"
    $pySrc = "系统"
}
Write-Host "[环境] 使用$pySrc Python：$python" -ForegroundColor Yellow

# ---------- 校验依赖 ----------
Write-Host "[检查] 后端依赖..." -ForegroundColor Yellow
& $python -c "import fastapi, sqlalchemy, alembic, uvicorn, psycopg2, jwt, bcrypt" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[初始化] 安装后端依赖（首次较慢）..." -ForegroundColor Yellow
    & $python -m pip install -r backend\requirements-dev.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 依赖安装失败，请检查网络或手动执行：$python -m pip install -r backend\requirements-dev.txt" -ForegroundColor Red
        Read-Host "按回车退出"
        exit 1
    }
}

# ---------- 环境变量文件 ----------
if (-not (Test-Path "backend\.env")) {
    Write-Host "[初始化] 生成后端 .env（请按需修改数据库/JWT 配置）" -ForegroundColor Yellow
    Copy-Item backend\.env.example backend\.env
}

# ---------- 启动后端 ----------
Write-Host "[启动] 后端 http://127.0.0.1:$BackendPort （自动执行数据库迁移）" -ForegroundColor Green

# 迁移用 alembic 命令（python -m alembic 不可用）。优先 venv，其次 PATH 中的 alembic。
$alembicExe = Join-Path $PSScriptRoot "backend\venv\Scripts\alembic.exe"
if (-not (Test-Path $alembicExe)) {
    $found = Get-Command alembic -ErrorAction SilentlyContinue
    if ($found) { $alembicExe = $found.Source } else { $alembicExe = "" }
}

if ($alembicExe -ne "") {
    $migrate = "`"$alembicExe`" upgrade head"
} else {
    Write-Host "[警告] 未找到 alembic 命令，跳过迁移（如未建表请先执行 alembic upgrade head）" -ForegroundColor Yellow
    $migrate = "echo skip-migrate"
}

$backendCmd = "cd /d `"$PSScriptRoot\backend`" && $migrate && `"$python`" -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort --reload"
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $backendCmd -WindowStyle Normal

# ---------- 启动前端 ----------
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "[初始化] 安装前端依赖..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
}

Write-Host "[启动] 前端 http://localhost:5173" -ForegroundColor Green
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$PSScriptRoot\frontend`" && npm run dev" -WindowStyle Normal

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  后端 API:  http://127.0.0.1:$BackendPort/docs"
Write-Host "  前端页面:  http://localhost:5173"
Write-Host "  默认账号:  admin / admin123"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "两个服务已在新窗口中启动，关闭对应窗口即停止。" -ForegroundColor Yellow
Read-Host "按回车键退出（不影响已启动的服务）"
