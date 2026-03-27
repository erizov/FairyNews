# Stop process listening on the MVP web port (default 8765).
param(
    [int]$Port = 8765
)
$ErrorActionPreference = "SilentlyContinue"
$seen = @{}
Get-NetTCPConnection -LocalPort $Port -State Listen | ForEach-Object {
    $procId = $_.OwningProcess
    if ($procId -and -not $seen.ContainsKey($procId)) {
        $seen[$procId] = $true
        Stop-Process -Id $procId -Force
        Write-Host "Stopped process $procId"
    }
}
if (-not $seen.Count) {
    Write-Host "No listener on port $Port."
}
