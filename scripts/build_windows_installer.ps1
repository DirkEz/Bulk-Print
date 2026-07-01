param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller certifi

pyinstaller --clean --windowed --name BulkPrint --icon assets/deyvo-logo.ico --add-data "assets;assets" --hidden-import=_socket --hidden-import=socket --hidden-import=ssl --hidden-import=_ssl --hidden-import=certifi --hidden-import=requests --hidden-import=urllib3 --hidden-import=fitz main.py

$env:APP_VERSION = $Version
iscc installer\bulk-print.iss

Write-Host "Installer gemaakt: dist\BulkPrint-Setup-v$Version.exe"
