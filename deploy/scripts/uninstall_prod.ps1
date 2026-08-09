# PM-System 生产卸载（Windows）
# 用法：powershell -ExecutionPolicy Bypass -File uninstall_prod.ps1
param(
    [string]$ServiceName = "pm-system",
    [switch]$KeepData   # 保留数据文件（默认不删；不加此开关则提示是否删除数据）
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Nssm = Join-Path $Root "deploy\bin\nssm.exe"

Write-Host "==> 停止并删除服务 $ServiceName ..." -ForegroundColor Yellow
& $Nssm stop $ServiceName 2>$null | Out-Null
Start-Sleep -Seconds 2
& $Nssm remove $ServiceName confirm

# 同时清理 MinIO 对象存储服务（若存在）
$MinioService = "$ServiceName-minio"
if ($null -ne (Get-Service -Name $MinioService -ErrorAction SilentlyContinue)) {
    Write-Host "==> 停止并删除服务 $MinioService ..." -ForegroundColor Yellow
    & $Nssm stop $MinioService 2>$null | Out-Null
    Start-Sleep -Seconds 2
    & $Nssm remove $MinioService confirm 2>$null | Out-Null
}

if (-not $KeepData) {
    $dataDir = Join-Path $Root "data"
    if (Test-Path $dataDir) {
        $ans = Read-Host "是否删除数据目录 $dataDir（上传附件/备份/日志）？(yes/no)"
        if ($ans -eq "yes") { Remove-Item -Recurse -Force $dataDir; Write-Host "   已删除 $dataDir" -ForegroundColor Green }
    }
    Write-Host "提示：如需彻底清理数据库，请用 PostgreSQL 管理工具删除 $($Root)" -ForegroundColor DarkGray
}

Write-Host "[OK] 卸载完成：服务 $ServiceName 已移除（pm-prod 目录可删除）" -ForegroundColor Green
