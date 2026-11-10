# start_windows.ps1 — launch the Whiteboard Catcher watcher (Windows)
# Creates/uses the project venv, installs deps quietly, starts the server,
# then opens the board in your browser. Works from any folder location.

$Watcher     = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $Watcher
$Venv        = Join-Path $ProjectRoot ".venv"

# 1. Venv
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    Write-Host "Creating venv at $Venv ..."
    python -m venv $Venv
}

# 2. Dependencies (quiet)
& (Join-Path $Venv "Scripts\python.exe") -m pip install -q -r (Join-Path $Watcher "requirements.txt")

# 3. Open the board in your browser, then start the server (blocking)
Start-Process msedge http://localhost:8765
Set-Location $Watcher
& (Join-Path $Venv "Scripts\python.exe") server.py
