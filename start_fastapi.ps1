$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    $pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
}

if (-not $pythonPath -or -not (Test-Path $pythonPath)) {
    throw "Python bulunamadı. .venv oluşturun ve requirements.txt dosyasını kurun."
}

& $pythonPath (Join-Path $root "main.py") --api @args
