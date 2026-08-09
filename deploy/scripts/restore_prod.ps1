# PM-System 数据库恢复引导（调用 db_restore.py，带确认）
# 用法：powershell -ExecutionPolicy Bypass -File restore_prod.ps1 -File "backups\db_xxx.sql"
param([Parameter(Mandatory=$true)][string]$File)
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ScriptDir "..\pm-prod\runtime\python\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
& $Python "$ScriptDir\db_restore.py" --file $File
exit $LASTEXITCODE
