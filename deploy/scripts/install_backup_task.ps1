# 把备份注册为 Windows 定时任务（每日执行）
# 用法：powershell -ExecutionPolicy Bypass -File install_backup_task.ps1 [-TaskName "PM-Backup"] [-Time "23:00"]
param(
    [string]$TaskName = "PM-System-Backup",
    [string]$Time = "23:00"
)
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackupPs1 = Join-Path $ScriptDir "backup_prod.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$BackupPs1`""
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "[OK] 定时备份任务已注册：$TaskName，每日 $Time 执行" -ForegroundColor Green
Write-Host "    手动触发：Start-ScheduledTask -TaskName `"$TaskName`"" -ForegroundColor Cyan
Write-Host "    卸载：powershell -File uninstall_backup_task.ps1" -ForegroundColor Cyan
