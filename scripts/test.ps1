param([switch]$Ui)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectPath
try {
    $pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
    & $pythonPath -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Core tests failed.' }
    if ($Ui) {
        $pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
        & $pythonPath (Join-Path $projectPath 'tests\smoke_qt.py')
        if ($LASTEXITCODE -ne 0) { throw 'Qt integration checks failed.' }
        & $pythonPath (Join-Path $projectPath 'tests\smoke_choices_qt.py')
        if ($LASTEXITCODE -ne 0) { throw 'Selection persistence checks failed.' }
        & $pythonPath (Join-Path $projectPath 'tests\smoke_offline_qt.py')
        if ($LASTEXITCODE -ne 0) { throw 'Offline sync integration checks failed.' }
        & $pythonPath (Join-Path $projectPath 'tests\smoke_popup_qt.py')
        if ($LASTEXITCODE -ne 0) { throw 'Independent popup checks failed.' }
        foreach ($scale in @('1','1.25','1.5','2')) {
            & $pythonPath (Join-Path $projectPath 'tests\qa_layout_qt.py') --scale $scale
            if ($LASTEXITCODE -ne 0) { throw "Layout QA failed at scale $scale." }
        }
    }
} finally { Pop-Location }
