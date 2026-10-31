$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Install requirements.txt in .venv first; see docs/DEVELOPING.md.' }
& $pythonPath (Join-Path $projectPath 'src\main.pyw') @args
if ($LASTEXITCODE -ne 0) { throw 'Source app exited with an error.' }
