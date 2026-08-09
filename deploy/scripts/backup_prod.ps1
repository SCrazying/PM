# PM-System 一键数据库备份（调用 db_backup.py）
# 用法：powershell -ExecutionPolicy Bypass -File backup_prod.ps1 [-Keep 14] [-OutputDir "D:\backups"]
param(
    [int]$Keep = 14,
    [string]$OutputDir = ""
)
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ScriptDir "..\pm-prod\runtime\python\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }   # 兜底：系统 python

$args = @("$ScriptDir\db_backup.py", "--keep", $Keep)
if ($OutputDir) { $args += @("--output-dir", $OutputDir) }

& $Python $args
exit $LASTEXITCODE
