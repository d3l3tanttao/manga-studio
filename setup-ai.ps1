param([switch]$SkipDownload)
$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$runtime = $project
$pointer = Join-Path $project '.runtime-path'
if (Test-Path -LiteralPath $pointer) {
    $runtime = [IO.Path]::GetFullPath((Join-Path $project (Get-Content -LiteralPath $pointer -Raw).Trim()))
}
$basePython = Join-Path $runtime '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $basePython)) { throw 'First run setup.ps1 -Device CUDA.' }
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE)." } }
& $basePython -c 'import torch; assert torch.cuda.is_available(), "Install the CUDA runtime first"'
Check-Exit
$envFolder = Join-Path $runtime '.reference-venv'
$aiPython = Join-Path $envFolder 'Scripts\python.exe'
if (!(Test-Path -LiteralPath $aiPython)) {
    & $basePython -m venv $envFolder
    Check-Exit
}
$sharedPackages = Join-Path $runtime '.venv\Lib\site-packages'
$linkFile = Join-Path $envFolder 'Lib\site-packages\manga_shared_runtime.pth'
[IO.File]::WriteAllText($linkFile, $sharedPackages+[Environment]::NewLine, [Text.UTF8Encoding]::new($false))
& $aiPython -m pip install -r (Join-Path $project 'requirements-ai.txt')
Check-Exit
& $aiPython -m pip check
Check-Exit
if (!$SkipDownload) {
    & $aiPython (Join-Path $project 'tools\download_ai.py') --models (Join-Path $runtime '.models')
    Check-Exit
}
Write-Host 'AI runtime is ready. Images are processed locally.'
