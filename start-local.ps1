$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$web = Join-Path $root "apps\web"

if (-not (Test-Path $python)) {
    Write-Host "Creating Python environment..."
    python -m venv (Join-Path $root ".venv")
    & $python -m pip install -e "$root[dev]"
}

& $python -c "import agentprobe" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing backend dependencies..."
    & $python -m pip install -e "$root[dev]"
}

if (-not (Test-Path (Join-Path $web "node_modules"))) {
    Write-Host "Installing dashboard dependencies..."
    & npm.cmd install --prefix $web
}

$env:AGENTPROBE_STORAGE_BACKEND = "memory"
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000/api/v1"

Write-Host "Starting AgentProbe without Docker..."
$api = Start-Process -FilePath $python -ArgumentList @(
    "-m", "uvicorn", "agentprobe.main:app",
    "--app-dir", (Join-Path $root "apps\api"),
    "--host", "127.0.0.1", "--port", "8000"
) -WorkingDirectory $root -NoNewWindow -PassThru

$dashboard = Start-Process -FilePath "npm.cmd" -ArgumentList @(
    "run", "dev", "--prefix", $web
) -WorkingDirectory $root -NoNewWindow -PassThru

Write-Host ""
Write-Host "Dashboard:       http://localhost:3000"
Write-Host "Test chatbot:    http://localhost:8000/demo"
Write-Host "API docs:        http://localhost:8000/docs"
Write-Host "Storage:         in memory (resets when stopped)"
Write-Host "Press Ctrl+C to stop both services."

try {
    while (-not $api.HasExited -and -not $dashboard.HasExited) {
        Start-Sleep -Seconds 1
    }
}
finally {
    if (-not $api.HasExited) { Stop-Process -Id $api.Id -Force }
    if (-not $dashboard.HasExited) { Stop-Process -Id $dashboard.Id -Force }
}
