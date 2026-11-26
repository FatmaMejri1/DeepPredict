$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv312\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "AI service Python 3.12 environment is missing. Create it with: py -3.12 -m venv .venv312"
}

Push-Location $PSScriptRoot
try {
    & $python -c "import sys, torch; assert sys.version_info[:2] == (3, 12), f'Python 3.12 is required, found {sys.version.split()[0]}'; assert torch.__version__ == '2.15.0+cpu', f'Expected the CPU PyTorch 2.15.0 wheel, found {torch.__version__}'; print('Python', sys.version.split()[0], '| PyTorch', torch.__version__, 'ready')"
    if ($LASTEXITCODE -ne 0) {
        throw "PyTorch failed to load in .venv312. Reinstall the service dependencies in that environment."
    }

    & $python -m uvicorn service.app:app --host 127.0.0.1 --port 8001
    if ($LASTEXITCODE -ne 0) {
        throw "The AI service exited with code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
