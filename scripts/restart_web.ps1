# Stop then start FairyNews (uvicorn). Same params as start_web.ps1.
param(
    [int]$Port = 8765,
    [switch]$Reload
)
$ErrorActionPreference = "Stop"
& "$PSScriptRoot\stop_web.ps1" -Port $Port
Start-Sleep -Seconds 1
if ($Reload) {
    & "$PSScriptRoot\start_web.ps1" -Port $Port -Reload
} else {
    & "$PSScriptRoot\start_web.ps1" -Port $Port
}
