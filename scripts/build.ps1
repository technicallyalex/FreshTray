param([string]$OutputDirectory = 'app')
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
$outputPath = if ([IO.Path]::IsPathRooted($OutputDirectory)) { [IO.Path]::GetFullPath($OutputDirectory) } else { [IO.Path]::GetFullPath((Join-Path $projectPath $OutputDirectory)) }
$running = Get-CimInstance Win32_Process -Filter "Name='FreshTray.exe'" | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($outputPath+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) }
if ($running) { throw 'Quit FreshTray from the tray menu before rebuilding its app folder, or use -OutputDirectory .build/review.' }
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create the project environment first: python -m venv .venv; ./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt' }
Push-Location -LiteralPath $projectPath
try {
    & $pythonPath -m PyInstaller --noconfirm --clean --distpath $outputPath --workpath (Join-Path $projectPath '.build\pyinstaller') (Join-Path $PSScriptRoot 'FreshTray.spec')
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    Write-Host "Ready: $outputPath\FreshTray.exe. This is a self-contained single-file application."
} finally { Pop-Location }
