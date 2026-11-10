param([switch]$Render,[string]$BlenderPath='C:/Program Files/Blender Foundation/Blender 5.0/blender.exe')
$ErrorActionPreference='Stop'
$qoimaRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $qoimaRoot
if(-not(Test-Path -LiteralPath $BlenderPath)){throw "Blender not found: $BlenderPath"}
foreach($qoimaModule in @('build_storage_environment','build_logistics','build_equipment','build_personnel','export_calibration_v2','assemble_large_warehouse')){
  & $BlenderPath --background --python 'tools/blender/v2/run_build.py' -- $qoimaModule
  if($LASTEXITCODE -ne 0){throw "Asset build failed: $qoimaModule"}
}
if($Render){
  foreach($qoimaAsset in (Get-ChildItem -LiteralPath 'assets/v2/blender' -Filter '*.blend' | Where-Object {$_.BaseName -notin @('calibration-v2','large-warehouse')})){
    & $BlenderPath --background $qoimaAsset.FullName --python 'tools/blender/render_asset.py' -- $qoimaAsset.BaseName --namespace v2
    if($LASTEXITCODE -ne 0){throw "Preview failed: $($qoimaAsset.BaseName)"}
  }
}
$qoimaPython=if(Test-Path -LiteralPath '.venv/Scripts/python.exe'){Join-Path $qoimaRoot '.venv/Scripts/python.exe'}else{'python'}
& $qoimaPython 'tools/verify_visual_assets_v2.py'
if($LASTEXITCODE -ne 0){throw 'Independent GLB verification failed'}
