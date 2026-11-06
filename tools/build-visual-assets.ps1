[CmdletBinding()]
param(
    [string]$BlenderPath = 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe',
    [switch]$Render
)

$ErrorActionPreference = 'Stop'
$taskRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$taskBlenderScripts = Join-Path $taskRoot 'tools\blender'
$taskRunBuild = Join-Path $taskBlenderScripts 'run_build.py'
$taskRenderScript = Join-Path $taskBlenderScripts 'render_asset.py'
$taskLogRoot = Join-Path $taskRoot 'work\visual-assets-build'
$taskAssets = @(
    @{ Id = 'environment'; Module = 'build_environment' },
    @{ Id = 'rack-bay'; Module = 'build_rack_bay' },
    @{ Id = 'crate'; Module = 'build_crate' },
    @{ Id = 'picker-cart'; Module = 'build_picker_cart' },
    @{ Id = 'packing-station'; Module = 'build_packing_station' },
    @{ Id = 'forklift'; Module = 'build_forklift' },
    @{ Id = 'ibc-tote'; Module = 'build_ibc_tote' },
    @{ Id = 'buffer-pallet'; Module = 'build_buffer_pallet' }
)

function Invoke-TaskBlender {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$BlenderArguments
    )
    $taskStdout = Join-Path $taskLogRoot ($Label + '.stdout.log')
    $taskStderr = Join-Path $taskLogRoot ($Label + '.stderr.log')
    # Windows paths cannot contain quote characters. Quote every separate argument
    # because Start-Process joins ArgumentList into one native command line.
    foreach ($taskArgument in $BlenderArguments) {
        if ($taskArgument.Contains('"')) { throw "Unexpected quote in Blender argument: $taskArgument" }
    }
    $taskArgumentLine = ($BlenderArguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
    Write-Output "Running $Label"
    $taskProcess = Start-Process -FilePath $BlenderPath -ArgumentList $taskArgumentLine -WorkingDirectory $taskRoot -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $taskStdout -RedirectStandardError $taskStderr
    Write-Output ("{0}: exit {1}; logs: {2} ; {3}" -f $Label, $taskProcess.ExitCode, $taskStdout, $taskStderr)
    if ($taskProcess.ExitCode -ne 0) {
        foreach ($taskLog in @($taskStdout, $taskStderr)) {
            if (Test-Path -LiteralPath $taskLog) {
                Write-Output "Last output from $taskLog"
                Get-Content -LiteralPath $taskLog -Tail 30
            }
        }
        throw ("Blender failed during {0} with exit code {1}." -f $Label, $taskProcess.ExitCode)
    }
}

function Assert-TaskOutput {
    param([string]$Path, [datetime]$StartedUtc)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Expected output was not created: $Path"
    }
    $taskOutput = Get-Item -LiteralPath $Path
    if ($taskOutput.Length -le 0 -or $taskOutput.LastWriteTimeUtc -lt $StartedUtc.AddSeconds(-2)) {
        throw "Expected a fresh, nonempty output: $Path"
    }
}

try {
    if (-not (Test-Path -LiteralPath $BlenderPath -PathType Leaf)) { throw "Blender not found: $BlenderPath" }
    $BlenderPath = (Get-Item -LiteralPath $BlenderPath).FullName
    $taskRequired = @($taskRunBuild, (Join-Path $taskBlenderScripts 'asset_common.py'), (Join-Path $taskBlenderScripts 'assemble_warehouse.py'), (Join-Path $taskRoot 'contracts\layout.example.json'))
    $taskRequired += $taskAssets | ForEach-Object { Join-Path $taskBlenderScripts ($_.Module + '.py') }
    if ($Render) { $taskRequired += $taskRenderScript }
    foreach ($taskInput in $taskRequired) {
        if (-not (Test-Path -LiteralPath $taskInput -PathType Leaf)) { throw "Required input missing: $taskInput" }
    }
    New-Item -ItemType Directory -Path $taskLogRoot -Force | Out-Null
    Write-Output "Project: $taskRoot"
    Write-Output "Blender: $BlenderPath"
    Write-Output "Editable sources: $(Join-Path $taskRoot 'assets\blender')"
    Write-Output "Runtime models: $(Join-Path $taskRoot 'frontend\public\models')"

    # A fresh background process per build, strictly serial. Never use a live GUI
    # scene or the user's running Blender session.
    $taskBuilds = @($taskAssets) + @(@{ Id = 'warehouse'; Module = 'assemble_warehouse' })
    foreach ($taskAsset in $taskBuilds) {
        $taskStarted = [datetime]::UtcNow
        Invoke-TaskBlender -Label ('build-' + $taskAsset.Id) -BlenderArguments @('--background', '--factory-startup', '--python-exit-code', '1', '--python', $taskRunBuild, '--', $taskAsset.Module)
        foreach ($taskRelativeOutput in @(
            ('assets\blender\' + $taskAsset.Id + '.blend'),
            ('assets\blender\' + $taskAsset.Id + '.stats.json'),
            ('frontend\public\models\' + $taskAsset.Id + '.glb')
        )) {
            $taskOutputPath = Join-Path $taskRoot $taskRelativeOutput
            Assert-TaskOutput -Path $taskOutputPath -StartedUtc $taskStarted
            Write-Output "Created: $taskOutputPath"
        }
    }

    if ($Render) {
        foreach ($taskAsset in $taskAssets) {
            $taskStarted = [datetime]::UtcNow
            $taskSource = Join-Path $taskRoot ('assets\blender\' + $taskAsset.Id + '.blend')
            Invoke-TaskBlender -Label ('render-' + $taskAsset.Id) -BlenderArguments @('--background', $taskSource, '--python-exit-code', '1', '--python', $taskRenderScript, '--', $taskAsset.Id)
            foreach ($taskView in @('front', 'side', 'rear', 'three-quarter')) {
                Assert-TaskOutput -Path (Join-Path $taskRoot ('assets\previews\' + $taskAsset.Id + '\' + $taskView + '.png')) -StartedUtc $taskStarted
            }
            Write-Output "Four views: $(Join-Path $taskRoot ('assets\previews\' + $taskAsset.Id))"
        }
    }
    Write-Output 'Completed all eight asset builds and the warehouse assembly.'
    if ($Render) { Write-Output 'Completed front, side, rear and three-quarter previews for all eight assets.' }
    exit 0
} catch {
    Write-Error ("Visual asset build failed: " + $_.Exception.Message) -ErrorAction Continue
    exit 1
}

