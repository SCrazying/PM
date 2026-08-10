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
    [string]$JwtSecret = "",            # 不填则自动生成随机密钥
    [int]$MinioPort = 9000,             # MinIO 对象存储 S3 端口（项目资料）
    [int]$MinioConsolePort = 9001,      # MinIO 控制台端口
    [switch]$NoMinio                    # 跳过 MinIO 服务（用本地磁盘存资料）
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

# 包装 nssm 调用：$ErrorActionPreference=Stop 会把 nssm 的 stderr（STOP:/START: 状态行）当 NativeCommandError 中断脚本。
# 这里临时切 Continue + 丢弃 stderr，失败与否通过 $LASTEXITCODE 判断。
function Invoke-Nssm {
    param([Parameter(ValueFromRemainingArguments = $true)][object[]]$NssmArgs)
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Nssm @NssmArgs 2>$null
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldEap
    }
}

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
# JWT_SECRET：优先复用 .env 已有值，保持稳定（否则每次部署换 secret，已登录用户 token 全部失效 → 登录后立即"已过期"）
$existingSecret = ""
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    if ($envContent -match "(?m)^JWT_SECRET=(\S+)") { $existingSecret = $matches[1].Trim() }
}
if ($JwtSecret) {
    $secretToUse = $JwtSecret
} elseif ($existingSecret -and $existingSecret -ne "change-me-in-prod") {
    $secretToUse = $existingSecret
} else {
    $bytes = New-Object byte[] 48; (New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($bytes)
    $secretToUse = [Convert]::ToBase64String($bytes)
}
$content = ""
if (Test-Path $envFile) { $content = Get-Content $envFile -Raw }
# 覆盖关键项
$lines = @()
foreach ($line in ($content -split "`n")) {
    $k = ($line -split "=")[0].Trim()
    if ($k -in @("APP_ENV","DATABASE_URL","JWT_SECRET","AI_BASE_URL","AI_API_KEY","CORS_ORIGINS","UPLOAD_DIR","BACKUP_DIR","STORAGE_BACKEND","MINIO_ENDPOINT","MINIO_ACCESS_KEY","MINIO_SECRET_KEY","MINIO_BUCKET","MINIO_SECURE")) { continue }
    if ($line.Trim()) { $lines += $line.TrimEnd("`r") }
}
$lines += "APP_ENV=prod"
$lines += "PM_SERVE_FRONTEND=1"
$lines += "DATABASE_URL=postgresql+psycopg2://$AppUser`:$AppPassword@127.0.0.1:5432/$DbName"
$lines += "JWT_SECRET=$secretToUse"
$lines += "AI_BASE_URL="
$lines += "AI_API_KEY="
$lines += "CORS_ORIGINS="
$lines += "UPLOAD_DIR=$Root\data\uploads"
$lines += "BACKUP_DIR=$Root\data\backups"
# MinIO 对象存储（项目资料）：minio.exe 存在且未 -NoMinio 时启用
# 凭据统一用 MinIO 默认 minioadmin/minioadmin（与既有数据目录匹配；该目录凭据首次初始化即固化）
$MinioExe = Join-Path $Root "runtime\minio\minio.exe"
$useMinio = (-not $NoMinio) -and (Test-Path $MinioExe)
if ($useMinio) {
    $lines += "STORAGE_BACKEND=minio"
    $lines += "MINIO_ENDPOINT=127.0.0.1:$MinioPort"
    $lines += "MINIO_ACCESS_KEY=minioadmin"
    $lines += "MINIO_SECRET_KEY=minioadmin"
    $lines += "MINIO_BUCKET=pm-system"
    $lines += "MINIO_SECURE=false"
} else {
    $lines += "STORAGE_BACKEND=local"
}
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
    # cmd /c 静默：Stop 模式下 PowerShell 会把 nssm 的 stderr 当 NativeCommandError，用 cmd 层丢弃
    cmd /c "`"$Nssm`" stop $ServiceName 2>nul"
    Start-Sleep -Seconds 1
    cmd /c "`"$Nssm`" remove $ServiceName confirm 2>nul"
    Start-Sleep -Seconds 1
}

# 安装服务（python 路径加引号防空格；NSSM 装服务需管理员权限）
Invoke-Nssm install $ServiceName "`"$Python`""
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] NSSM 安装服务失败。请以【管理员身份】运行 PowerShell 后重试本脚本。" -ForegroundColor Red
    throw "NSSM 安装服务失败（可能需要管理员权限）"
}
Invoke-Nssm set $ServiceName AppDirectory $BackendDir
Invoke-Nssm set $ServiceName AppParameters "-m uvicorn app.main:app --host 0.0.0.0 --port $Port"
Invoke-Nssm set $ServiceName DisplayName "PM-System 项目管理系统"
Invoke-Nssm set $ServiceName Description "内网项目管理系统（FastAPI 后端 + 前端静态伺服）"
Invoke-Nssm set $ServiceName Start SERVICE_AUTO_START
Invoke-Nssm set $ServiceName AppStdout "$Root\data\logs\backend.log"
Invoke-Nssm set $ServiceName AppStderr "$Root\data\logs\backend.err"
Invoke-Nssm set $ServiceName AppRotateFiles 1
Invoke-Nssm set $ServiceName AppRotateBytes 10485760
Invoke-Nssm set $ServiceName AppExit Default Restart
Invoke-Nssm set $ServiceName AppRestartDelay 5000

# ---------- 3.6 MinIO 对象存储服务（项目资料） ----------
$MinioService = "$ServiceName-minio"
if ($useMinio) {
    Write-Host "[MinIO] 注册对象存储服务 $MinioService ..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path "$Root\data\minio" | Out-Null
    $mSvc = $null -ne (Get-Service -Name $MinioService -ErrorAction SilentlyContinue)
    if ($mSvc) {
        cmd /c "`"$Nssm`" stop $MinioService 2>nul"
        Start-Sleep -Seconds 1
        cmd /c "`"$Nssm`" remove $MinioService confirm 2>nul"
        Start-Sleep -Seconds 1
    }
    # minio.exe 直连 + 清空 NSSM 环境变量（凭据用 MinIO 默认 minioadmin/minioadmin，与 data\minio 初始化一致）
    # 不能用 AppEnvironmentExtra 传 MINIO_ROOT_USER=pm——NSSM 在本环境会把 pm 传进 minio 导致其崩溃
    Invoke-Nssm install $MinioService "`"$MinioExe`""
    Invoke-Nssm set $MinioService AppDirectory $Root
    Invoke-Nssm set $MinioService AppParameters "server `"$Root\data\minio`" --address :$MinioPort --console-address :$MinioConsolePort"
    Invoke-Nssm set $MinioService AppEnvironmentExtra "" 2>&1 | Out-Null
    Invoke-Nssm set $MinioService DisplayName "PM-System MinIO 对象存储"
    Invoke-Nssm set $MinioService Description "PM-System 项目资料对象存储（S3 兼容）"
    Invoke-Nssm set $MinioService Start SERVICE_AUTO_START
    Invoke-Nssm set $MinioService AppStdout "$Root\data\logs\minio.log"
    Invoke-Nssm set $MinioService AppStderr "$Root\data\logs\minio.err"
    Invoke-Nssm set $MinioService AppRotateFiles 1
    Invoke-Nssm set $MinioService AppRestartDelay 2000
    Invoke-Nssm set $MinioService AppExit Default Restart
    Invoke-Nssm start $MinioService | Out-Null
    Start-Sleep -Seconds 4
    $minioOk = try { (Invoke-WebRequest -Uri "http://127.0.0.1:$MinioPort/minio/health/live" -UseBasicParsing -TimeoutSec 6).StatusCode } catch { 0 }
    if ($minioOk -eq 200) {
        Write-Host "[MinIO] 已启动（S3: http://127.0.0.1:$MinioPort  控制台: http://127.0.0.1:$MinioConsolePort  账号 minioadmin/minioadmin）" -ForegroundColor Green
    } else {
        Write-Host "[MinIO] 服务已注册但健康检查未通过（HTTP $minioOk），资料存储将回退本地磁盘；可看 data\logs\minio.err" -ForegroundColor Yellow
    }
} else {
    Write-Host "[MinIO] 跳过（未启用），资料存储用本地磁盘 $Root\data\uploads" -ForegroundColor DarkGray
}

# ---------- 3.5 防火墙放行端口（内网同事可访问） ----------
Write-Host "[防火墙] 放行 TCP $Port ..." -ForegroundColor Yellow
cmd /c "netsh advfirewall firewall add rule name=PM-System-$Port dir=in action=allow protocol=TCP localport=$Port 2>nul" | Out-Null

# ---------- 4. 启动服务 ----------
Write-Host "[服务] 启动 $ServiceName ..." -ForegroundColor Yellow
Invoke-Nssm start $ServiceName
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
