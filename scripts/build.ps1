param([string]$OutputDirectory = 'app')
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
$outputPath = if ([IO.Path]::IsPathRooted($OutputDirectory)) { [IO.Path]::GetFullPath($OutputDirectory) } else { [IO.Path]::GetFullPath((Join-Path $projectPath $OutputDirectory)) }
$running = Get-CimInstance Win32_Process -Filter "Name='FreshTray.exe'" | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($outputPath+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) }
if ($running) { throw 'Quit FreshTray from the tray menu before rebuilding its app folder, or use -OutputDirectory .build/review.' }
Push-Location -LiteralPath $projectPath
try {
    python -m PyInstaller --noconfirm --clean --distpath $outputPath --workpath (Join-Path $projectPath '.build\pyinstaller') (Join-Path $PSScriptRoot 'FreshTray.spec')
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    Write-Host "Ready: $outputPath\FreshTray\FreshTray.exe. Keep the entire FreshTray folder together."
} finally { Pop-Location }
