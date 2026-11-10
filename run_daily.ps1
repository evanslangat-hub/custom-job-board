$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$root\reports" | Out-Null

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path "$root\logs\run.log" -Value "[$stamp] Starting daily job report" -Encoding UTF8

& python "$root\daily_jobs.py" *>&1 | Out-File -FilePath "$root\logs\run.log" -Append -Encoding utf8
$code = $LASTEXITCODE

$end = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path "$root\logs\run.log" -Value "[$end] Finished with exit code $code" -Encoding UTF8
exit $code
