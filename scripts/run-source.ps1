$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
& python (Join-Path $projectPath 'src\main.pyw') @args
if ($LASTEXITCODE -ne 0) { throw 'Source app exited with an error.' }
