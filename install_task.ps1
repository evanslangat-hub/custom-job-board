param(
    [string]$Time = "07:00"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskName = "Daily Data Engineering Job Report"

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$root\run_daily.ps1`""
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Fetches data engineering jobs and emails the HTML report every morning." -Force | Out-Null

Write-Output "Scheduled task '$taskName' installed. It will run daily at $Time."
Write-Output "Test it now with:  powershell -ExecutionPolicy Bypass -File `"$root\run_daily.ps1`""
