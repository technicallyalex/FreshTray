param([switch]$Ui)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectPath
try {
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Core tests failed.' }
    if ($Ui) {
        foreach ($test in @('smoke_windows.py','smoke_history.py','smoke_render.py','smoke_launch_calendar.py','smoke_chrome.py','smoke_drag.py','smoke_dock_width.py','smoke_audit.py')) {
            python (Join-Path $projectPath "tests\$test")
            if ($LASTEXITCODE -ne 0) { throw "UI test failed: $test" }
        }
    }
} finally { Pop-Location }
