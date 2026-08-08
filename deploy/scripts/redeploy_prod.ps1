# PM-System 重新部署（卸载服务 → 重新部署，保留数据文件）
# 用法：powershell -ExecutionPolicy Bypass -File redeploy_prod.ps1
# 说明：
#   - 先执行 uninstall_prod.ps1（-KeepData 保留上传/备份/日志，不删数据目录）
#   - 再执行 deploy_prod.ps1（生成 .env、跑迁移/种子、NSSM 重注册并启动服务）
#   - 适合升级后让服务加载新代码：先停旧服务，再按新代码重新部署
#   - 原有 uninstall_prod.ps1 / deploy_prod.ps1 保留，仍可单独使用
param(
    [string]$PgPassword = "postgres",   # PostgreSQL 超级用户密码
    [int]$Port = 8001,                  # 后端端口（默认 8001）
    [string]$ServiceName = "pm-system", # Windows 服务名
    [string]$AppUser = "pm",
    [string]$AppPassword = "pm123",
    [string]$DbName = "pm_system",
    [string]$JwtSecret = ""             # 不填则复用 .env 已有 secret
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  PM-System 重新部署（先卸载，再部署，保留数据）" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# ---------- 1. 卸载（保留数据） ----------
Write-Host ""
Write-Host "==> 步骤 1/2：卸载服务 $ServiceName（保留数据）..." -ForegroundColor Yellow
& "$PSScriptRoot\uninstall_prod.ps1" -ServiceName $ServiceName -KeepData
if ($LASTEXITCODE -ne 0) { throw "卸载失败（步骤 1/2）" }

# ---------- 2. 重新部署 ----------
Write-Host ""
Write-Host "==> 步骤 2/2：重新部署（迁移/种子/重注册服务并启动）..." -ForegroundColor Yellow
& "$PSScriptRoot\deploy_prod.ps1" `
    -PgPassword $PgPassword -Port $Port -ServiceName $ServiceName `
    -AppUser $AppUser -AppPassword $AppPassword -DbName $DbName -JwtSecret $JwtSecret
if ($LASTEXITCODE -ne 0) { throw "重新部署失败（步骤 2/2）" }

Write-Host ""
Write-Host "[OK] 重新部署完成：服务 $ServiceName 已用最新代码启动" -ForegroundColor Green
Write-Host "    访问 http://localhost:$Port  初始账号 admin / admin123" -ForegroundColor Cyan
