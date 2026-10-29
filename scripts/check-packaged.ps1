param([string]$ExecutablePath = "")
$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path -Parent $PSScriptRoot
$exePath = if ($ExecutablePath) { [IO.Path]::GetFullPath($ExecutablePath) } else { Join-Path $workspacePath 'app\FreshTray\FreshTray.exe' }
$existingPreview = Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('FreshTray.exe','pythonw.exe','python.exe') -and $_.CommandLine -like '*--demo*' -and $_.CommandLine -like '*FreshTray*' }
if ($existingPreview) { throw 'Close the existing FreshTray offline preview before running this packaged check.' }
$profilePath = Join-Path $workspacePath ('.build\packaged-preview-' + [Guid]::NewGuid().ToString('N'))
$settingsPath = Join-Path $profilePath 'settings.json'
$startedProcess = Start-Process -FilePath $exePath -ArgumentList @('--demo', '--data-dir', ('"' + $profilePath + '"')) -WindowStyle Hidden -PassThru
try {
    $deadline = (Get-Date).AddSeconds(12)
    do {
        Start-Sleep -Milliseconds 300
        $startedProcess.Refresh()
        if ($startedProcess.HasExited) { throw 'Packaged app exited before opening.' }
        $title = $startedProcess.MainWindowTitle
        $settings = $null
        if (Test-Path -LiteralPath $settingsPath) {
            try { $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json } catch { }
        }
    } while ((($title -notlike 'FreshTray*') -or ($null -eq $settings) -or ($settings.business_id -ne 1)) -and ((Get-Date) -lt $deadline))
    if ($title -ne 'FreshTray — Offline preview') { throw "Unexpected preview window: $title" }
    if (-not (Test-Path -LiteralPath $settingsPath)) { throw 'Packaged demo did not load catalog/settings.' }
    $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
    if ($settings.business_id -ne 1) { throw 'Packaged demo business was not loaded.' }
    Write-Output 'PASS: Packaged executable opened its offline preview and loaded the demo business without Python.'
} finally {
    # Only the exact offline preview process created above; no real writes are in flight.
    if (-not $startedProcess.HasExited) { Stop-Process -Id $startedProcess.Id }
}
