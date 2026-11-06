param([string]$BlenderPath = 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskFile = Join-Path $taskRoot 'assets\blender\calibration.blend'
if (-not (Test-Path -LiteralPath $BlenderPath)) { throw "Blender not found: $BlenderPath" }
if (-not (Test-Path -LiteralPath $taskFile)) { throw 'Run tools/export-calibration.ps1 first.' }
$taskConnection = [System.Net.Sockets.TcpClient]::new()
try {
    $taskConnection.Connect('127.0.0.1', 9876)
    Write-Output 'An MCP endpoint is already listening on localhost:9876; no new Blender instance was started.'
    return
} catch {
    if ($_.Exception.InnerException -is [System.Net.Sockets.SocketException] -and $_.Exception.InnerException.SocketErrorCode -eq 'AccessDenied') { throw }
} finally { $taskConnection.Dispose() }
# A new task-local Blender instance; never close or overwrite another scene.
$taskWork = Join-Path $taskRoot 'work'
New-Item -ItemType Directory -Path $taskWork -Force | Out-Null
$taskProcess = Start-Process -FilePath $BlenderPath -ArgumentList ('"' + $taskFile + '"') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskWork 'blender-mcp.stdout.log') -RedirectStandardError (Join-Path $taskWork 'blender-mcp.stderr.log')
Write-Output "Started task Blender PID $($taskProcess.Id). Verify the installed MCP addon at localhost:9876."
