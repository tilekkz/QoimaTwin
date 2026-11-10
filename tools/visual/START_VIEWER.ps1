$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js 22.12+ is required. See README_MORNING.md.' }
$qoimaPort=if($env:QOIMA_PORT){[int]$env:QOIMA_PORT}else{4180}
Write-Host "Open http://127.0.0.1:$qoimaPort in your browser. Keep this window open."
node (Join-Path $PSScriptRoot 'server.mjs')
