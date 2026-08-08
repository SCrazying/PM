# PM-System 数据库初始化（Windows）

# 用法：powershell -ExecutionPolicy Bypass -File deploy\scripts\init_db.ps1

# 功能：幂等创建应用用户/数据库 → 执行 Alembic 迁移建表 → 写入种子数据(内置TR模板/管理员/配置)

# 前置：本机已安装 PostgreSQL 14+ 与 Python（含后端依赖）

param(

    [string]$PgHost = "127.0.0.1",

    [string]$PgPort = "5432",

    [string]$PgUser = "postgres",

    [string]$PgPassword = "",

    [string]$AppUser = "pm",

    [string]$AppPassword = "postgres",

    [string]$DbName = "pm_system",

    [string]$Psql = "",

    [string]$BackendDir = "",

    [string]$Python = ""    # 便携 Python 路径（内网未装 Python 时传入，用于迁移/种子）

)

$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8



function Find-Psql {

    param([string]$Hint)

    if ($Hint -and (Test-Path $Hint)) { return $Hint }

    if (Get-Command psql -ErrorAction SilentlyContinue) { return (Get-Command psql).Source }

    # 常见安装路径：C:\Program Files\PostgreSQL\<version>\bin\psql.exe

    $root = "C:\Program Files\PostgreSQL"

    if (Test-Path $root) {

        $latest = Get-ChildItem $root -Directory | Sort-Object { [int]$_.Name } -Descending | Select-Object -First 1

        if ($latest) {

            $candidate = Join-Path $latest.FullName "bin\psql.exe"

            if (Test-Path $candidate) { return $candidate }

        }

    }

    throw "未找到 psql，请用 -Psql 参数指定 psql.exe 路径（或把 PostgreSQL bin 加入 PATH）"

}



$Psql = Find-Psql $Psql

if (-not $PgPassword) {

    $PgPassword = Read-Host "请输入 PostgreSQL 超级用户($PgUser)密码"

}

# 设置密码环境变量，避免 psql 交互式提示密码

$env:PGPASSWORD = $PgPassword

if (-not $BackendDir) {

    $BackendDir = Join-Path $PSScriptRoot "..\..\backend"

}

$BackendDir = [System.IO.Path]::GetFullPath($BackendDir)

if (-not (Test-Path (Join-Path $BackendDir "alembic.ini"))) {

    throw "后端目录不正确：$BackendDir（缺少 alembic.ini）"

}



Write-Host "==> psql:      $Psql" -ForegroundColor Cyan

Write-Host "==> 后端目录:  $BackendDir" -ForegroundColor Cyan

Write-Host "==> 目标库:    $DbName（用户 $AppUser）" -ForegroundColor Cyan



# 1. 建应用用户与数据库（幂等）

Write-Host "==> 检查/创建用户 $AppUser ..." -ForegroundColor Yellow

# 注意：psql 查询无结果/连接失败时输出可能为 null，先 Out-String 再 Trim，避免"对 Null 值调用方法"

$roleOut = (& $Psql -h $PgHost -p $PgPort -U $PgUser -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$AppUser'" 2>$null) | Out-String

$roleExists = ("$roleOut".Trim() -eq "1")

if (-not $roleExists) {

    & $Psql -h $PgHost -p $PgPort -U $PgUser -d postgres -c "CREATE USER $AppUser WITH PASSWORD '$AppPassword'"

    Write-Host "   已创建用户 $AppUser" -ForegroundColor Green

} else {

    Write-Host "   用户已存在，跳过" -ForegroundColor DarkGray

}



Write-Host "==> 检查/创建数据库 $DbName ..." -ForegroundColor Yellow

$dbOut = (& $Psql -h $PgHost -p $PgPort -U $PgUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'" 2>$null) | Out-String

$dbExists = ("$dbOut".Trim() -eq "1")

if (-not $dbExists) {

    & $Psql -h $PgHost -p $PgPort -U $PgUser -d postgres -c "CREATE DATABASE $DbName OWNER $AppUser"

    Write-Host "   已创建数据库 $DbName" -ForegroundColor Green

} else {

    Write-Host "   数据库已存在，跳过" -ForegroundColor DarkGray

}



# 2. 写后端 .env 的 DATABASE_URL（若已存在则替换/补全）

$envFile = Join-Path $BackendDir ".env"

if (-not (Test-Path $envFile)) {

    if (Test-Path (Join-Path $BackendDir ".env.example")) {

        Copy-Item (Join-Path $BackendDir ".env.example") $envFile

    }

}

if (Test-Path $envFile) {

    $content = Get-Content $envFile -Raw

    $url = "postgresql+psycopg2://$AppUser`:$AppPassword@$PgHost`:$PgPort/$DbName"

    if ($content -match "(?m)^DATABASE_URL=.*") {

        $content = $content -replace "(?m)^DATABASE_URL=.*", "DATABASE_URL=$url"

    } else {

        $content += "`nDATABASE_URL=$url`n"

    }

    Set-Content -Path $envFile -Value $content -Encoding UTF8

    Write-Host "==> 已更新 $envFile 的 DATABASE_URL" -ForegroundColor Green

}



# 3. Alembic 迁移建表

Write-Host "==> 执行 Alembic 迁移（建表）..." -ForegroundColor Yellow

Push-Location $BackendDir

try {

    $PyDir = $BackendDir.Replace('', '/')

    if ($Python -and (Test-Path $Python)) {
        & $Python -m alembic upgrade head
    } elseif (Test-Path (Join-Path $BackendDir "venv\Scripts\alembic.exe")) {

        & (Join-Path $BackendDir "venv\Scripts\alembic.exe") upgrade head

    } elseif (Get-Command alembic -ErrorAction SilentlyContinue) {

        & alembic upgrade head

    } else {

        python -m alembic upgrade head

    }

    if ($LASTEXITCODE -ne 0) { throw "Alembic 迁移失败" }

    Write-Host "   迁移完成" -ForegroundColor Green



    # 4. 种子数据（把 psql 目录加入 PATH，让 seed 优先用原生 psql 执行）

    Write-Host "==> 写入种子数据（内置TR模板/管理员/配置）..." -ForegroundColor Yellow

    $psqlDir = Split-Path $Psql

    if ($env:PATH -notlike "*$psqlDir*") {

        $env:PATH = "$psqlDir;$env:PATH"

    }

    if ($Python -and (Test-Path $Python)) {

        & $Python -c "import sys; sys.path.insert(0, r'$PyDir'); from app.seed import run; sys.exit(run())"

    } elseif (Get-Command python -ErrorAction SilentlyContinue) {

        & python -c "import sys; sys.path.insert(0, r'$PyDir'); from app.seed import run; sys.exit(run())"

    } else {

        & (Join-Path $BackendDir "venv\Scripts\python.exe") -c "import sys; sys.path.insert(0, r'$PyDir'); from app.seed import run; sys.exit(run())"

    }

    if ($LASTEXITCODE -ne 0) { throw "种子数据写入失败" }

    Write-Host "   种子数据完成" -ForegroundColor Green

} finally {

    Pop-Location

}



Write-Host ""

Write-Host "==========================================" -ForegroundColor Green

Write-Host "[OK] 数据库初始化完成：$DbName"

Write-Host "   应用用户: $AppUser / $AppPassword"

Write-Host "   初始管理员: admin / admin123（请登录后立即修改）"

Write-Host "==========================================" -ForegroundColor Green

