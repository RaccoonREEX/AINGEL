$ErrorActionPreference='Stop'
$aingelRegistry=Join-Path $PSScriptRoot '.local\processes.json'
if (-not (Test-Path -LiteralPath $aingelRegistry)) { Write-Output 'No launcher-managed processes recorded.'; return }
$aingelProcesses=Get-Content -LiteralPath $aingelRegistry -Raw | ConvertFrom-Json
foreach ($aingelEntry in @($aingelProcesses)) {
    $aingelProcess=Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$aingelEntry.pid)" -ErrorAction SilentlyContinue
    if ($aingelProcess -and $aingelProcess.CommandLine.Contains([string]$aingelEntry.marker)) {
        & taskkill.exe /PID ([string]$aingelEntry.pid) /T /F | Out-Null
    }
}
Write-Output 'Recorded AINGEL processes stopped; unrelated processes were not selected.'
