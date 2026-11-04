param(
    [ValidateSet('CPU','CUDA')] [string]$Device = 'CPU',
    [switch]$InstallEngine,
    [switch]$DownloadWeights,
    [string]$Wheelhouse
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE)." } }
if (!(Test-Path -LiteralPath $python)) {
    & py -3.10 -m venv (Join-Path $root '.venv')
    Check-Exit
}
if ($Wheelhouse) {
    $variant = if ($Device -eq 'CPU') { 'cpu' } else { 'cu128' }
    & $python -m pip install --no-index --find-links $Wheelhouse "torch==2.8.0+$variant" "torchvision==0.23.0+$variant" -r (Join-Path $root 'requirements.txt')
    Check-Exit
} else {
    $variant = if ($Device -eq 'CPU') { 'cpu' } else { 'cu128' }
    & $python -m pip install --index-url "https://download.pytorch.org/whl/$variant" "torch==2.8.0+$variant" "torchvision==0.23.0+$variant"
    Check-Exit
    & $python -m pip install -r (Join-Path $root 'requirements.txt')
    Check-Exit
}
if ($InstallEngine) {
    $engine = Join-Path $root '.upstream'
    $rev = 'a0d0e4482e5e86ddbd49958475f3e95f282a1915'
    if (!(Test-Path -LiteralPath $engine)) {
        & git clone https://github.com/qweasdd/manga-colorization-v2.git $engine
        Check-Exit
        & git -C $engine checkout --detach $rev
        Check-Exit
    }
    if ((& git -C $engine rev-parse HEAD) -ne $rev) { throw "Use the engine revision listed in CREDITS.md." }
}
if ($DownloadWeights) {
    $weights = Join-Path $root '.models'
    New-Item -ItemType Directory -Force -Path $weights | Out-Null
    $files = @(
        @('generator.zip','1qmxUEKADkEM4iYLp1fpPLLKnfZ6tcF-t','087e6a0bc02770e732a52f33878b71a272a6123c9ac649e9b5bfb75e39e5c1d5'),
        @('net_rgb.pth','161oyQcYpdkVdw8gKz_MA8RD-Wtg9XDp3','0fe98bfd2ac870b15f360661b1c4789eecefc6dc2e4462842a0dd15e149a0433')
    )
    foreach ($file in $files) {
        $target = Join-Path $weights $file[0]
        if (!(Test-Path -LiteralPath $target)) {
            $temp = Join-Path $weights ([guid]::NewGuid().ToString()+'.tmp')
            try {
                & curl.exe --fail --silent --show-error --location --retry 2 --retry-all-errors --connect-timeout 20 --max-time 600 --output $temp ("https://drive.usercontent.google.com/download?id="+$file[1]+"&export=download&confirm=t")
                Check-Exit
                if ((Get-FileHash -LiteralPath $temp).Hash -ne $file[2]) { throw "Invalid checkpoint: $($file[0])" }
                Move-Item -LiteralPath $temp -Destination $target
            } finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp } }
        }
        if ((Get-FileHash -LiteralPath $target).Hash -ne $file[2]) { throw "Unexpected checkpoint: $target" }
    }
}
& (Join-Path $root 'windows\build.ps1')
