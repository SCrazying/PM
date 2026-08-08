# PM-System 生产一键部署（Windows · 内网免装 Python）
# 用法：powershell -ExecutionPolicy Bypass -File deploy_prod.ps1
# 功能：初始化数据库 → 生成配置 → 便携 Python 建表/种子 → NSSM 注册 Windows 服务 → 启动（开机自启）
# 前置：内网已安装 PostgreSQL 14+（需 postgres 超级用户密码）；本包已内置便携 Python/前端 dist/NSSM
param(
    [string]$PgPassword = "postgres",    # PostgreSQL 超级用户密码（内网默认 postgres）
    [int]$Port = 8001,                  # 后端端口（默认 8001）
    [string]$ServiceName = "pm-system", # Windows 服务名
    [string]$AppUser = "pm",
    [string]$AppPassword = "pm123",  # 数据库应用密码（内网统一 postgres）
    [string]$DbName = "pm_system",
    [string]$JwtSecret = ""             # 不填则自动生成随机密钥
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 检查管理员权限（NSSM 注册 Windows 服务需要）
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[警告] 当前非管理员权限，注册 Windows 服务可能失败。建议：右键 PowerShell → 以管理员身份运行，再执行本脚本。" -ForegroundColor Yellow
}

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)  # deploy\scripts\.. → pm-prod
$Python = Join-Path $Root "runtime\python\python.exe"
$BackendDir = Join-Path $Root "backend"
$Nssm = Join-Path $Root "deploy\bin\nssm.exe"
$InitDb = Join-Path $PSScriptRoot "init_db.ps1"

if (-not (Test-Path $Python) -or -not (Test-Path $Nssm)) {
    Write-Host ""
    Write-Host "[错误] 部署包结构不完整：" -ForegroundColor Red
    Write-Host "  便携 Python: $Python  -> $([bool](Test-Path $Python))" -ForegroundColor Yellow
    Write-Host "  NSSM:         $Nssm    -> $([bool](Test-Path $Nssm))" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "请确认使用方式：" -ForegroundColor Cyan
    Write-Host "  1) 解压完整 pm-prod.zip（不要只拷单个脚本）" -ForegroundColor Cyan
    Write-Host "  2) 从 pm-prod\deploy\scripts\deploy_prod.ps1 运行本脚本（脚本必须位于部署包内的 deploy\scripts 目录，不能单独拷出）" -ForegroundColor Cyan
    Write-Host "  3) 部署包根目录下应含：runtime\python、backend、frontend\dist、db、deploy\bin\nssm.exe" -ForegroundColor Cyan
    throw "部署包结构不完整（请解压完整 pm-prod.zip 后在包内运行）"
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  PM-System 生产一键部署" -ForegroundColor Cyan
Write-Host "  部署目录: $Root" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# ---------- 0. 创建数据目录（日志/附件/备份；NSSM 服务写日志依赖） ----------
New-Item -ItemType Directory -Force -Path "$Root\data\logs", "$Root\data\uploads", "$Root\data\backups" | Out-Null

# ---------- 0.1 生成 .env ----------
$envFile = Join-Path $BackendDir ".env"
if (-not (Test-Path $envFile)) {
    if (Test-Path (Join-Path $BackendDir ".env.example")) { Copy-Item (Join-Path $BackendDir ".env.example") $envFile }
}
if (-not $JwtSecret) {
    $bytes = New-Object byte[] 48; (New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($bytes)
    $JwtSecret = [Convert]::ToBase64String($bytes)
}
$content = ""
if (Test-Path $envFile) { $content = Get-Content $envFile -Raw }
# 覆盖关键项
$lines = @()
foreach ($line in ($content -split "`n")) {
    $k = ($line -split "=")[0].Trim()
    if ($k -in @("APP_ENV","DATABASE_URL","JWT_SECRET","AI_BASE_URL","AI_API_KEY","CORS_ORIGINS","UPLOAD_DIR","BACKUP_DIR")) { continue }
    if ($line.Trim()) { $lines += $line.TrimEnd("`r") }
}
$lines += "APP_ENV=prod"
$lines += "PM_SERVE_FRONTEND=1"
$lines += "DATABASE_URL=postgresql+psycopg2://$AppUser`:$AppPassword@127.0.0.1:5432/$DbName"
$lines += "JWT_SECRET=$JwtSecret"
$lines += "AI_BASE_URL="
$lines += "AI_API_KEY="
$lines += "CORS_ORIGINS="
$lines += "UPLOAD_DIR=$Root\data\uploads"
$lines += "BACKUP_DIR=$Root\data\backups"
Set-Content -Path $envFile -Value ($lines -join "`r`n") -Encoding UTF8
Write-Host "[配置] 已生成 $envFile（JWT_SECRET 已随机）" -ForegroundColor Green

# ---------- 1. 数据库初始化（复用 init_db.ps1，幂等） ----------
Write-Host "[数据库] 检查/初始化 PostgreSQL（需超级用户密码）..." -ForegroundColor Yellow
& powershell -NoProfile -ExecutionPolicy Bypass -File $InitDb `
    -PgPassword $PgPassword -AppUser $AppUser -AppPassword $AppPassword -DbName $DbName `
    -BackendDir $BackendDir -Python $Python
if ($LASTEXITCODE -ne 0) { throw "数据库初始化失败" }

# ---------- 2. 用便携 Python 建表 + 种子（init_db 已做，这里兜底幂等） ----------
Write-Host "[数据库] 便携 Python 迁移 + 种子 ..." -ForegroundColor Yellow
Push-Location $BackendDir
try {
    & $Python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "迁移失败" }
    # 便携 Python 的 embeddable 特性：-m 不会把当前目录加入 sys.path，须用 -c + sys.path.insert 导入 app
    $PyDir = $BackendDir.Replace('\', '/')
    & $Python -c "import sys; sys.path.insert(0, r'$PyDir'); from app.seed import run; sys.exit(run())"
    if ($LASTEXITCODE -ne 0) { throw "种子数据写入失败" }
} finally { Pop-Location }

# ---------- 3. NSSM 注册 Windows 服务 ----------
Write-Host "[服务] 注册 Windows 服务 $ServiceName ..." -ForegroundColor Yellow

# 幂等：若已存在同名服务，先停止并移除（服务不存在时静默跳过，避免 nssm stop 报错）
$svcExists = $null -ne (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)
if ($svcExists) {
    & $Nssm stop $ServiceName 2>$null | Out-Null
    Start-Sleep -Seconds 1
    & $Nssm remove $ServiceName confirm 2>$null | Out-Null
    Start-Sleep -Seconds 1
}

# 安装服务（python 路径加引号防空格；NSSM 装服务需管理员权限）
& $Nssm install $ServiceName "`"$Python`""
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] NSSM 安装服务失败。请以【管理员身份】运行 PowerShell 后重试本脚本。" -ForegroundColor Red
    throw "NSSM 安装服务失败（可能需要管理员权限）"
}
& $Nssm set $ServiceName AppDirectory $BackendDir
& $Nssm set $ServiceName AppParameters "-m uvicorn app.main:app --host 0.0.0.0 --port $Port"
& $Nssm set $ServiceName DisplayName "PM-System 项目管理系统"
& $Nssm set $ServiceName Description "内网项目管理系统（FastAPI 后端 + 前端静态伺服）"
& $Nssm set $ServiceName Start SERVICE_AUTO_START
& $Nssm set $ServiceName AppStdout "$Root\data\logs\backend.log"
& $Nssm set $ServiceName AppStderr "$Root\data\logs\backend.err"
& $Nssm set $ServiceName AppRotateFiles 1
& $Nssm set $ServiceName AppRotateBytes 10485760
& $Nssm set $ServiceName AppExit Default Restart
& $Nssm set $ServiceName AppRestartDelay 5000

# ---------- 4. 启动服务 ----------
Write-Host "[服务] 启动 $ServiceName ..." -ForegroundColor Yellow
& $Nssm start $ServiceName
Start-Sleep -Seconds 6
$health = try { (Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 8).StatusCode } catch { 0 }

# 健康检查失败时，读取后端日志帮助定位
if ($health -ne 200) {
    $errLog = Join-Path $Root "data\logs\backend.err"
    $outLog = Join-Path $Root "data\logs\backend.log"
    Write-Host ""
    Write-Host "[警告] 服务已注册但健康检查未通过（HTTP $health）" -ForegroundColor Yellow
    Write-Host "服务状态:" -ForegroundColor Cyan
    sc.exe query $ServiceName 2>&1 | Select-String "STATE" | ForEach-Object { $_.Line.Trim() }
    Write-Host ""
    Write-Host "--- data\logs\backend.err（最后30行）---" -ForegroundColor Cyan
    if (Test-Path $errLog) { Get-Content $errLog -Tail 30 } else { Write-Host "（无 err 日志）" -ForegroundColor DarkGray }
    Write-Host "--- data\logs\backend.log（最后20行）---" -ForegroundColor Cyan
    if (Test-Path $outLog) { Get-Content $outLog -Tail 20 } else { Write-Host "（无 log 日志）" -ForegroundColor DarkGray }
    Write-Host ""
    Write-Host "手动验证后端（前台运行看报错）：" -ForegroundColor Yellow
    Write-Host "  cd `"$BackendDir`"" -ForegroundColor Yellow
    Write-Host "  `"$Python`" -m uvicorn app.main:app --host 0.0.0.0 --port $Port" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "[OK] 部署完成"
Write-Host "   服务名:   $ServiceName（开机自启，重启后无需手动启动）"
Write-Host "   访问地址: http://<本机IP>:$Port"
Write-Host "   健康检查: $health"
Write-Host "   初始账号: admin / admin123（请登录后修改密码）"
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "管理命令："
Write-Host "   启动/停止:  net start $ServiceName / net stop $ServiceName"
Write-Host "   卸载服务:  powershell -File $PSScriptRoot\uninstall_prod.ps1"
