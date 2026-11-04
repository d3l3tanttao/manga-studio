$ErrorActionPreference = "Stop"
$project = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $project ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath (Join-Path $project ".runtime-path")) {
    $runtime = (Get-Content -LiteralPath (Join-Path $project ".runtime-path") -Raw).Trim()
    $python = Join-Path (Join-Path $project $runtime) ".venv\Scripts\python.exe"
}
$env:QT_QPA_PLATFORM = "offscreen"
Push-Location $project
try {
    @'
from pathlib import Path
from PIL import Image
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
app = QApplication([])
pixmap = QIcon("studio/mark.svg").pixmap(256, 256)
if pixmap.isNull():
    raise RuntimeError("Could not render application icon")
icon = Image.fromqimage(pixmap.toImage())
icon.save("windows/studio.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
'@ | & $python -
    if ($LASTEXITCODE -ne 0) { throw "Icon build failed" }
    $compiler = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    $source = Join-Path $PSScriptRoot "Launcher.cs"
    $icon = Join-Path $PSScriptRoot "studio.ico"
    & $compiler /nologo /target:winexe /codepage:65001 /reference:System.Windows.Forms.dll /reference:System.Web.Extensions.dll "/win32icon:$icon" '/out:Manga Studio 1.2.exe' $source
    if ($LASTEXITCODE -ne 0) { throw "Launcher build failed" }
} finally {
    Pop-Location
}
