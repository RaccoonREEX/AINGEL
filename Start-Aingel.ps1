param([string]$ModelKeyFile = '')
$ErrorActionPreference = 'Stop'
$aingelRoot = $PSScriptRoot
$aingelLocal = Join-Path $aingelRoot '.local'
New-Item -ItemType Directory -Force -Path $aingelLocal | Out-Null
$aingelPython = Join-Path $aingelRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $aingelPython)) { throw 'Create the Python virtual environment and install backend/requirements.lock.txt first.' }
$aingelVite = Join-Path $aingelRoot 'web\node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $aingelVite)) { throw 'Run npm ci in web/ first.' }
$aingelBackend = Join-Path $aingelRoot 'backend'
Push-Location $aingelBackend
try {
    & $aingelPython manage.py migrate
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
    & $aingelPython manage.py seed_demo
    if ($LASTEXITCODE -ne 0) { throw 'Demo setup failed' }
    & $aingelPython manage.py purge_expired_memories
    if ($LASTEXITCODE -ne 0) { throw 'Retention cleanup failed' }
} finally { Pop-Location }
if (-not $ModelKeyFile) {
    $aingelCandidates = @(Get-ChildItem -LiteralPath ([Environment]::GetFolderPath('Desktop')) -File | Where-Object { $_.Name -match '^API AINGEL' })
    if ($aingelCandidates.Count -eq 1) { $ModelKeyFile = $aingelCandidates[0].FullName }
}
$aingelStarted = @()
if (-not (Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue)) {
    $aingelLauncher = Join-Path $aingelBackend 'scripts\serve_local.py'
    $aingelArguments = @("`"$aingelLauncher`"")
    if ($ModelKeyFile) { $aingelArguments += @('--key-file', "`"$ModelKeyFile`"") }
    $aingelProcess = Start-Process -FilePath $aingelPython -ArgumentList $aingelArguments -WorkingDirectory $aingelBackend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $aingelLocal 'backend.log') -RedirectStandardError (Join-Path $aingelLocal 'backend.error.log') -PassThru
    $aingelStarted += @{pid=$aingelProcess.Id;marker=$aingelLauncher}
}
if (-not (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) {
    $aingelNode = (Get-Command node.exe).Source
    $aingelProcess = Start-Process -FilePath $aingelNode -ArgumentList @("`"$aingelVite`"",'--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $aingelRoot 'web') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $aingelLocal 'web.log') -RedirectStandardError (Join-Path $aingelLocal 'web.error.log') -PassThru
    $aingelStarted += @{pid=$aingelProcess.Id;marker=$aingelVite}
}
if ($aingelStarted.Count -gt 0) { ConvertTo-Json -InputObject @($aingelStarted) | Set-Content -LiteralPath (Join-Path $aingelLocal 'processes.json') -Encoding utf8 }
Write-Output 'AINGEL local: http://127.0.0.1:5173/'
Write-Output 'Synthetic test accounts: .local/demo-accounts.json. Keep this file private.'
Write-Output 'Use only synthetic image/audio inputs for Meta tests until privacy review is complete.'
