param([Parameter(Mandatory=$true)][string]$ExecutablePath,[switch]$ExpectRollback)
$ErrorActionPreference='Stop'
$projectPath=Split-Path -Parent $PSScriptRoot
$sourcePath=[IO.Path]::GetFullPath($ExecutablePath)
$testId=[Guid]::NewGuid().ToString('N')
$testPath=Join-Path $projectPath ('.build\update-e2e-'+$testId)
$profilePath=Join-Path $testPath 'profile'
$targetPath=Join-Path $testPath ('FreshTray-UpdateTest-'+$testId+'.exe')
New-Item -ItemType Directory -Path $profilePath -Force | Out-Null
Copy-Item -LiteralPath $sourcePath -Destination $targetPath
[IO.File]::WriteAllText((Join-Path $profilePath 'settings.json'),'{"reminders":false,"popup_sound":false,"close_to_tray":false,"auto_updates":false}',[Text.UTF8Encoding]::new($false))
$pythonPath=Join-Path $projectPath '.venv\Scripts\python.exe'
$planPath=& $pythonPath (Join-Path $PSScriptRoot 'prepare_update_fixture.py') $projectPath $targetPath $profilePath
if ($LASTEXITCODE -ne 0) { throw 'Test update preparation failed.' }
$planPath=$planPath.Trim()
$exeName=[IO.Path]::GetFileName($targetPath)
$helperPath=Join-Path (Split-Path -Parent $planPath) 'update-helper.exe'
$oldParent=$null;$helper=$null;$testSucceeded=$false
$previousPath=$env:PATH
function Get-TestProcesses {
    @(Get-CimInstance Win32_Process -Filter "Name='$exeName'" | Where-Object { $_.ExecutablePath -eq $targetPath })
}
try {
    $env:PATH="$env:SystemRoot\System32;$env:SystemRoot"
    $oldParent=Start-Process -FilePath $targetPath -ArgumentList ('--demo --data-dir "'+$profilePath+'"') -WindowStyle Hidden -PassThru
    $deadline=(Get-Date).AddSeconds(25);$gui=$null
    do {
        foreach ($item in (Get-TestProcesses)) {
            if ($item.ParentProcessId -eq $oldParent.Id) {
                $candidate=Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
                if ($candidate -and $candidate.MainWindowTitle -eq 'FreshTray — Offline preview') { $gui=$candidate;break }
            }
        }
        if (-not $gui) { Start-Sleep -Milliseconds 100 }
    } while (-not $gui -and (Get-Date) -lt $deadline)
    if (-not $gui) { throw 'Disposable test app did not open. Close any existing offline preview and retry.' }
    # Let the initial fictional catalog finish; production install is guarded by busy state.
    $deadline=(Get-Date).AddSeconds(10)
    do {
        $settings=Get-Content -LiteralPath (Join-Path $profilePath 'settings.json') -Raw | ConvertFrom-Json
        if ($settings.business_id -ne 1) { Start-Sleep -Milliseconds 100 }
    } while ($settings.business_id -ne 1 -and (Get-Date) -lt $deadline)
    if ($settings.business_id -ne 1) { throw 'Disposable catalog did not load.' }
    Start-Sleep -Milliseconds 500
    $plan=Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
    $plan.pid=$gui.Id
    if ($ExpectRollback) { $plan.version='999.0' }
    [IO.File]::WriteAllText($planPath,($plan | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
    $helper=Start-Process -FilePath $helperPath -ArgumentList ('--apply-update "'+$planPath+'"') -WindowStyle Hidden -PassThru
    if (-not $gui.CloseMainWindow()) { throw 'Could not close disposable test app.' }
    $resultPath=Join-Path (Split-Path -Parent $planPath) 'result.json'
    $deadline=(Get-Date).AddSeconds(65)
    while (-not (Test-Path -LiteralPath $resultPath) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 100 }
    if (-not (Test-Path -LiteralPath $resultPath)) { throw 'Packaged update did not report completion.' }
    $result=Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    if ($ExpectRollback) {
        if ($result.ok) { throw 'Expected failed-start rollback was not triggered.' }
        if (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $planPath) 'ready.json')) { throw 'Invalid update received a readiness receipt.' }
    } elseif (-not $result.ok) { throw ('Packaged update failed: '+$result.message) }
    if ((Get-FileHash -LiteralPath $sourcePath).Hash -ne (Get-FileHash -LiteralPath $targetPath).Hash) { throw 'Installed hash mismatch.' }
    if (-not (Get-TestProcesses)) { throw 'Updated test app did not remain running.' }
    $testSucceeded=$true
    if ($ExpectRollback) { Write-Output 'PASS: frozen helper rejected the wrong startup version, restored the previous disposable EXE, and restarted it.' }
    else { Write-Output 'PASS: copied frozen helper waited for exit, replaced a disposable EXE, restarted it with isolated demo data, and received startup acknowledgement.' }
} finally {
    $env:PATH=$previousPath
    if (-not $testSucceeded) {
        # Stop only this test's copied helper, including its one-file child.
        foreach ($item in @(Get-CimInstance Win32_Process -Filter "Name='update-helper.exe'" | Where-Object { $_.ExecutablePath -eq $helperPath })) {
            Stop-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
        }
    }
    foreach ($item in (Get-TestProcesses)) {
        $process=Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
        if ($process -and $process.MainWindowHandle -ne 0) { [void]$process.CloseMainWindow() }
    }
    $deadline=(Get-Date).AddSeconds(8)
    while ((Get-TestProcesses) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 100 }
    foreach ($item in (Get-TestProcesses)) { Stop-Process -Id $item.ProcessId -ErrorAction SilentlyContinue }
}
