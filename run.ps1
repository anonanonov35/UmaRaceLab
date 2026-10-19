$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$candidates = @()
if ($env:UMA_LAB_PYTHON) { $candidates += $env:UMA_LAB_PYTHON }
$candidates += Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) { $candidates += $pythonCommand.Source }
foreach ($candidate in $candidates) {
    if ((Test-Path -LiteralPath $candidate) -and ($candidate -notlike '*WindowsApps*')) {
        & $candidate -c 'import sys, tkinter, sqlite3; assert sys.version_info >= (3, 11)' 2>$null
        if ($LASTEXITCODE -eq 0) {
            & $candidate -X utf8 -m uma_lab
            exit $LASTEXITCODE
        }
    }
}
throw 'Python 3.11+ with Tk is required. Set UMA_LAB_PYTHON to its python.exe path.'
