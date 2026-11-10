param([switch]$Preview)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $taskRoot 'frontend')
try {
    if ($Preview) { & npm.cmd run preview }
    else { & npm.cmd run dev }
    if ($LASTEXITCODE -ne 0) { throw "Client exited with code $LASTEXITCODE" }
} finally { Pop-Location }
