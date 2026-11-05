param(
    [ValidateSet('CPU','CUDA')] [string]$Device = 'CUDA',
    [switch]$SkipAI,
    [switch]$SkipDownload,
    [switch]$InstallSelection,
    [ValidateSet('Small','Large')] [string]$SelectionModel = 'Small',
    [string]$Wheelhouse
)
$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$root = $project
$pointer = Join-Path $project '.runtime-path'
if (Test-Path -LiteralPath $pointer) {
    $root = [IO.Path]::GetFullPath((Join-Path $project (Get-Content -LiteralPath $pointer -Raw).Trim()))
}
$python = Join-Path $root '.venv\Scripts\python.exe'
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE)." } }
if (!(Test-Path -LiteralPath $python)) {
    & py -3.10 -m venv (Join-Path $root '.venv')
    Check-Exit
}
if ($InstallSelection) {
    $selection = Join-Path $root '.sam2'
    $manifest = Get-Content -LiteralPath (Join-Path $project 'studio\backends.json') -Raw | ConvertFrom-Json
    $model = if ($SelectionModel -eq 'Large') { $manifest.selection_large } else { $manifest.selection }
    if (!(Test-Path -LiteralPath $selection)) {
        & git clone $model.source $selection
        Check-Exit
        & git -C $selection checkout --detach $model.revision
        Check-Exit
    }
    if ((& git -C $selection rev-parse HEAD) -ne $model.revision) { throw 'Unexpected SAM 2 source revision.' }
    & $python -m pip install hydra-core==1.3.2 iopath==0.1.10 tqdm==4.67.1 omegaconf==2.3.1 PyYAML==6.0.3 portalocker==4.4.2
    Check-Exit
    $weights = Join-Path $root '.models'
    New-Item -ItemType Directory -Force -Path $weights | Out-Null
    $target = Join-Path $weights $model.weights
    if (!(Test-Path -LiteralPath $target)) {
        $temp = Join-Path $weights ([guid]::NewGuid().ToString()+'.tmp')
        try {
            & curl.exe --fail --silent --show-error --location --retry 2 --retry-all-errors --connect-timeout 20 --max-time 600 --output $temp $model.url
            Check-Exit
            if ((Get-FileHash -LiteralPath $temp).Hash -ne $model.sha256) { throw 'Invalid SAM 2 checkpoint.' }
            Move-Item -LiteralPath $temp -Destination $target
        } finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp } }
    }
    if ((Get-FileHash -LiteralPath $target).Hash -ne $model.sha256) { throw 'Unexpected SAM 2 checkpoint.' }
}
if ($Wheelhouse) {
    $variant = if ($Device -eq 'CPU') { 'cpu' } else { 'cu128' }
    & $python -m pip install --no-index --find-links $Wheelhouse "torch==2.8.0+$variant" "torchvision==0.23.0+$variant" -r (Join-Path $project 'requirements.txt')
    Check-Exit
} else {
    $variant = if ($Device -eq 'CPU') { 'cpu' } else { 'cu128' }
    & $python -m pip install --index-url "https://download.pytorch.org/whl/$variant" "torch==2.8.0+$variant" "torchvision==0.23.0+$variant"
    Check-Exit
    & $python -m pip install -r (Join-Path $project 'requirements.txt')
    Check-Exit
}
if (!$SkipAI -and $Device -eq 'CUDA') {
    & (Join-Path $project 'setup-ai.ps1') -SkipDownload:$SkipDownload
}
& (Join-Path $project 'windows\build.ps1')
