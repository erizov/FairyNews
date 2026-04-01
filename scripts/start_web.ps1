# Start FairyNews MVP (uvicorn) in a separate minimized console window.
param(
    [int]$Port = 8765,
    [switch]$Reload
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$py = if (Test-Path ".venv\Scripts\python.exe") {
    (Resolve-Path ".venv\Scripts\python.exe").Path
} else {
    (Get-Command python -ErrorAction Stop).Source
}

$argList = @(
    "-m", "uvicorn",
    "app.main:app",
    "--host", "127.0.0.1",
    "--port", "$Port"
)
if ($Reload) {
    $argList += "--reload"
}
Start-Process -FilePath $py -ArgumentList $argList `
    -WorkingDirectory $Root -WindowStyle Minimized
$mode = if ($Reload) { "reload" } else { "fixed" }
Write-Host (
    "Started http://127.0.0.1:$Port ($mode, new window). " +
    "Configure API keys in .env if needed."
)
