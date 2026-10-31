param([string]$ExecutablePath = "")
$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path -Parent $PSScriptRoot
$exePath = if ($ExecutablePath) { [IO.Path]::GetFullPath($ExecutablePath) } else { Join-Path $workspacePath 'app\FreshTray.exe' }
if (-not (Test-Path -LiteralPath $exePath)) { throw 'Build FreshTray.exe first.' }
$existingPreview = Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('FreshTray.exe','pythonw.exe','python.exe') -and $_.CommandLine -like '*--demo*' -and $_.CommandLine -like '*FreshTray*' }
if ($existingPreview) { throw 'Close the existing FreshTray offline preview before running this packaged check.' }
$profilePath = Join-Path $workspacePath ('.build\packaged-preview-' + [Guid]::NewGuid().ToString('N'))
$settingsPath = Join-Path $profilePath 'settings.json'
New-Item -ItemType Directory -Path $profilePath | Out-Null
# Exit normally so the one-file parent can clean up its extracted runtime.
Set-Content -LiteralPath $settingsPath -Value '{"reminders":false,"popup_sound":false,"close_to_tray":false}' -Encoding utf8
function Get-PreviewTree([int]$RootId) {
    $previewExeName = [IO.Path]::GetFileName($exePath)
    $inventory = @(Get-CimInstance Win32_Process -Filter "Name='$previewExeName'")
    $ids = [Collections.Generic.HashSet[int]]::new()
    [void]$ids.Add($RootId)
    do {
        $added = $false
        foreach ($item in $inventory) {
            if ($ids.Contains([int]$item.ParentProcessId) -and $ids.Add([int]$item.ProcessId)) { $added = $true }
        }
    } while ($added)
    foreach ($taskPid in $ids) { Get-Process -Id $taskPid -ErrorAction SilentlyContinue }
}
$previousPath = $env:PATH
try {
    # A standalone copy must not depend on Python or other developer tools on PATH.
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $startedProcess = Start-Process -FilePath $exePath -WorkingDirectory (Split-Path -Parent $exePath) -ArgumentList @('--demo','--data-dir',('"'+$profilePath+'"')) -WindowStyle Hidden -PassThru
} finally { $env:PATH = $previousPath }
$owned = @()
$uiProcess = $null
$stopwatch = [Diagnostics.Stopwatch]::StartNew()
try {
    $deadline = (Get-Date).AddSeconds(35)
    do {
        Start-Sleep -Milliseconds 250
        $startedProcess.Refresh()
        if ($startedProcess.HasExited) { throw 'Packaged app exited before opening.' }
        $owned = @(Get-PreviewTree $startedProcess.Id)
        $uiProcess = $owned | Where-Object { $_.MainWindowTitle -eq 'FreshTray — Offline preview' } | Select-Object -First 1
        if ($owned | Where-Object { $_.MainWindowTitle -eq 'Unhandled exception in script' }) { throw 'Packaged app reported an unhandled startup error.' }
        $settings = $null
        try { $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json } catch { }
    } while ((-not $uiProcess -or $settings.business_id -ne 1) -and (Get-Date) -lt $deadline)
    if (-not $uiProcess -or $settings.business_id -ne 1) { throw 'Standalone preview did not open and load its sample catalog.' }
    Write-Output ('PASS: Standalone preview loaded in {0:N2}s with Python absent from PATH.' -f $stopwatch.Elapsed.TotalSeconds)
} finally {
    # Only descendants of the exact offline process started here, never the user's app.
    $owned = @(Get-PreviewTree $startedProcess.Id)
    foreach ($item in $owned | Where-Object { $_.MainWindowTitle -eq 'FreshTray — Offline preview' }) { [void]$item.CloseMainWindow() }
    if (-not $startedProcess.WaitForExit(8000)) {
        foreach ($item in $owned | Where-Object { $_.Id -ne $startedProcess.Id }) { if (-not $item.HasExited) { Stop-Process -Id $item.Id } }
        if (-not $startedProcess.WaitForExit(3000)) { Stop-Process -Id $startedProcess.Id }
    }
}
