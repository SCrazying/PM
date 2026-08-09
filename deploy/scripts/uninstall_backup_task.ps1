# 卸载备份定时任务
# 用法：powershell -ExecutionPolicy Bypass -File uninstall_backup_task.ps1 [-TaskName "PM-Backup"]
param([string]$TaskName = "PM-System-Backup")
$ErrorActionPreference = "Stop"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "[OK] 已卸载定时备份任务：$TaskName" -ForegroundColor Green
