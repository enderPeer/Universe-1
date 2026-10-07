$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$python = (Get-Command python -ErrorAction Stop).Source
$script = Join-Path $PSScriptRoot 'share_bridge.py'
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match [regex]::Escape($script) }
if ($running) { $running | Select-Object ProcessId,CommandLine; exit 0 }
Start-Process -FilePath $python -ArgumentList @('-u', ('"'+$script+'"')) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'results/share-bridge.log') -RedirectStandardError (Join-Path $projectRoot 'results/share-bridge.err.log') -PassThru | Select-Object Id,ProcessName
