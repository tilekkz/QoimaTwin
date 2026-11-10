param([string]$BlenderPath = 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe')
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $BlenderPath)) { throw "Blender not found: $BlenderPath" }
$taskRoot = Split-Path -Parent $PSScriptRoot
& $BlenderPath --background --factory-startup --python-exit-code 1 --python (Join-Path $taskRoot 'tools\blender\export_calibration.py')
if ($LASTEXITCODE -ne 0) { throw "Blender export failed: $LASTEXITCODE" }
